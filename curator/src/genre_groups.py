from __future__ import annotations

import re


def display_genre_label(genre: str) -> str:
    parts = genre.replace("_", " ").replace("-", " ").strip().split()
    if not parts:
        return "Other"
    return " ".join(part.capitalize() for part in parts)


def _genre_search_text(genre: str) -> str:
    text = genre.replace("_", " ").replace("-", " ").strip().lower()
    return re.sub(r"\s+", " ", text)


GENRE_GROUP_PATTERNS: tuple[tuple[str, str], ...] = (
    ("House", r"\bhouse\b"),
    ("Techno", r"\btechno\b"),
    ("Breakbeat/Jungle", r"\bbreakbeat\b|jungle|drum.n.bass"),
    ("IDM", r"\bidm\b|experimental"),
    ("Trip-Hop", r"trip hop|triphop"),
    ("Disco", r"\bdisco\b"),
    ("Funk", r"\bfunk\b"),
    ("Soul", r"soul"),
    ("Jazz", r"\bjazz\b|fusion"),
    ("Blues", r"\bblues\b"),
    (
        "Alternative & Indie",
        r"\balt\b|alternative|indie|grunge|punk|new wave|psychedelic|psychedelisch|"
        r"kraut|prog rock|art rock|british invasion|adult alternative",
    ),
    ("Classical", r"classical|klassik|klassisch|neoclassical|baroque|barock"),
    ("Rock", r"rock|metal|surf|hardcore"),
    ("Lounge", r"lounge"),
    ("Pop", r"\bpop\b|easy listening|new age|christmas|inspirational|schlager|vocal"),
    ("Folk & Singer-Songwriter", r"folk|singer|songwriter|country|traditional folk"),
    ("Ambient", r"ambient"),
    (
        "Electronic",
        r"electro|electronica|dance|trance|downtempo|garage|bass|speed|deep|"
        r"post club|rave|edm|fitness|workout",
    ),
    ("Hip Hop & RnB", r"hip|hop|rap|r&b|rnb|r & b|r and b|dope"),
    (
        "Latin & Brasileiro",
        r"latin|latino|latina|pagode|tropical|baile|mpb|bossa|brazilian|"
        r"brasilianisch|balada|bolero|rumba|mexicana|mexiko|south america|"
        r"caribbean|karibik|urbano|reggae|dancehall|cuban|salsa|flamenco|samba",
    ),
    (
        "African & World",
        r"afro|african|afrikanische|afrobeats|highlife|world|welt|turkish|"
        r"halk|farsi|bollywood|j pop|kayokyoku|worldwide",
    ),
    ("Soundtrack", r"soundtrack|soundtracks|score|originalfilm|tv soundtrack"),
)


def canonical_genre_label(genre: str) -> str:
    text = _genre_search_text(genre)
    if not text:
        return "Sonstige"

    for label, pattern in GENRE_GROUP_PATTERNS:
        if re.search(pattern, text):
            return label
    if text in {"other", "sonstige"}:
        return "Sonstige"
    return "Sonstige"
