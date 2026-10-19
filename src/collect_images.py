"""
Download openly licensed textile images for every style, automatically.

Sources (all free, no API key needed):
  - Wikimedia Commons   (CC BY / CC BY-SA / CC0 / public domain only)
  - The Met Museum      (public-domain objects only)
  - Cleveland Museum    (CC0 objects only)

Each image goes to data/images/<style>/ and gets one row in data/metadata.csv
with its source, author and license, so Rule 4 (clean data) is handled for you.

Usage (run from the repo root):
    pip install -r requirements.txt
    python src/collect_images.py                 # all styles, all sources
    python src/collect_images.py --style bandhani
    python src/collect_images.py --max 80        # up to 80 per style per source

After it finishes, open each folder and DELETE any wrong image.
Then run:
    python src/collect_images.py --clean
to remove the deleted files' rows from metadata.csv.
"""

import argparse
import csv
import hashlib
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "data" / "images"
METADATA = ROOT / "data" / "metadata.csv"
FIELDS = ["file_name", "style", "source", "source_url", "author", "license", "type", "notes"]

HEADERS = {"User-Agent": "VastraVision/0.1 (educational ML project; https://github.com/Mrudula666/Vastra-vision)"}

# Search words per style. Add more words here if a style gets too few images.
QUERIES = {
    "kalamkari": ["Kalamkari", "Srikalahasti Kalamkari", "kalamkari painting"],
    "pochampally_ikat": ["Pochampally", "Pochampally ikat", "Telangana ikat saree"],
    "mangalagiri": ["Mangalagiri saree", "Mangalagiri handloom", "Mangalagiri cotton"],
    "banarasi": ["Banarasi saree", "Banaras brocade", "Varanasi brocade", "kimkhab"],
    "bandhani": ["Bandhani", "Bandhej", "Gujarat tie-dye textile"],
    "kanjeevaram": ["Kanchipuram saree", "Kanjeevaram silk", "Kanchipuram silk"],
}

ALLOWED_LICENSE_PREFIXES = ("cc by", "cc-by", "cc0", "public domain", "pd")
BLOCKED_LICENSE_WORDS = ("nc", "nd", "fair use", "non-free")


# ---------------------------------------------------------------- helpers

def load_metadata():
    if not METADATA.exists():
        return []
    with METADATA.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_metadata(rows):
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    with METADATA.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def license_ok(text):
    t = (text or "").strip().lower()
    if not t.startswith(ALLOWED_LICENSE_PREFIXES):
        return False
    words = t.replace("-", " ").split()
    return not any(w in words for w in BLOCKED_LICENSE_WORDS)


def get_json(url, params=None):
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (attempt + 1))
    return None


def download(url, dest):
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
            return None
        dest.write_bytes(r.content)
        return hashlib.md5(r.content).hexdigest()
    except requests.RequestException:
        return None


# ---------------------------------------------------------------- sources

def from_commons(query, limit):
    """Yield candidate images from Wikimedia Commons."""
    data = get_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": min(limit, 50),
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 1024,
    })
    pages = (data or {}).get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not license_ok(lic):
            continue
        author = meta.get("Artist", {}).get("value", "")
        author = author.split(">")[-2].split("<")[0] if "<" in author else author
        yield {
            "image_url": info.get("thumburl") or info.get("url"),
            "source": "wikimedia_commons",
            "source_url": info.get("descriptionurl", ""),
            "author": author.strip()[:120],
            "license": lic,
            "type": "to_check",            # Commons mixes artifacts and crafts: you decide
            "notes": page.get("title", "").replace("File:", "")[:150],
        }


def from_met(query, limit):
    """Yield public-domain objects from The Met."""
    data = get_json("https://collectionapi.metmuseum.org/public/collection/v1/search",
                    {"q": query, "hasImages": "true"})
    for oid in ((data or {}).get("objectIDs") or [])[:limit]:
        obj = get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")
        if not obj or not obj.get("isPublicDomain") or not obj.get("primaryImageSmall"):
            continue
        yield {
            "image_url": obj["primaryImageSmall"],
            "source": "met_museum",
            "source_url": obj.get("objectURL", ""),
            "author": obj.get("artistDisplayName") or "The Metropolitan Museum of Art",
            "license": "CC0 (Met Open Access)",
            "type": "artifact",
            "notes": f"{obj.get('title', '')} | {obj.get('objectDate', '')} | {obj.get('culture', '')}"[:150],
        }
        time.sleep(0.1)  # the Met asks for polite request rates


