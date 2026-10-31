"""글자 2-gram BM25 검색. 메모리 색인이고 벡터 DB는 쓰지 않는다.

띄어쓰기로 나눈 덩어리마다 글자 두 개씩 쪼갠다("신혼부부" → 신혼, 혼부, 부부). 한국어는 붙여 쓰고
줄여 쓰는 일이 많아 형태소 분석 없이도 부분 일치가 잡힌다. 줄임말은 ABBREV와 조건표 aliases로 넓힌다.
BM25는 역색인 위에 직접 구현했다(idf는 음수가 나지 않는 Lucene 식).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

import numpy as np

# 조건표 aliases로 못 넓히는 흔한 줄임말. 원문 용어로 바꿔 덧붙인다(원래 검색어도 남긴다).
ABBREV = {
    "특공": "특별공급",
    "생초": "생애최초",
    "신특": "신혼부부 특별공급",
    "전세대출": "전세자금",
    "다둥이": "다자녀",
}

FIELD_WEIGHT = {"name": 3, "aliases": 2}


class BM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.n = len(corpus)
        lengths = np.array([len(d) for d in corpus], dtype=float)
        self.norm = k1 * (1 - b + b * lengths / max(lengths.mean(), 1.0))
        self.k1 = k1
        postings: dict[str, tuple[list[int], list[int]]] = {}
        for i, doc in enumerate(corpus):
            for term, tf in Counter(doc).items():
                ids, tfs = postings.setdefault(term, ([], []))
                ids.append(i)
                tfs.append(tf)
        self.postings = {t: (np.array(ids), np.array(tfs, dtype=float)) for t, (ids, tfs) in postings.items()}
        self.idf = {t: math.log((self.n - len(ids) + 0.5) / (len(ids) + 0.5) + 1) for t, (ids, _) in self.postings.items()}

    def get_scores(self, query: list[str]) -> np.ndarray:
        scores = np.zeros(self.n)
        for term in query:
            if term in self.postings:
                ids, tfs = self.postings[term]
                scores[ids] += self.idf[term] * tfs * (self.k1 + 1) / (tfs + self.norm[ids])
        return scores


def norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").lower()


def bigrams(text: str) -> list[str]:
    out = []
    for seg in re.findall(r"[0-9a-z가-힣]+", norm(text)):
        out.extend([seg] if len(seg) == 1 else [seg[i:i + 2] for i in range(len(seg) - 1)])
    return out


def doc_tokens(doc: dict) -> list[str]:
    tokens = bigrams(doc["name"]) * FIELD_WEIGHT["name"]
    for key, value in doc["fields"].items():
        if value:
            tokens += bigrams(str(value)) * FIELD_WEIGHT.get(key, 1)
    if doc.get("org"):
        tokens += bigrams(doc["org"])
    return tokens


def expand_query(q: str, rules: dict[str, dict]) -> str:
    parts = [q]
    squeezed = re.sub(r"\s+", "", norm(q))
    for short, full in ABBREV.items():
        if short in squeezed:
            parts.append(full)
    for rule in rules.values():
        for alias in rule.get("aliases") or []:
            a = re.sub(r"\s+", "", norm(alias))
            if len(a) >= 2 and len(squeezed) >= 2 and (a in squeezed or squeezed in a):
                parts.append(rule.get("name") or "")
                break
    return " ".join(parts)


def _squeeze(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", norm(text))


def _in_region(doc: dict, sido: str) -> bool:
    region = doc.get("region")
    if region is None:
        return True   # 전국
    return isinstance(region, dict) and region.get("sido") == sido


class SearchIndex:
    def __init__(self, docs: list[dict], rules: dict[str, dict]) -> None:
        self.docs = docs
        self.rules = rules
        tokenized = [doc_tokens(d) or ["_"] for d in docs]
        self.bm25 = BM25(tokenized) if docs else None
        self.names = [_squeeze(d["name"]) for d in docs]

    def search(self, q: str, *, limit: int = 20, tag: str | None = None, subject: str | None = None,
               sido: str | None = None) -> list[tuple[dict, float]]:
        if not self.bm25:
            return []
        query = bigrams(expand_query(q, self.rules))
        if not query:
            return []
        scores = self.bm25.get_scores(query)
        # 본문이 긴 제도는 길이 보정으로 점수가 깎인다. 이름이 검색어와 같거나 검색어를 통째로 담으면 얹는다.
        target = _squeeze(q)
        if len(target) >= 2 and scores.max() > 0:
            top = float(scores.max())
            for i in np.nonzero(scores)[0]:
                name = self.names[i]
                if name == target:
                    scores[i] += top
                elif target in name:
                    scores[i] += top * 0.5
        order = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: -scores[i])
        out = []
        for i in order:
            doc = self.docs[i]
            if tag and tag not in doc["stage_tags"]:
                continue
            if subject and doc["subject"] != subject:
                continue
            if sido and not _in_region(doc, sido):
                continue
            out.append((doc, float(scores[i])))
            if len(out) >= limit:
                break
        return out


def snippet(doc: dict, q: str, width: int = 30) -> str | None:
    """검색어 조각이 처음 나오는 곳의 앞뒤. 원문을 그대로 자른다."""
    terms = [t for t in bigrams(q) if len(t) == 2] or bigrams(q)
    for value in [doc["fields"].get(k) for k in ("criteria", "target", "summary", "benefit", "aliases")]:
        text = re.sub(r"\s+", " ", str(value or ""))
        low = norm(text)
        hits = [low.find(t) for t in terms if t in low]
        if hits:
            at = min(hits)
            start = max(0, at - width)
            return ("…" if start else "") + text[start:at + width] + ("…" if at + width < len(text) else "")
    summary = doc["fields"].get("summary")
    return str(summary)[: width * 2] if summary else None
