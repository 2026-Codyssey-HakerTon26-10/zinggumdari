"""부모님 저장 칸과 질문의 계약을 합성 조건표로 검사해요. 정답지는 읽지 않아요."""  # 실제 개인정보나 평가 정답을 쓰지 않아요.
from datetime import date  # 판정 날짜를 고정해 경계가 흔들리지 않게 해요.
import pytest  # 여러 조건을 같은 계약으로 반복 검사해요.
from backend.db.profiles import PARENT, _check_fields  # 실제 저장 허용 목록과 검사를 확인해요.
from backend.engine import judge  # 사용자가 받는 조건 등급을 검사해요.
from backend.engine.ask import _question, choose_ask  # 질문 생성의 방어도 직접 검사해요.
from backend.engine.cards import build_judge  # 화면에 전달하는 카드와 질문을 함께 검사해요.
from backend.engine.fields import PARENT_PROFILE_FIELDS  # 저장과 엔진이 공유하는 목록을 가져와요.
TODAY = date(2026, 11, 1)  # 외부 시계나 서버를 사용하지 않아요.
def condition(field, value=1, op="<=", **extra):  # 테스트용 조건 한 줄을 만들어요.
    return {"field": field, "op": op, "value": value, "status": "reviewed", "evidence": ["test:l1"], **extra}  # 사람이 검토한 가상 조건만 사용해요.
def rule(cond, subject="parent", **extra):  # 테스트용 제도 한 개를 만들어요.
    return {"id": "test:contract", "name": "가상 계약 검사", "subject": subject, "source": "manual", "review": {"status": "reviewed"}, "updated": "2026-11-01", "conditions": [cond], **extra}  # 실제 제도 조건표를 열지 않아요.
def profile(parent=None, own=None):  # 본인과 부모님의 서로 다른 값을 가진 가상 프로필이에요.
    return {"user_id": "test-only", "consents": {"sensitive": True, "parent": True}, "self": own or {"household_size": 1, "income_household": 100, "tenure_type": "자가"}, "parents": [{"relation": "모", "birth_date": "1960-01-01", **(parent or {})}]}  # 본인 정보가 부모 조건으로 새지 않는지도 검사해요.
@pytest.mark.parametrize("field", ["household_size", "income_self", "income_household", "income_band_median", "income_band_urban", "house_price", "tenure_type", "marital_status", "qual_code"])  # 부모님이 수집하지 않는 여러 칸을 확인해요.
def test_parent_unsupported_condition_stays_check_without_question(field):  # 저장 불가 질문을 없애되 자격을 확정하면 안 돼요.
    item = rule(condition(field)); result = build_judge(profile(), [item], TODAY, focus=item["id"])  # 카드를 직접 열어도 같은 방어를 거쳐야 해요.
    card = result["cards"][0]; row = card["conditions"][0]  # 실제 화면 응답의 조건 줄을 확인해요.
    assert card["verdict"] == "needs_check" and row["grade"] == "확인 필요" and row["ok"] is None  # 미수집 칸으로 통과나 탈락을 단정하지 않아요.
    assert card["blocking_fields"] == [] and result["ask"] is None  # 저장할 수 없는 칸은 질문에 올라오지 않아야 해요.
@pytest.mark.parametrize("parent", [{}, {"household_size": 1, "income_household": 100}])  # 잘못된 옛 입력이 메모리에 있어도 부모 소득을 확정하지 않아요.
def test_parent_income_percent_does_not_ask_derived_household_size(parent):  # 소득 계산이 요구하는 재료 칸도 부모 질문으로 새면 안 돼요.
    item = rule(condition("income_band_median", 100, income_basis="median_pct")); result = build_judge(profile(parent), [item], TODAY, focus=item["id"])  # 가구 소득 비율 조건을 재현해요.
    assert result["cards"][0]["conditions"][0]["grade"] == "확인 필요" and result["ask"] is None  # 가구원 수나 월소득을 추가로 묻지 않아요.
