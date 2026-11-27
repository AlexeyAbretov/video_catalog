import re
from difflib import SequenceMatcher

_PUNCT = re.compile(r"[^0-9a-zа-я]+")


def normalize(text: str | None) -> str:
    value = (text or "").lower().replace("ё", "е")
    value = _PUNCT.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


_YO_FLIP = {"е": "ё", "Е": "Ё", "ё": "е", "Ё": "Е"}


def yo_variants(title: str, limit: int = 8) -> list[str]:
    """е/ё swaps for search indexes that do not fold those letters.

    One letter at a time first, then pairs. The list stops at `limit`.
    """
    positions = [index for index, char in enumerate(title) if char in _YO_FLIP]
    if not positions or limit <= 0:
        return []
    variants: list[str] = []

    def add(indexes: tuple[int, ...]) -> None:
        if len(variants) >= limit:
            return
        chars = list(title)
        for index in indexes:
            chars[index] = _YO_FLIP[chars[index]]
        text = "".join(chars)
        if text != title and text not in variants:
            variants.append(text)

    for pos in positions:
        add((pos,))
    for left_at, left in enumerate(positions):
        for right in positions[left_at + 1 :]:
            if len(variants) >= limit:
                return variants
            add((left, right))
    return variants


def similarity(left: str, right: str) -> float:
    a = normalize(left)
    b = normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def score_match(
    query_title: str,
    query_year: int | None,
    candidate_titles: list[str],
    candidate_year: int | None,
) -> float:
    best = 0.0
    for title in candidate_titles:
        best = max(best, similarity(query_title, title))
    if query_year and candidate_year:
        gap = abs(candidate_year - query_year)
        if gap == 0:
            best = min(1.0, best + 0.12)
        elif gap == 1:
            best = min(1.0, best + 0.04)
        else:
            best -= 0.2
    return best


def classify(best: float, second: float | None) -> str:
    if best >= 0.78 and (second is None or best - second >= 0.05):
        return "matched"
    if best >= 0.58:
        return "ambiguous"
    return "failed"
