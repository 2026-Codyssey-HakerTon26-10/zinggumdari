"""첫 덤프로 확인할 것 두 가지를 출력한다. 팀에 공유하는 용도.

    uv run --project backend python -m backend.data.report

1. LH 상세의 PDF 첨부 필드 이름(알려진 이름은 dsAhflInfo.AHFL_URL, 미확인)
2. 행안부 혜택 「신청기한」의 실제 형식 분포
"""

from __future__ import annotations

from collections import Counter

from backend.data.deadline import parse_deadline
from backend.data.load import iter_details, iter_items
from backend.notices.lh import find_attachments


def lh_attachment_fields() -> list[str]:
    where, kinds, samples = Counter(), Counter(), {}
    n = 0
    for _, detail in iter_details("lh_detail"):
        n += 1
        for att in find_attachments(detail):
            spot = f"{att['block']}.{att['url_key']}"
            where[spot] += 1
            kinds[(spot, att["kind"])] += 1
            samples.setdefault(spot, att)
    if not n:
        return ["LH 상세 덤프 없음 (dump --source lh 먼저)"]
    lines = [f"LH 상세 {n}건에서 URL을 가진 필드:"]
    for spot, count in where.most_common():
        s = samples[spot]
        by_kind = ", ".join(f"{k} {c}" for (sp, k), c in kinds.items() if sp == spot)
        lines.append(f"  {spot}: {count}회 ({by_kind}), 같은 줄의 키 {s['row_keys']}, 예: {s['name']}")
    return lines


def gov24_deadline_formats(limit: int = 15) -> list[str]:
    texts = Counter()
    types = Counter()
    for item in iter_items("gov24_serviceList"):
        raw = (item.get("신청기한") or "").strip()
        texts[raw] += 1
        types[parse_deadline(raw)["type"]] += 1
    if not texts:
        return ["행안부 혜택 목록 덤프 없음 (dump --source gov24 먼저)"]
    lines = [f"행안부 혜택 「신청기한」 {sum(texts.values())}건, 분류 {dict(types)}", "  자주 나오는 원문:"]
    lines += [f"    {c:5d}  {t[:60]!r}" for t, c in texts.most_common(limit)]
    return lines


def main() -> None:
    for line in lh_attachment_fields() + [""] + gov24_deadline_formats():
        print(line)


if __name__ == "__main__":
    main()
