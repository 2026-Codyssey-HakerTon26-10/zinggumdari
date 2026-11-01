"""시연 녹화용 미리보기 API. DB 없이 실제 엔진(조건표·판정·플래너·공고 투입 캐시 재생)을 쓴다.
가입·프리셋·프로필·알림은 메모리로 흉내 내고, 공고 투입은 data/notices 복사본에만 쓴다."""
import copy
import logging
import shutil
import sys
from datetime import date
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

logging.disable(logging.WARNING)
WORK = Path(sys.argv[1])
ROOT = Path(sys.argv[2])

from backend.data import config  # noqa: E402

if not (WORK / "notices").exists():
    shutil.copytree(ROOT / "data" / "notices", WORK / "notices")
config.NOTICES_DIR = WORK / "notices"
config.UPLOAD_RULES_DIR = WORK / "uploads"

from backend.app import main, sources  # noqa: E402
from backend.app.routers import judge as judge_router  # noqa: E402
from backend.engine.cards import build_judge  # noqa: E402
from backend.engine.stub_data import EXAMPLE_PROFILE  # noqa: E402
from backend.notify import lifecycle  # noqa: E402
from backend.search import ports as search_ports  # noqa: E402

ACCOUNT = "A-demo"
STATE = {"login": False, "profile": None}


def fresh_profile():
    p = copy.deepcopy(EXAMPLE_PROFILE)
    p["user_id"] = "U-demo"
    p.pop("derived", None)
    return p


main.app.dependency_overrides[judge_router.own_profile] = lambda: {"profile": copy.deepcopy(STATE["profile"]), "account_id": ACCOUNT}
search_ports.ports.session_user = lambda request: {"account_id": ACCOUNT, "profile_id": "U-demo"} if STATE["login"] else None

app = FastAPI()


@app.post("/_reset")
def reset():
    STATE.update(login=False, profile=None)
    shutil.rmtree(WORK / "uploads", ignore_errors=True)
    return STATE


@app.post("/auth/signup", status_code=201)
def signup(body: dict):
    STATE.update(login=True, profile=None)
    return {"account_id": ACCOUNT}


@app.get("/auth/me")
def me():
    if not STATE["login"]:
        raise HTTPException(401, "로그인이 필요합니다")
    return {"account_id": ACCOUNT, "email": "demo@zinggum.test", "user_id": "U-demo" if STATE["profile"] else None, "nickname": "지원"}


@app.post("/profiles/presets/{preset}")
def preset(preset: str):
    STATE["profile"] = fresh_profile()
    return {"user_id": "U-demo", "preset": preset}


@app.get("/profiles/U-demo")
def get_profile():
    return STATE["profile"]


@app.patch("/profiles/U-demo")
def patch(body: dict):
    for k, v in (body.get("self") or {}).items():
        STATE["profile"]["self"][k] = v
    return STATE["profile"]


def _judge():
    rules = sources.load_rules(owner=ACCOUNT)
    return rules, build_judge(copy.deepcopy(STATE["profile"]), rules, date.today())


@app.get("/notifications")
def notifications():
    rules, result = _judge()
    items = lifecycle.notifications("U-demo", result, {r["id"]: r.get("name") for r in rules}, today=date.today(), me=STATE["profile"]["self"])
    return sorted(items, key=lambda n: n.get("order", 0))


@app.get("/notify/report", response_class=HTMLResponse)
def report():
    rules, result = _judge()
    return lifecycle.report(STATE["profile"], result, {r["id"]: r.get("name") for r in rules}, today=date.today())[2]


app.mount("/", main.app)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8031, log_level="warning")
