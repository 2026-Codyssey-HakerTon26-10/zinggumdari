"""규칙 엔진 결과로만 알림을 생성한다. 날짜 계산은 플래너의 책임이다."""

from datetime import date
from hashlib import sha256


def notification(user_id, rule, result, *, today, event=None):
    if result.get("verdict") not in {"eligible", "needs_check"}:
        return None
    deadline = result.get("deadline")
    if deadline and date.fromisoformat(deadline) < today:
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
        # 연도 단위 부모 알림도 재현한다. 과거 날짜의 알림은 생성하지 않는다.
        due_date = date(int(due), 1, 1) if len(due) == 4 else date.fromisoformat(due)
        if due_date > today or (len(due) == 4 and due_date.year != today.year) or (len(due) != 4 and due_date != today):
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


def rebuild(profiles, rules, judge, save, *, today, events=None):
    """save(user_id, 알림)는 ID별 upsert. 프로필·날짜를 LLM에 보내지 않는다."""
    count = 0
    for profile in profiles:
        results = judge(profile, rules)
        for rule in rules:
            result = results[rule["id"]]
            candidates = [notification(profile["user_id"], rule, result, today=today)]
            if events:
                candidates += [notification(profile["user_id"], rule, result, today=today, event=e)
                               for e in events(profile, rule, result, today)]
            for item in candidates:
                if item:
                    save(profile["user_id"], item)
                    count += 1
    return {"processed_profiles": len(profiles), "notifications": count}
