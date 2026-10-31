"""main.py 소유자가 인증·DB 어댑터를 연결하는 라우터 팩토리.

store: list(user_id), mark_read(user_id, id), rebuild(today), test_email(user_id).
require_user는 세션 소유 프로필 ID, require_admin은 관리 권한을 검증해야 한다.
운영 코드에서 인메모리 저장소나 클라이언트 user_id를 인증 대용으로 쓰지 않는다.
"""

from datetime import date
import smtplib

from fastapi import APIRouter, Depends, HTTPException
from backend.notify.email import DeliveryRecordError


def create_router(store, require_user, require_admin):
    router = APIRouter()

    @router.get("/notifications")
    def listing(user_id: str = Depends(require_user)):
        return store.list(user_id)

    @router.patch("/notifications/{notification_id}/read")
    def read(notification_id: str, user_id: str = Depends(require_user)):
        item = store.mark_read(user_id, notification_id)
        if item is None:
            raise HTTPException(404, "알림을 찾을 수 없습니다")
        return item

    @router.post("/trigger/rebuild", dependencies=[Depends(require_admin)])
    def rebuild(today: date | None = None):
        return store.rebuild(today or date.today())

    @router.post("/notify/test-email")
    def test_email(user_id: str = Depends(require_user)):
        try:
            return store.test_email(user_id)
        except (smtplib.SMTPException, OSError, DeliveryRecordError):
            raise HTTPException(503, "메일 처리 상태를 확인해 주세요") from None

    return router