def from_cleveland(query, limit):
    """Yield CC0 objects from the Cleveland Museum of Art."""
    data = get_json("https://openaccess-api.clevelandart.org/api/artworks/",
                    {"q": query, "has_image": 1, "cc0": 1, "limit": min(limit, 100)})
    for obj in (data or {}).get("data", []):
        web = ((obj.get("images") or {}).get("web") or {}).get("url")
        if not web:
            continue
        yield {
            "image_url": web,
            "source": "cleveland_museum",
            "source_url": obj.get("url", ""),
            "author": "The Cleveland Museum of Art",
            "license": "CC0",
            "type": "artifact",
            "notes": f"{obj.get('title', '')} | {obj.get('creation_date', '')} | {obj.get('culture', [''])[0] if obj.get('culture') else ''}"[:150],
        }


SOURCES = {"commons": from_commons, "met": from_met, "cleveland": from_cleveland}


# ---------------------------------------------------------------- main steps

def collect(styles, sources, max_per_source):
    rows = load_metadata()
    seen_urls = {r["source_url"] for r in rows}
    seen_hashes = set()

    for style in styles:
        folder = IMAGES / style
        folder.mkdir(parents=True, exist_ok=True)
        prefix = style[:3]
        have = sum(1 for r in rows if r["style"] == style)
        # continue numbering after the highest existing file, so names never clash
        nums = [int(p.stem.split("_")[1]) for p in folder.glob(f"{prefix}_[0-9]*.*")
                if p.stem.split("_")[1].isdigit()]
        count = max(nums, default=0)
        print(f"\n=== {style} (already have {have}) ===")

        for source_name in sources:
            added = 0
            for query in QUERIES[style]:
                if added >= max_per_source:
                    break
                for item in SOURCES[source_name](query, max_per_source):
                    if added >= max_per_source:
                        break
                    if not item["image_url"] or item["source_url"] in seen_urls:
                        continue
                    count += 1
                    ext = ".png" if item["image_url"].lower().endswith(".png") else ".jpg"
                    file_name = f"{prefix}_{count:04d}{ext}"
                    digest = download(item["image_url"], folder / file_name)
                    if not digest or digest in seen_hashes:
                        (folder / file_name).unlink(missing_ok=True)
                        count -= 1
                        continue
                    seen_hashes.add(digest)
                    seen_urls.add(item["source_url"])
                    rows.append({
                        "file_name": file_name, "style": style, "source": item["source"],
                        "source_url": item["source_url"], "author": item["author"],
                        "license": item["license"], "type": item["type"], "notes": item["notes"],
                    })
                    added += 1
                    print(f"  + {file_name}  [{item['source']}] {item['notes'][:60]}")
            print(f"  {source_name}: {added} new")
        save_metadata(rows)  # save after every style, so nothing is lost if it stops

    print("\nDone. Now open each folder, delete wrong images, then run:  python src/collect_images.py --clean")


def clean():
    rows = load_metadata()
    kept = [r for r in rows if (IMAGES / r["style"] / r["file_name"]).exists()]
    save_metadata(kept)
    print(f"Removed {len(rows) - len(kept)} rows for deleted images. {len(kept)} images remain.")
    for style in QUERIES:
        n = sum(1 for r in kept if r["style"] == style)
        print(f"  {style:18s} {n}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Collect openly licensed images for Vastra Vision.")
    p.add_argument("--style", choices=list(QUERIES), help="only this style")
    p.add_argument("--source", choices=list(SOURCES), help="only this source")
    p.add_argument("--max", type=int, default=50, help="max new images per style per source")
    p.add_argument("--clean", action="store_true", help="drop metadata rows for deleted images")
    a = p.parse_args()

    if a.clean:
        clean()
    else:
        collect([a.style] if a.style else list(QUERIES),
                [a.source] if a.source else list(SOURCES),
                a.max)
