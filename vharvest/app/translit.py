import re

from app.filenames import has_cyrillic

# Scene translit: Koloniya → Колония, Chernoknizhnik → Чернокнижник.
# Longer sequences are tried first so "iya" stays "ия", not "ий" + "а".
_PAIRS = (
    ("shch", "щ"),
    ("sch", "щ"),
    ("iya", "ия"),
    ("yo", "ё"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "е"),
    ("jo", "ё"),
    ("ju", "ю"),
    ("ja", "я"),
    ("ii", "ий"),
    ("yi", "ый"),
    ("ey", "ей"),
    ("oy", "ой"),
    ("oi", "ой"),
    ("ay", "ай"),
    ("uy", "уй"),
    ("oj", "ой"),
    ("ej", "ей"),
    ("aj", "ай"),
    ("ij", "ий"),
    ("iy", "ий"),
)
_SINGLE = {
    "a": "а",
    "b": "б",
    "c": "ц",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "х",
    "y": "ы",
    "z": "з",
}
_ORDERED = tuple(sorted(_PAIRS, key=lambda item: len(item[0]), reverse=True))
_VOWELS = set("aeiou")
_MIXED_TOKEN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).+$")
# Strong Russian-in-Latin markers. "ya" only at a word end, so "Royal" stays English.
_RU_LATIN = re.compile(
    r"shch|zh|kh|ii|yi|iya|(?:ya|yu|yo|ja|ju|jo)(?=[^a-z]|$)",
    re.IGNORECASE,
)
_SURE_SCORE = 0.92
_WEAK_LATIN_SCORE = 0.58


def clean_query(title: str) -> str:
    kept = [token for token in (title or "").split() if not _MIXED_TOKEN.fullmatch(token)]
    return " ".join(kept)


def looks_like_ru_latin(title: str) -> bool:
    text = clean_query(title) or (title or "").strip()
    if not text or has_cyrillic(text):
        return False
    return _RU_LATIN.search(text) is not None


def cyrillic_variant(title: str) -> str | None:
    text = clean_query(title) or (title or "").strip()
    if not text or has_cyrillic(text) or not re.search(r"[A-Za-z]", text):
        return None
    converted = _capitalize(_convert(text.lower()))
    if not has_cyrillic(converted) or converted.casefold() == text.casefold():
        return None
    return converted


def ordered_queries(title: str) -> list[str]:
    cleaned = clean_query(title) or (title or "").strip()
    if not cleaned:
        return []
    ru = cyrillic_variant(cleaned)
    if not ru:
        return [cleaned]
    if looks_like_ru_latin(cleaned):
        return [ru, cleaned]
    return [cleaned, ru]


def should_try_alternate(title: str, score: float | None) -> bool:
    if len(ordered_queries(title)) < 2:
        return False
    if score is not None and score >= _SURE_SCORE:
        return False
    if looks_like_ru_latin(title):
        return True
    return score is None or score < _WEAK_LATIN_SCORE


def _convert(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if not ("a" <= char <= "z"):
            out.append(char)
            index += 1
            continue
        matched = False
        for latin, cyrillic in _ORDERED:
            if not text.startswith(latin, index):
                continue
            # "oya"/"aya" are о+я and а+я, not ой+а and ай+а.
            nxt = index + len(latin)
            if latin.endswith("y") and nxt < len(text) and text[nxt] in _VOWELS:
                continue
            out.append(cyrillic)
            index = nxt
            matched = True
            break
        if not matched:
            out.append(_SINGLE.get(char, char))
            index += 1
    return "".join(out)


def _capitalize(text: str) -> str:
    chars = list(text)
    for index, char in enumerate(chars):
        if char.isalpha():
            chars[index] = char.upper()
            return "".join(chars)
    return text
