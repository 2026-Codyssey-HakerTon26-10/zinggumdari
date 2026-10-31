"""자격 답변 입력의 API 계약. DB와 외부 API를 호출하지 않는다."""
import pytest  # 기존 프로젝트 테스트 도구를 사용한다.
from fastapi import HTTPException  # 잘못된 입력은 422여야 한다.
from backend.app.routers.profiles_db import _shape  # 실제 저장 라우터의 입력 검사다.


@pytest.mark.parametrize("answer", [None, True, False, 0, "", "false", "yes", [], {}])  # 잘못된 값이 해당함으로 바뀌는 것을 막는다.
def test_invalid_qualification_answer_is_rejected(answer):  # 미해당을 나타내는 값은 N만 허용한다.
    with pytest.raises(HTTPException) as caught:  # 서버 내부 오류가 아닌 입력 오류여야 한다.
        _shape({"self": {"qualifications": [{"qual_code": "청년", "has": answer}]}})  # 실제 요청 모양을 사용한다.
    assert caught.value.status_code == 422  # 응답 코드 계약을 보존한다.


@pytest.mark.parametrize("qualification", [{"qual_code": "청년"}, {"qual_code": "청년", "has": "Y"}, {"qual_code": "청년", "has": "N"}])  # 기존 입력과 명시적인 두 답을 지원한다.
def test_supported_qualification_answers(qualification):  # 동의·소유권 검사는 기존 라우터 흐름을 유지한다.
    _shape({"self": {"qualifications": [qualification]}})  # 정상 답을 잘못 거절하지 않아야 한다.
