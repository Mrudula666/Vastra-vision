"""Shared paths, metadata schema and helpers for the Vastra Vision data pipeline.

Pipeline:
    collect  ->  data/candidates/<style>/   (status = candidate)
    quality  ->  hard failures moved to data/rejected/<style>/
    review   ->  you keep or reject each candidate in a web page
    apply    ->  kept images move to data/images/<style>/ (status = accepted)

Only data/images/ is used for training.

Trust tiers (how sure we are that the label is right):
    A  own photos/videos of a verified piece (GI tag, Handloom/Silk Mark, bought
       from a GI cooperative) or images given with permission by such a source
    B  museum catalogue record whose place/culture fields match the style
    C  open web (Wikimedia Commons) after human review
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CARDS = ROOT / "cards"
METADATA = DATA / "metadata.csv"
FOLDERS = {
    "candidate": DATA / "candidates",
    "accepted": DATA / "images",
    "rejected": DATA / "rejected",
}

FIELDS = [
    "file_name", "style", "status", "trust_tier", "source", "source_url",
    "author", "license", "type", "group_id", "quality_flags", "notes",
]

STYLES = ["kalamkari", "pochampally_ikat", "mangalagiri", "banarasi", "bandhani", "kanjeevaram"]
# explicit prefixes: banarasi and bandhani both start with "ban"
PREFIX = {
    "kalamkari": "kal", "pochampally_ikat": "poc", "mangalagiri": "man",
    "banarasi": "bnr", "bandhani": "bdh", "kanjeevaram": "knj",
}

# Words that confirm a record really is this style (checked against catalogue text)
STYLE_KEYWORDS = {
    "kalamkari": ["kalamkari", "srikalahasti", "kalahasti", "kalamkar"],
    "pochampally_ikat": ["pochampally", "pochampalli", "telia rumal", "chirala", "puttapaka"],
    "mangalagiri": ["mangalagiri"],
    "banarasi": ["banaras", "benares", "banarasi", "varanasi", "kinkhab", "kimkhab"],
    "bandhani": ["bandhani", "bandhej", "bandhana", "bandhni", "tie-dye", "tie-dyed", "tie dyed"],
    "kanjeevaram": ["kanchipuram", "kanjeevaram", "kanjivaram", "kancheepuram", "conjeeveram"],
}


def load_metadata():
    if not METADATA.exists() or METADATA.stat().st_size == 0:
        return []
    with METADATA.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:  # upgrade rows written by older versions of the scripts
        for k in FIELDS:
            r.setdefault(k, "")
            r[k] = r[k] or ""
        if not r["status"]:
            r["status"] = "accepted"
    return rows


def save_metadata(rows):
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    with METADATA.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def image_path(row):
    return FOLDERS[row["status"]] / row["style"] / row["file_name"]


def move(row, new_status):
    src = image_path(row)
    row["status"] = new_status
    dst = image_path(row)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists() and src != dst:
        src.rename(dst)


def next_number(style):
    """Next free file number for a style, looking in every folder so names never clash."""
    prefix = PREFIX[style]
    best = 0
    for folder in FOLDERS.values():
        for p in (folder / style).glob(f"{prefix}_*"):
            tail = p.stem.split("_")[-1]
            if tail.isdigit():
                best = max(best, int(tail))
    return best + 1


def new_file_name(style, number, ext=".jpg"):
    return f"{PREFIX[style]}_{number:05d}{ext}"


def add_flag(row, flag):
    flags = [f for f in row["quality_flags"].split(";") if f]
    if flag not in flags:
        flags.append(flag)
    row["quality_flags"] = ";".join(flags)


def mentions_style(text, style):
    t = (text or "").lower()
    return any(k in t for k in STYLE_KEYWORDS[style])
