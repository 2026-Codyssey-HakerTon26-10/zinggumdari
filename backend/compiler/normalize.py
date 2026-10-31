"""한국어 수·날짜 정규화(SPEC §9.3 값·비교어·단위·신호어·경계 쌍 검사가 쓴다).

find_quantities는 단위가 붙은 수만 찾는다. 금액은 만원, %는 숫자, 나이는 세, 기간은 원문 단위(년·개월),
날짜는 "YYYY-MM-DD"(달까지면 "YYYY-MM")다. 비교어는 그 수 바로 뒤(조사·띄어쓰기, 비교어 없는 괄호 하나 허용)나
범위 위치에서 정한다. "…초과하는 자는 신청할 수 없다"처럼 비교어 바로 뒤가 제외 문장이면 비교어를 뒤집는다.
맨 숫자, 목록 번호("1.", "2)"), 조항("제41조"), 전화번호, 달 없는 연도("2026년 기준")는 내지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date


@dataclass(frozen=True)
class Quantity:
    kind: str                # money(만원) | percent | age(세) | months | years | count | date
    value: float | str       # 수는 float, 날짜는 "YYYY-MM-DD" 또는 "YYYY-MM"
    start: int               # 수+단위의 글자 위치(원문 기준)
    end: int
    comparator: str | None   # "<=" "<" ">=" ">" 또는 None
    raw: str
    range_id: int | None = None  # 범위("N 이상 M 이하", "N~M")의 두 끝을 잇는다
    inverted: bool = False       # 제외 문장이라 원문 비교어를 뒤집었다


_NUM = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
# 숫자 중간이나 "제N조" 꼴에서 시작하지 않는다
_LB = r"(?<!\d)(?<!\d[.,])(?<!제)(?<!제 )"
_MAG = "억천백십만"
_SMALL = {"십": 10, "백": 100, "천": 1000}
_BIG = {"만": 10**4, "억": 10**8}

_PHONE_RE = re.compile(r"(?<![\d-])(?:0\d{1,2}-\d{3,4}-\d{4}|1\d{3}-\d{4})(?![\d-])")
_DATE_KO_RE = re.compile(r"(?<!\d)(\d{4})\s*년\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?")
_DATE_NUM_RE = re.compile(r"(?<![\d.\-/])(\d{4})\s*([.\-/])\s*(\d{1,2})\s*\2\s*(\d{1,2})(?!\d)(?:\s*\.)?")
_MONTH_NUM_RE = re.compile(r"(?<![\d.\-/])(\d{4})\s*\.\s*(\d{1,2})(?!\d)(?:\s*\.)?(?!\s*\d)")
_FRAC_RE = re.compile(rf"{_LB}({_NUM})\s*분의\s*({_NUM})")
_YEAR_MONTH_RE = re.compile(rf"{_LB}({_NUM})\s*년\s*({_NUM})\s*개월")
_MONEY_RE = re.compile(rf"{_LB}(?=[\d{_MAG}])(?:{_NUM}\s*)?(?:[{_MAG}]\s*(?:{_NUM}\s*)?)*원")
_PCT_RE = re.compile(rf"{_LB}({_NUM})\s*(?:%|％|퍼센트|프로(?!그램|젝트))")
_MONTHS_RE = re.compile(rf"{_LB}({_NUM})\s*개월")
_YEARS_RE = re.compile(rf"{_LB}({_NUM})\s*년")
_AGE_RE = re.compile(rf"{_LB}({_NUM})\s*세(?![대금율])")
_COUNT_RE = re.compile(rf"{_LB}({_NUM})\s*(?:명|회(?!계)|가구|자녀|인)")

# 비교어. 앞의 것이 먼저다("초과하지 않는"이 "초과"보다 먼저)
_CMP_GAP = r"(?:\s*\.)?(?:\s*\([월화수목금토일]\))?(?:\s*\d{1,2}:\d{2})?\s*(?:(?:을|를|이|가|은|는|에|의|로|으로)\s*)?"
_CMP_WORDS = [
    (r"초과\s*하지\s*(?:않|아니)", "<="), (r"넘지\s*(?:않|아니)", "<="),
    (r"이하", "<="), (r"이내", "<="), (r"전\s*까지", "<"), (r"까지", "<="),
    (r"미만", "<"), (r"이전", "<"),
    (r"이상", ">="), (r"부터", ">="), (r"이후", ">="),
    (r"초과", ">"), (r"넘는", ">"), (r"넘을", ">"),
    (r"지\s*나\s*지\s*(?:않|아니)", "<"), (r"지\s*[나난]|경과", ">="),  # "가입 후 12개월이 지난"
]
_CMP_RES = [(re.compile(_CMP_GAP + f"(?:{p})"), op) for p, op in _CMP_WORDS]
_ANY_CMP_RE = re.compile("|".join(p for p, _ in _CMP_WORDS))
# 비교어 없이 건너뛰는 괄호: "120%(맞벌이 130%) 이하", "2명(태아 포함) 이상"
_PAREN_RE = re.compile(r"(?:\s*\.)?\s*[(（]([^()（）]*)[)）]")
# 제외·불가 말. 비교어 바로 뒤("…초과하는 자는 신청할 수 없다", "…미만인 자는 제외")면 비교어를 뒤집는다
_NEG = r"제외|신청할\s*수\s*없|신청\s*불가|지원\s*불가|불가|지원하지\s*않|해당하지\s*않|선정하지\s*않"
_NEG_RE = re.compile(_NEG)
_NOT_RE = re.compile(_NEG + r"|아닌|아니|않|없")
_NEG_AFTER_RE = re.compile(r"\s*(?:하는|되는|하|이|인|한|된|일)?\s*(?:자|경우|사람|분|세대|가구|때)?\s*(?:는|은|도|에는)?\s*"
                           r"(?:(?:신청|지원|선정)?\s*대상에서\s*)?(?:" + _NEG + ")")
_INVERT = {"<=": ">", "<": ">=", ">=": "<", ">": "<="}
# "N 이상 M 이하"에서 앞 비교어와 뒤 수 사이에 올 수 있는 것
_PAIR_GAP_RE = re.compile(r"\s*(?:,|이고|이며|이면서|부터|[~∼〜～])?\s*(?:만\s*)?")
_TILDE_RE = re.compile(r"([~∼〜～])\s*(?:만\s*)?$")
_TILDE_GAP_RE = re.compile(r"(?:\s*\.)?(?:\s*\([월화수목금토일]\))?(?:\s*\d{1,2}:\d{2})?\s*")  # "1.(일) 10:00 ~"
_BARE_LEFT_RE = re.compile(rf"{_LB}({_NUM}(?:\s*[{_MAG}])*)\s*$")

_SEP_RE = re.compile(
    r"및|또는|[,，;；()（）\[\]［］·ㆍ・/○●◦•▪■□◆◇▶▷※☞①-⑳]|(?<!\S)-(?=\s)"
)
# 이어 주는 끝("이내이고 ", "거주하며 ", "지나고 ")도 뒤에 수가 있으면 절을 나눈다
_CONJ_RE = re.compile(r"(?<=[이하되있않없나넘았었])(?:고|며|으며|면서|으면서|거나)(?=\s)")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _korean_number(s: str) -> float:
    """"7천 5백만" → 75000000, "3억 4,500만" → 345000000. 원 단위."""
    total = section = 0.0
    cur = None
    for tok in re.findall(rf"{_NUM}|[{_MAG}]", s):
        if tok in _SMALL:
            section += (1 if cur is None else cur) * _SMALL[tok]
            cur = None
        elif tok in _BIG:
            section += cur or 0
            total += (section or 1) * _BIG[tok]
            section, cur = 0.0, None
        else:
            cur = _num(tok)
    return total + section + (cur or 0)


def _ymd(y: str, mo: str, d: str | None = None) -> str | None:
    y_, mo_ = int(y), int(mo)
    if not (1900 <= y_ <= 2100 and 1 <= mo_ <= 12):
        return None
    if d is None:
        return f"{y_:04d}-{mo_:02d}"
    try:
        return date(y_, mo_, int(d)).isoformat()
    except ValueError:
        return None


def _money(m: re.Match) -> float | None:
    s = m.start()
    if m.group()[0] in _MAG and s > 0 and "가" <= m.string[s - 1] <= "힣":
        return None  # "인천원"의 "천원" 같은 낱말 속
    return round(_korean_number(m.group()) / 10000, 6)


def _years(m: re.Match) -> float | None:
    v = _num(m.group(1))
    return None if v >= 1000 else v  # "2026년 기준" 같은 달력 연도


def _year_months(m: re.Match) -> float | None:
    y = _num(m.group(1))
    return None if y >= 1000 else y * 12 + _num(m.group(2))


# (kind, 정규식, 값 함수). 앞의 것이 먼저 자리를 차지한다
_PATTERNS = [
    ("date", _DATE_KO_RE, lambda m: _ymd(*m.group(1, 2, 3))),
    ("date", _DATE_NUM_RE, lambda m: _ymd(*m.group(1, 3, 4))),
    ("date", _MONTH_NUM_RE, lambda m: _ymd(*m.group(1, 2))),
    ("percent", _FRAC_RE, lambda m: round(_num(m.group(2)) * 100 / _num(m.group(1)), 6) if _num(m.group(1)) else None),
    ("months", _YEAR_MONTH_RE, _year_months),
    ("money", _MONEY_RE, _money),
    ("percent", _PCT_RE, lambda m: _num(m.group(1))),
    ("months", _MONTHS_RE, lambda m: _num(m.group(1))),
    ("years", _YEARS_RE, _years),
    ("age", _AGE_RE, lambda m: _num(m.group(1))),
    ("count", _COUNT_RE, lambda m: _num(m.group(1))),
]


def _comparator_after(text: str, end: int) -> tuple[str | None, int]:
    """수 바로 뒤의 비교어와 그 끝 위치. 비교어가 없는 괄호 하나는 건너뛴다."""
    m = _PAREN_RE.match(text, end)
    for pos in [end] + ([m.end()] if m and not _ANY_CMP_RE.search(m[1]) else []):
        for rx, op in _CMP_RES:
            n = rx.match(text, pos)
            if n:
                return op, n.end()
    return None, end


def _bare_left(text: str, tilde: int, right: Quantity) -> Quantity | None:
    """"19~34세"의 19처럼 단위가 없는 범위 앞쪽 수를 뒤쪽 단위로 읽는다."""
    m = _BARE_LEFT_RE.search(text, 0, tilde)
    if not m or right.kind == "date":
        return None
    raw = m.group(1)
    has_mag = any(c in _MAG for c in raw)
    if right.kind == "money":
        if not has_mag and any(c in _MAG for c in right.raw):
            return None  # "5~7천만원"은 5가 5천만인지 알 수 없다
        value = round(_korean_number(raw) / 10000, 6)
    elif has_mag:
        return None
    else:
        value = _num(raw)
    return Quantity(right.kind, value, m.start(1), m.start(1) + len(raw), ">=", raw)


def find_quantities(text: str) -> list[Quantity]:
    """단위가 붙은 수를 원문 순서로 찾는다. 범위의 두 끝은 같은 range_id를 갖는다."""
    taken = [m.span() for m in _PHONE_RE.finditer(text)]
    found: list[tuple[str, float | str, int, int]] = []
    for kind, rx, conv in _PATTERNS:
        for m in rx.finditer(text):
            s, e = m.span()
            if any(s < te and ts < e for ts, te in taken):
                continue
            value = conv(m)
            if value is None:
                continue
            taken.append((s, e))
            found.append((kind, value, s, e))
    found.sort(key=lambda f: f[2])

    qs: list[Quantity] = []
    cmp_end: list[int] = []
    for kind, value, s, e in found:
        op, ce = _comparator_after(text, e)
        inv = op is not None and bool(_NEG_AFTER_RE.match(text, ce))
        qs.append(Quantity(kind, value, s, e, _INVERT[op] if inv else op, text[s:e], inverted=inv))
        cmp_end.append(ce)

    rid = 0
    # "N~M": 앞은 >=, 뒤는 (비교어가 없으면) <=
    n = len(qs)
    for i in range(n):
        right = qs[i]
        m = _TILDE_RE.search(text, 0, right.start)
        if not m or right.range_id is not None:
            continue
        tilde = m.start(1)
        j = next((j for j, q in enumerate(qs) if q.end <= tilde and _TILDE_GAP_RE.fullmatch(text, q.end, tilde)), None)
        if j is None:
            left = _bare_left(text, tilde, right)
            if left is None or left.value > right.value:
                continue
            qs.append(left)
            j = len(qs) - 1
        elif qs[j].kind != right.kind or qs[j].range_id is not None or qs[j].value > right.value:
            continue  # 아래 끝이 위 끝보다 크면 범위가 아니다
        rid += 1
        qs[j] = replace(qs[j], comparator=">=", range_id=rid)
        qs[i] = replace(right, comparator=right.comparator or "<=", range_id=rid)
    # "N 이상 M 이하": 같은 종류의 아래 경계 바로 뒤에 위 경계(앞의 n개는 원문 순서 그대로다)
    for i in range(n - 1):
        a, b = qs[i], qs[i + 1]
        if (a.range_id is None and b.range_id is None and a.kind == b.kind and a.value <= b.value
                and a.comparator in (">=", ">") and b.comparator in ("<=", "<")
                and _PAIR_GAP_RE.fullmatch(text, cmp_end[i], b.start)):
            rid += 1
            qs[i], qs[i + 1] = replace(a, range_id=rid), replace(b, range_id=rid)
    return sorted(qs, key=lambda q: q.start)


def clause_spans(text: str) -> list[tuple[int, int]]:
    """쉼표·괄호·"및"·"또는"·가운뎃점·빗금·줄 안 항목 기호로 나눈 절의 (시작, 끝). 수 안에서는 자르지 않는다.
    "이고·하며·지나고" 같은 이어 주는 끝은 뒤에 수가 더 있을 때만 나눈다."""
    qs = find_quantities(text)
    keep = [(q.start, q.end) for q in qs]
    cuts = []
    for m in _SEP_RE.finditer(text):
        s, e = m.span()
        if any(ks < e and s < ke for ks, ke in keep):
            continue
        if text[s] in ",/" and 0 < s < len(text) - 1 and text[s - 1].isdigit() and text[e].isdigit():
            continue  # 1,000 같은 맨 숫자
        cuts.append((s, e))
    cuts += [m.span() for m in _CONJ_RE.finditer(text) if any(q.start >= m.end() for q in qs)]
    cuts.sort()
    spans, prev = [], 0
    for s, e in cuts + [(len(text), len(text))]:
        seg = text[prev:s]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            spans.append((prev + lead, prev + len(seg.rstrip())))
        prev = e
    return spans


def _paren_groups(text: str) -> list[tuple[int, int]]:
    """맨 바깥 둥근 괄호의 (여는 자리, 닫는 자리 + 1)."""
    out, stack = [], []
    for i, ch in enumerate(text):
        if ch in "(（":
            stack.append(i)
        elif ch in ")）" and stack:
            s = stack.pop()
            if not stack:
                out.append((s, i + 1))
    return out


def _clause(text: str, pos: int) -> tuple[str, int, int] | None:
    """(본 글, 절 시작, 절 끝). 수가 든 괄호 밖의 자리면 괄호를 투명하게 본다:
    수가 없는 괄호("(태아 포함)", "(부부합산)")는 절 안에 두고, 수가 든 괄호("(맞벌이 7천만원 이하)")는 지우고 앞뒤를 잇는다."""
    qs = find_quantities(text)
    groups = [(s, e, any(s < q.start < e for q in qs)) for s, e in _paren_groups(text)]
    view = text
    if not any(s < pos < e and has_q for s, e, has_q in groups):
        chars = list(text)
        for s, e, has_q in groups:
            for i in (range(s, e) if has_q else (s, e - 1)):
                chars[i] = " "
        view = "".join(chars)
    return next(((view, s, e) for s, e in clause_spans(view) if s <= pos < e), None)


def clause_at(text: str, pos: int) -> str:
    """pos가 든 절의 텍스트(빈칸은 하나로). 구분자 위면 빈 문자열. 괄호는 _clause처럼 본다."""
    c = _clause(text, pos)
    return " ".join(c[0][c[1]:c[2]].split()) if c else ""


def lead_in(text: str, pos: int) -> str:
    """pos의 수 앞의 말: 앞 수(그 수가 든 괄호면 괄호 끝) 뒤부터 pos까지. pos가 괄호 안이면 괄호 안에서만.
    "본인 또는 배우자 연소득 5천만원"의 "본인 또는 배우자 연소득 "처럼 및·또는으로 나뉜 절을 넘어 본다."""
    groups = _paren_groups(text)
    inside = next(((s, e) for s, e in groups if s < pos < e), None)
    lo = inside[0] + 1 if inside else 0
    for q in find_quantities(text):
        if lo <= q.start and q.end <= pos:
            g = next((e for s, e in groups if s < q.start < e and (s, e) != inside), None)
            lo = max(lo, g or q.end)
    return text[lo:pos]


def negated(text: str, start: int, end: int, *, broad: bool = False) -> bool:
    """start에 있는 말 뒤(end부터) 같은 절(괄호에서 끊는다)에 제외·불가 말이 있나. broad면 "아닌·않·없"도 본다."""
    rx = _NOT_RE if broad else _NEG_RE
    return any(s <= start < e and rx.search(text, end, e) for s, e in clause_spans(text))


def comparator_later(text: str, pos: int) -> bool:
    """pos 뒤 줄 끝까지 비교어가 있나("5천만원(맞벌이 7천만원) 이하"의 5천만원은 "=="가 아니다)."""
    return bool(_ANY_CMP_RE.search(text, pos))


def convert(q: Quantity, target: str) -> float | str | None:
    """조건 value 단위로 바꾼다. 같은 종류는 그대로, 년→개월 ×12, 개월→년은 나누어떨어질 때만. 나머지는 None."""
    if q.kind == target:
        return q.value
    if q.kind == "years" and target == "months":
        return q.value * 12
    if q.kind == "months" and target == "years":
        return q.value / 12 if q.value % 12 == 0 else None
    return None
