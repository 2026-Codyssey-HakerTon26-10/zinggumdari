"""규칙 엔진 결과로만 알림을 생성한다. 날짜 계산은 플래너의 책임이다."""

from datetime import date
from hashlib import sha256


def notification(user_id, rule, result, *, today, event=None):
    if result.get("superseded_by") or result.get("no_subject"):
        return None
    allowed = {"eligible", "needs_check", "opens_later"} if event else {"eligible", "needs_check"}
    if result.get("verdict") not in allowed:
        return None
    deadline = result.get("deadline")
    if deadline and deadline not in ("상시", "미정") and date.fromisoformat(deadline) < today:
        return None
    kind = "new_rule"
    extra = {}
    eligible = (result["verdict"] == "eligible"
                and rule.get("review", {}).get("status") == "reviewed")
    title = f"새 공고: {rule['name']} " + ("신청할 수 있어요" if eligible else "조건을 확인해 보세요")
    if event is not None:
        kind = event["kind"]
        if kind not in {"d_day", "closing", "apply_open"}:
            raise ValueError("지원하지 않는 날짜 알림")
        # 근거가 실제 검증된 조건 또는 검수한 신청 기간에 속해야 한다.
        trusted = {line for c in rule.get("conditions", [])
                   if c.get("status") in {"reviewed", "auto_verified"}
                   for line in c.get("evidence", [])}
        if rule.get("review", {}).get("status") == "reviewed":
            trusted.update((rule.get("apply_window") or {}).get("evidence", []))
        evidence = set(event.get("evidence", []))
        if not evidence or not evidence <= trusted:
            return None
        due = str(event["due"])
        # due는 발송일이다. 미리 알리는 날짜도 플래너가 계산해 전달한다.
        # 알림 창은 상수로 만들지 않고 플래너의 notify_from부터 due까지로 받는다.
        due_date = date(int(due), 1, 1) if len(due) == 4 else date.fromisoformat(due)
        start = date.fromisoformat(event.get("notify_from", due_date.isoformat()))
        active = due_date.year == today.year if len(due) == 4 else start <= today <= due_date
        if not active:
            return None
        title = event["title"]
        if not eligible and "신청할 수 있어요" in title:
            return None
        extra = {key: event[key] for key in ("due", "from", "evidence") if key in event}
    # 재판정 버튼을 여러 번 눌러도 같은 공고·버전·날짜 알림은 하나다.
    key = (user_id, rule["id"], rule.get("updated"), kind, extra.get("due"), title)
    identifier = sha256(repr(key).encode()).hexdigest()[:32]
    return dict(id="n_" + identifier, kind=kind, subject=rule["subject"],
                rule_id=rule["id"], title=title, created=today.isoformat(), read=False, **extra)


def explore_notification(user_id, item, similar, *, today):
    if item.get("my_verdict") != "needs_check" or item["prevalence"] < .3 or similar["neighbors"] < 1:
        return None
    key = (user_id, item["rule_id"], "explore", today.isoformat())
    return dict(id="n_" + sha256(repr(key).encode()).hexdigest()[:32], kind="explore",
                subject=item["subject"], rule_id=item["rule_id"], read=False,
                created=today.isoformat(), title=f"비슷한 가구에서 {item['prevalence']:.0%}가 해당돼요. 조건을 확인해 보세요",
                prevalence=item["prevalence"], neighbors=similar["neighbors"],
                blocking_fields=item["blocking_fields"], basis="가상 인구(가정 분포)",
                label=similar["label"], assignment=similar["assignment"])


def rebuild(profiles, rules, judge, save, *, today, events=None, rule_ids=None, account_id=None):
    """save(user_id, 알림)는 ID별 upsert. 프로필·날짜를 LLM에 보내지 않는다."""
    # DB 어댑터가 소유 관계를 내부 account_id로 붙인다. 누락은 전체 사용자로 해석하지 않는다.
    selected_profiles = [p for p in profiles if not account_id or p.get("account_id") == account_id]
    visible_rules = [r for r in rules if r.get("source") != "upload" or
                     (account_id and (rule_ids is None or r["id"] in rule_ids))]
    count = 0
    for profile in selected_profiles:
        results = judge(profile, visible_rules, today=today)
        for rule in visible_rules:
            if rule_ids is not None and rule["id"] not in rule_ids:
                continue
            result = results[rule["id"]]
            candidates = [notification(profile["user_id"], rule, result, today=today)]
            if events:
                candidates += [notification(profile["user_id"], rule, result, today=today, event=e)
                               for e in events(profile, rule, result, today)]
            for item in candidates:
                if item:
                    save(profile["user_id"], item)
                    count += 1
    return {"processed_profiles": len(selected_profiles), "notifications": count}
