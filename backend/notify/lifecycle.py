"""판정 결과(build_judge 응답)의 타임라인을 생애주기 알림과 리포트 메일로 바꾼다.

새 판정은 하지 않는다. 엔진·플래너가 낸 opens·todo·dated만 문장으로 옮긴다.
"""

from datetime import date
from hashlib import sha256
from html import escape

STEP_LABEL = {"newlywed": "신혼이 되면", "child": "아이가 생기면", "multi_child": "둘째가 생기면"}
STEP_NAME = {"newlywed": "신혼", "child": "자녀", "multi_child": "다자녀"}
TODO_LABEL = {"marriage_registration": "혼인신고", "move_in": "전입신고", "ltc_grade_apply": "장기요양등급 신청"}
RELATION = {"모": "어머니", "부": "아버지"}
DISCLAIMER = "참고용 모의 판정입니다. 실제 자격은 접수 기관 심사로 결정됩니다."


def _names(ids, names, limit=None, me=None):
    """특정 대상(한부모·장애 등) 제도는 뒤로. 카드 순서와 같은 기준이다."""
    from backend.engine.cards import _niche

    out = [names[i] for i in dict.fromkeys(ids) if names.get(i)]
    out.sort(key=lambda n: _niche(n, me or {}))
    return out[:limit] if limit else out


def _summary(items):
    return items[0] + (f" 외 {len(items) - 1}개" if len(items) > 1 else "")


def _todos(step):
    return list(dict.fromkeys(TODO_LABEL.get(t["action"], t.get("read_as") or t["action"])
                              for t in step.get("todo") or [] if t.get("status") != "met"))   # 이미 된 것은 해둘 일이 아니다


def _id(user_id, *key):
    return "n_" + sha256(repr((user_id, "lifecycle") + key).encode()).hexdigest()[:32]


def notifications(user_id, result, names, *, today, me=None):
    """타임라인 한 단계마다 알림 하나. 같은 단계·같은 제도 묶음이면 ID가 같아 다시 만들어도 하나다."""
    out = []
    timeline = result.get("timeline") or {}
    for step in timeline.get("self") or []:
        opened = _names(step.get("opens") or [], names, me=me)
        if not opened:
            continue
        todos = _todos(step)
        title = f"{STEP_LABEL.get(step['step'], step['step'])} 열려요: {_summary(opened)}"
        if todos:
            title += f" · 미리 해둘 일: {', '.join(todos)}"
        out.append(dict(id=_id(user_id, "self", step["step"], tuple(step["opens"])), kind="lifecycle", subject="self",
                        rule_id=step["opens"][0], title=title, created=today.isoformat(), read=False, step=step["step"],
                        order=len(out)))
    for step in timeline.get("parent") or []:
        opened = _names(step.get("opens") or [], names)
        if not opened:
            continue
        who = RELATION.get(step.get("relation"), "부모님")
        if step.get("year"):
            title = f"{who} {step['year']}년 만 65세: {_summary(opened)} 신청이 열려요"
            if step.get("apply_from"):
                title += f" ({step['apply_from']} 신청)"
        else:
            todos = _todos(step)
            title = f"{who}: {', '.join(todos) or _summary(opened)}을 미리 챙겨 보세요"
            if step.get("why"):
                title += f" ({step['why']})"
        item = dict(id=_id(user_id, "parent", step["step"], tuple(step["opens"])), kind="lifecycle", subject="parent",
                    rule_id=step["opens"][0], title=title, created=today.isoformat(), read=False, step=step["step"],
                    order=50 + len(out))
        if step.get("year"):
            item["due"] = str(step["year"])
        out.append(item)
    for d in timeline.get("dated") or []:
        if not d.get("date"):
            continue   # 연도만 있는 날짜(만 65세 등)는 위 단계 알림에 이미 있다
        try:
            if date.fromisoformat(d["date"]) < today:
                continue
        except ValueError:
            continue
        out.append(dict(id=_id(user_id, "dated", d["what"], d["date"]), kind="lifecycle", subject="self",
                        rule_id=d.get("rule_id") or "dated", title=f"다가오는 날짜: {d['what']} ({d['date']})",
                        created=today.isoformat(), due=d["date"], read=False, order=20 + len(out)))
    return out