def test_parent_recognized_income_keeps_asset_conversion_note():  # 기초연금의 재산 환산 필요 안내는 유지해야 해요.
    item = rule(condition("income_recognized", 200, income_basis="recognized")); card = judge(profile(), [item], TODAY)[item["id"]]  # 소득인정액 조건을 가상으로 만들어요.
    assert card["conditions"][0]["grade"] == "확인 필요" and "재산 환산" in card["conditions"][0]["why"]  # 부모 소득을 묻는 대신 기존 이유를 알려줘요.
@pytest.mark.parametrize("field", ["household_size", "income_household", "tenure_type", "qual_code"])  # 기존에 만들어진 잘못된 카드도 방어해요.
def test_question_selector_defends_unsupported_parent_fields(field):  # 조건 판정 외에도 질문 선택 자체가 안전해야 해요.
    item = rule(condition(field)); card = {"rule_id": item["id"], "subject": "parent", "verdict": "needs_check", "blocking_fields": [field]}  # 예전 서버가 만든 질문 후보를 흉내 내요.
    assert _question("parent", field, item, profile()) is None  # 개별 질문 생성이 저장 불가 칸을 거부해야 해요.
    assert choose_ask([card], {item["id"]: item}, profile(), focus=item["id"]) is None  # 사용자가 카드를 열어도 거부해야 해요.
@pytest.mark.parametrize("cond,parent,field", [(condition("age", 65, ">="), {"birth_date": None}, "birth_date"), (condition("care_wanted", "Y", "=="), {}, "care_wanted"), (condition("sido", "서울", "=="), {}, "sido")])  # 정상 부모 질문은 계속 제공해야 해요.
def test_supported_parent_questions_remain_available(cond, parent, field):  # 생년월일·돌봄·지역 질문이 사라지는 회귀를 막아요.
    item = rule(cond); result = build_judge(profile(parent), [item], TODAY, focus=item["id"])  # 비어 있는 정상 칸을 대상으로 판정해요.
    assert result["ask"]["subject"] == "parent" and result["ask"]["field"] == field  # 질문의 대상과 저장 칸을 정확히 유지해요.
def test_parent_age_and_common_apply_date_still_evaluate():  # 저장하지 않는 계산 조건도 정상 비교해야 해요.
    item = rule(condition("age", 65, ">=")); item["conditions"].append(condition("apply_date", "2026-12-31"))  # 만 66세와 접수 마감일을 함께 확인해요.
    assert judge(profile(), [item], TODAY)[item["id"]]["verdict"] == "eligible"  # 부모님 지원 필드와 공통 날짜가 모두 통과해야 해요.
def test_parent_region_still_asks_own_region():  # 별도 지역 메타데이터로 생성하는 질문도 유지해야 해요.
    item = rule(condition("age", 65, ">="), region={"sido": "서울"}); result = build_judge(profile(), [item], TODAY, focus=item["id"])  # 본인과 별개인 부모님 지역을 비워 둬요.
    assert result["ask"]["subject"] == "parent" and result["ask"]["field"] == "sido"  # 부모님 지역을 본인 지역으로 대신 채우지 않아요.
def test_self_household_size_remains_answerable_and_storable():  # 본인의 정상 질문과 저장 경로는 바뀌면 안 돼요.
    item = rule(condition("household_size", 2), subject="self"); person = profile(own={"nickname": "가상"}); result = build_judge(person, [item], TODAY, focus=item["id"])  # 본인 가구원 수만 비운 프로필을 만들어요.
    assert result["ask"]["subject"] == "self" and result["ask"]["field"] == "household_size"  # 본인에게는 가구원 수를 물을 수 있어야 해요.
    person["self"]["household_size"] = 1; _check_fields(person)  # 답변이 실제 저장 허용 목록을 통과해야 해요.
def test_parent_storage_contract_is_unchanged():  # 이번 수정으로 부모님 표에 칸을 추가하지 않았음을 확인해요.
    assert PARENT == PARENT_PROFILE_FIELDS and "household_size" not in PARENT  # 저장과 질문이 같은 기존 칸 목록을 사용해야 해요.
    person = profile(parent={"household_size": 1})  # 부모님에 저장할 수 없는 값을 일부러 넣어요.
    with pytest.raises(ValueError, match="household_size"):  # API의 기존 잘못된 칸 거절은 유지해야 해요.
        _check_fields(person)  # 허용 목록 밖 값을 DB에 넣지 못하도록 확인해요.
