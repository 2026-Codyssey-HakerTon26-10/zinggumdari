"""가상 인구 생성(backend/population). 네트워크 없이 손으로 만든 Nemotron 행으로 돈다."""

import numpy as np
import pandas as pd
import pytest

from backend.population import features
from backend.population.synth import check, synthesize


def _row(**kw):
    base = {"uuid": "x", "sex": "여자", "age": 30, "marital_status": "미혼", "family_type": "혼자 거주",
            "occupation": "경리 사무원", "province": "서울", "district": "서울-마포구",
            "persona": "김지원 씨는 마포구에 산다.", "family_persona": ""}
    return {**base, **kw}


ROWS = [
    _row(uuid="mom", age=34, marital_status="배우자있음", family_type="배우자·자녀와 거주",
         family_persona="자가 아파트에서 남편, 아이들과 함께 산다."),
    _row(uuid="seeker", age=27, occupation="무직", family_type="부모와 동거",
         family_persona="부모님과 전세 아파트에 살며 취업 준비 중이다."),
    _row(uuid="newlywed", sex="남자", age=31, marital_status="배우자있음", family_type="배우자와 거주",
         family_persona="전세 아파트에서 아내와 신혼 생활을 한다."),
    _row(uuid="ambiguous", age=25, family_persona="전·월세 집에서 혼자 산다."),
    _row(uuid="single_parent", age=36, family_type="자녀와 거주 (한부모)", province="경상남",
         district="경상남-창원시 의창구"),
    _row(uuid="young", age=19, marital_status="배우자있음", family_type="배우자와 거주",
         family_persona="신혼 생활을 한다."),
]


def _users(n_copies=1, seed=0):
    raw = pd.DataFrame(ROWS * n_copies)
    return synthesize(raw, seed=seed, holdout=0).set_index("source_uuid", drop=False)


def test_text_signals_win_over_assumptions():
    u = _users()
    assert u.loc["mom", "children_count"] >= 2
    assert u.loc["mom", "tenure_type"] == "자가" and u.loc["mom", "is_homeless"] == "N"
    assert u.loc["seeker", "employment_status"] == "구직"
    assert u.loc["newlywed", "marital_status"] == "신혼"
    assert "marital_status" in u.loc["newlywed", "from_text"]


def test_parents_home_is_rent_free_even_if_text_says_jeonse():
    seeker = _users().loc["seeker"]
    assert (seeker.tenure_type, seeker.is_householder) == ("무상거주", "세대원")
    assert seeker.household_size == 3


def test_ambiguous_tenure_is_not_read_from_text():
    assert "tenure_type" not in _users().loc["ambiguous", "from_text"]


def test_region_and_nickname():
    sp = _users().loc["single_parent"]
    assert (sp.sido, sp.sigungu) == ("경남", "창원시")
    assert sp.nickname == "지원"  # 성을 뺀 이름만
    assert sp.children_count == 1 and sp.household_size == 2


def test_many_draws_pass_check_and_are_reproducible():
    a = _users(n_copies=300, seed=7)
    assert check(a) == []
    pd.testing.assert_frame_equal(a, _users(n_copies=300, seed=7))


@pytest.mark.parametrize("change, message", [
    ({"marital_status": "미혼"}, "혼인신고일"),
    ({"gender": "남", "pregnant": "Y", "due_month": "2027-03"}, "임신"),
    ({"youngest_child_age": pd.NA}, "막내 나이"),
    ({"tenure_type": "자가", "is_homeless": "Y"}, "자가"),
    ({"employment_status": "구직", "employment_type": "맞벌이"}, "맞벌이"),
])
def test_check_catches_contradictions(change, message):
    u = _users().reset_index(drop=True)
    i = u.index[u["source_uuid"] == "mom"][0]
    for col, value in change.items():
        u[col] = u[col].astype(object)
        u.at[i, col] = value
    assert any(message in p for p in check(u))


def test_unknown_family_type_is_an_error():
    with pytest.raises(ValueError, match="family_type"):
        synthesize(pd.DataFrame([_row(family_type="처음 보는 가구")]), seed=0, holdout=0)


def test_stage2_matches_team_sheet():
    u = _users()
    s1 = features.stage1(u)
    x = features.stage2(s1, features.fit_scale(s1))
    assert list(x.columns[1:]) == features.COLUMNS and len(features.COLUMNS) == 32
    v = x[features.COLUMNS].to_numpy()
    assert np.nanmin(v) >= 0 and np.nanmax(v) <= 1
    # 원핫 묶음은 한 사람에 하나만 1
    for prefix in ("혼인_", "취업_", "점유_", "sido_"):
        cols = [c for c in features.COLUMNS if c.startswith(prefix)]
        assert (x[cols].sum(axis=1) == 1).all()
    mom = x[u["source_uuid"].to_numpy() == "mom"].iloc[0]
    assert mom["sido_서울"] == 1 and mom["gender_여"] == 1


def test_stage2_leaves_unknown_fields_empty_for_new_users():
    s1 = features.stage1(_users())
    scale = features.fit_scale(s1)
    new = s1.iloc[[0]].copy()
    new[["tenure_type", "income_household"]] = None
    x = features.stage2(new, scale).iloc[0]
    assert np.isnan(x["income_s"]) and np.isnan(x["점유_전세"])