def report(profile, result, names, *, today):
    """생애주기 리포트 메일. (제목, 텍스트 본문, HTML 본문)."""
    me = profile.get("self") or {}
    nick = me.get("nickname") or "회원"
    timeline = result.get("timeline") or {}
    cards = result.get("cards") or []
    now_self = [c for c in cards if c.get("subject") == "self" and c.get("verdict") in ("eligible", "needs_check")]
    eligible = [c["name"] for c in now_self if c.get("verdict") == "eligible"]
    check = [c["name"] for c in now_self if c.get("verdict") == "needs_check"]

    sections = []   # (제목, 부제, [줄])
    now_lines = [f"✓ 신청할 수 있어요: {n}" for n in eligible[:3]] + [f"· 조건을 확인해 보세요: {n}" for n in check[:5]]
    if len(check) > 5:
        now_lines.append(f"· 그 밖에 확인할 제도 {len(check) - 5}개")
    sections.append(("지금", f"{me.get('marital_status') or '현재'} 단계 · {me.get('sido') or ''} {me.get('sigungu') or ''}".strip(), now_lines or ["지금 단계에서 새로 확인할 제도가 없어요."]))
    for step in timeline.get("self") or []:
        opened = _names(step.get("opens") or [], names, 5, me=me)
        closed = _names(step.get("closes") or [], names, 3)
        lines = [f"+ 열려요: {n}" for n in opened] + [f"− 닫혀요: {n}" for n in closed]
        todos = _todos(step)
        if todos:
            lines.append(f"☐ 그 전에 해둘 일: {', '.join(todos)}")
        if lines:
            sections.append((STEP_NAME.get(step["step"], step["step"]), STEP_LABEL.get(step["step"], ""), lines))
    for step in timeline.get("parent") or []:
        opened = _names(step.get("opens") or [], names, 5)
        if not opened:
            continue
        who = RELATION.get(step.get("relation"), "부모님")
        sub = f"{step['year']}년 만 65세" + (f" · {step['apply_from']} 신청" if step.get("apply_from") else "") if step.get("year") else (step.get("why") or "")
        lines = [f"+ {n}" for n in opened]
        todos = _todos(step)
        if todos:
            lines.append(f"☐ 해둘 일: {', '.join(todos)}")
        sections.append((f"{who}", sub, lines))
    dated = [d for d in timeline.get("dated") or [] if d.get("date") or d.get("year")]
    if dated:
        sections.append(("다가오는 날짜", "놓치기 쉬운 기한", [f"{d.get('date') or str(d['year']) + '년'} · {d['what']}" for d in dated[:6]]))

    subject = f"[징검] {nick}님의 생애주기 리포트 · 다음 단계에서 열리는 제도"
    text = [f"{nick}님, 지금부터 다음 단계까지 열리는 제도를 정리했어요. ({today.isoformat()} 기준)", ""]
    for title, sub, lines in sections:
        text += [f"■ {title}" + (f" — {sub}" if sub else "")] + [f"  {l}" for l in lines] + [""]
    text.append(DISCLAIMER)

    stones = "".join(
        f'<td style="padding:0 4px;text-align:center"><div style="width:14px;height:14px;border-radius:50%;margin:0 auto 6px;'
        f'background:{"#00809a" if i == 0 else "#bfe3ea"}"></div><div style="font-size:11px;color:#52606d">{escape(t)}</div></td>'
        for i, t in enumerate(dict.fromkeys(t for t, _, _ in sections if t != "다가오는 날짜")))
    blocks = "".join(
        f'<tr><td style="padding:14px 0;border-top:1px solid #edf1f5">'
        f'<div style="font-size:15px;font-weight:700;color:{"#d9692e" if t in RELATION.values() else "#00809a"}">{escape(t)}'
        f'<span style="font-weight:400;color:#7b8794;font-size:12px;margin-left:8px">{escape(sub)}</span></div>'
        + "".join(f'<div style="font-size:14px;color:#1f2933;margin-top:6px">{escape(l)}</div>' for l in lines)
        + "</td></tr>"
        for t, sub, lines in sections)
    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(subject)}</title></head>"
        '<body style="margin:0;background:#f4f7fa;font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Noto Sans KR\',sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" style="max-width:600px;background:#fff;border-radius:16px;padding:28px" cellpadding="0" cellspacing="0">'
        '<tr><td><div style="font-size:12px;color:#00809a;font-weight:700;letter-spacing:.04em">징검다리 · 생애주기 리포트</div>'
        f'<h1 style="font-size:22px;color:#1f2933;margin:8px 0 6px">{escape(nick)}님의 다음 걸음</h1>'
        f'<p style="font-size:13px;color:#52606d;margin:0 0 18px">지금부터 다음 단계까지 열리는 제도와, 그 전에 해둘 일을 정리했어요. ({today.isoformat()} 기준)</p>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-bottom:8px"><tr>{stones}</tr></table></td></tr>'
        f"{blocks}"
        f'<tr><td style="padding-top:18px;font-size:11px;color:#9aa5b1;border-top:1px solid #edf1f5">{escape(DISCLAIMER)}<br>'
        "알림 설정에서 이메일 수신을 끄면 더 이상 보내지 않아요.</td></tr>"
        "</table></td></tr></table></body></html>")
    return subject, "\n".join(text), html
