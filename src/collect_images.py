"""
Step 1 of the pipeline: collect CANDIDATE images from museum archives and open sources.

Museum records are only kept when their catalogue says the object is an Indian
textile (place / culture / object-type fields), so an Indonesian ikat or a
modern print does not slip in just because the search word matched.

Sources:
    met        The Met (public-domain objects)              tier B
    cleveland  Cleveland Museum of Art (CC0)                 tier B
    artic      Art Institute of Chicago (public domain)      tier B
    vam        Victoria and Albert Museum                    tier B  (opt-in: --include-vam,
               free for non-commercial use only; huge Indian textile collection)
    commons    Wikimedia Commons (CC BY / BY-SA / CC0 / PD)  tier C

Everything lands in data/candidates/<style>/ with status=candidate.
Nothing is used for training until it passes quality_filter.py and review.py.

Usage (from the repo root):
    python src/collect_images.py
    python src/collect_images.py --style kalamkari --source met --max 40
    python src/collect_images.py --include-vam
"""

import argparse
import hashlib
import io
import time

import requests
from PIL import Image

from common import (FOLDERS, STYLES, load_metadata, mentions_style, new_file_name,
                    next_number, save_metadata)

HEADERS = {"User-Agent": "VastraVision/0.2 (educational ML project; https://github.com/Mrudula666/Vastra-vision)"}

# Museum catalogues use older or broader names, so museum queries differ from web queries.
MUSEUM_QUERIES = {
    "kalamkari": ["kalamkari", "Srikalahasti", "temple hanging India painted cotton", "palampore"],
    "pochampally_ikat": ["Pochampally", "telia rumal", "ikat Andhra Pradesh", "ikat Telangana"],
    "mangalagiri": ["Mangalagiri"],
    "banarasi": ["Banaras brocade", "Benares sari", "Varanasi brocade", "kinkhab"],
    "bandhani": ["bandhani", "bandhej", "tie-dyed odhni", "tie-dyed sari Gujarat"],
    "kanjeevaram": ["Kanchipuram sari", "Kanjeevaram", "Tamil Nadu silk sari"],
}
WEB_QUERIES = {
    "kalamkari": ["Srikalahasti Kalamkari", "Kalamkari"],
    "pochampally_ikat": ["Pochampally saree", "Pochampally ikat"],
    "mangalagiri": ["Mangalagiri saree", "Mangalagiri handloom"],
    "banarasi": ["Banarasi saree", "Banaras brocade"],
    "bandhani": ["Bandhani", "Bandhej"],
    "kanjeevaram": ["Kanchipuram saree", "Kanjeevaram silk"],
}

INDIA_WORDS = ["india", "indian", "andhra", "telangana", "gujarat", "rajasthan", "varanasi",
               "banaras", "benares", "tamil", "kanchipuram", "madras", "coromandel", "deccan",
               "golconda", "masulipatnam", "machilipatnam", "kutch", "kachchh", "jamnagar",
               "hyderabad", "uttar pradesh", "mughal"]
TEXTILE_WORDS = ["textile", "sari", "saree", "cloth", "fabric", "hanging", "shawl", "odhni",
                 "odhani", "dupatta", "turban", "rumal", "panel", "fragment", "brocade", "skirt",
                 "garment", "coverlet", "palampore", "chintz", "cotton", "silk", "dyed", "woven"]

OPEN_LICENSE_PREFIXES = ("cc by", "cc-by", "cc0", "public domain", "pd")
BLOCKED_LICENSE_WORDS = ("nc", "nd", "fair", "non-free")


def license_ok(text):
    t = (text or "").strip().lower()
    if not t.startswith(OPEN_LICENSE_PREFIXES):
        return False
    return not any(w in t.replace("-", " ").split() for w in BLOCKED_LICENSE_WORDS)


def is_indian_textile(text):
    t = (text or "").lower()
    return any(w in t for w in INDIA_WORDS) and any(w in t for w in TEXTILE_WORDS)


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


def fetch_image(url):
    """Return image bytes if the URL really is a readable image, else None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            return None
        Image.open(io.BytesIO(r.content)).verify()
        return r.content
    except Exception:
        return None


# ---------------------------------------------------------------- sources
# Each source yields dicts: image_url, source, source_url, author, license,
# trust_tier, type, record_text (catalogue text used for checks), notes

def src_met(query, limit):
    data = get_json("https://collectionapi.metmuseum.org/public/collection/v1/search",
                    {"q": query, "hasImages": "true"})
    for oid in ((data or {}).get("objectIDs") or [])[: limit * 3]:
        o = get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")
        time.sleep(0.1)
        if not o or not o.get("isPublicDomain") or not o.get("primaryImageSmall"):
            continue
        text = " | ".join(str(o.get(k, "")) for k in
                          ("title", "objectName", "classification", "culture", "country",
                           "region", "city", "medium", "objectDate"))
        yield {"image_url": o["primaryImageSmall"], "source": "met_museum",
               "source_url": o.get("objectURL", ""),
               "author": o.get("artistDisplayName") or "The Metropolitan Museum of Art",
               "license": "CC0 (Met Open Access)", "trust_tier": "B", "type": "artifact",
               "record_text": text, "notes": text}


def src_cleveland(query, limit):
    data = get_json("https://openaccess-api.clevelandart.org/api/artworks/",
                    {"q": query, "has_image": 1, "cc0": 1, "limit": min(limit * 2, 100)})
    for o in (data or {}).get("data", []):
        web = ((o.get("images") or {}).get("web") or {}).get("url")
        if not web:
            continue
        text = " | ".join(str(x) for x in (o.get("title", ""), o.get("type", ""),
                                            ", ".join(o.get("culture") or []), o.get("technique", ""),
                                            o.get("department", ""), o.get("creation_date", "")))
        yield {"image_url": web, "source": "cleveland_museum", "source_url": o.get("url", ""),
               "author": "The Cleveland Museum of Art", "license": "CC0", "trust_tier": "B",
               "type": "artifact", "record_text": text, "notes": text}


def src_artic(query, limit):
    data = get_json("https://api.artic.edu/api/v1/artworks/search", {
        "q": query, "limit": min(limit * 2, 100),
        "fields": "id,title,image_id,place_of_origin,date_display,artwork_type_title,"
                  "medium_display,is_public_domain,classification_titles"})
    for o in (data or {}).get("data", []):
        if not o.get("is_public_domain") or not o.get("image_id"):
            continue
        text = " | ".join(str(x) for x in (o.get("title", ""), o.get("artwork_type_title", ""),
                                            o.get("place_of_origin", ""), o.get("medium_display", ""),
                                            ", ".join(o.get("classification_titles") or []),
                                            o.get("date_display", "")))
        yield {"image_url": f"https://www.artic.edu/iiif/2/{o['image_id']}/full/843,/0/default.jpg",
               "source": "art_institute_chicago",
               "source_url": f"https://www.artic.edu/artworks/{o['id']}",
               "author": "Art Institute of Chicago", "license": "CC0", "trust_tier": "B",
               "type": "artifact", "record_text": text, "notes": text}


def src_vam(query, limit):
    data = get_json("https://api.vam.ac.uk/v2/objects/search",
                    {"q": query, "images_exist": 1, "page_size": min(limit * 2, 100)})
    for o in (data or {}).get("records", []):
        base = (o.get("_images") or {}).get("_iiif_image_base_url")
        if not base:
            continue
        maker = (o.get("_primaryMaker") or {}).get("name", "")
        text = " | ".join(str(x) for x in (o.get("_primaryTitle", ""), o.get("objectType", ""),
                                            o.get("_primaryPlace", ""), o.get("_primaryDate", ""), maker))
        yield {"image_url": f"{base}full/1024,/0/default.jpg", "source": "va_museum",
               "source_url": f"https://collections.vam.ac.uk/item/{o.get('systemNumber', '')}/",
               "author": maker or "Victoria and Albert Museum",
               "license": "V&A non-commercial use", "trust_tier": "B", "type": "artifact",
               "record_text": text, "notes": text}


def src_commons(query, limit):
    data = get_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": min(limit, 50),
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 1024})
    for page in ((data or {}).get("query", {}).get("pages", {})).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not license_ok(lic):
            continue
        author = meta.get("Artist", {}).get("value", "")
        if "<" in author:  # strip HTML links
            import re
            author = re.sub("<[^>]+>", "", author)
        title = page.get("title", "").replace("File:", "")
        desc = meta.get("ImageDescription", {}).get("value", "")
        yield {"image_url": info.get("thumburl") or info.get("url"), "source": "wikimedia_commons",
               "source_url": info.get("descriptionurl", ""), "author": author.strip()[:120],
               "license": lic, "trust_tier": "C", "type": "to_check",
               "record_text": f"{title} {desc}", "notes": title}


SOURCES = {"met": src_met, "cleveland": src_cleveland, "artic": src_artic,
           "vam": src_vam, "commons": src_commons}
MUSEUMS = {"met", "cleveland", "artic", "vam"}


# ---------------------------------------------------------------- main

def collect(styles, sources, max_per_source):
    rows = load_metadata()
    seen_urls = {r["source_url"] for r in rows if r["source_url"]}
    seen_md5 = set()

    for style in styles:
        n = next_number(style)
        folder = FOLDERS["candidate"] / style
        folder.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {style} ===")
        for name in sources:
            added = skipped = 0
            queries = MUSEUM_QUERIES[style] if name in MUSEUMS else WEB_QUERIES[style]
            for q in queries:
                if added >= max_per_source:
                    break
                for item in SOURCES[name](q, max_per_source):
                    if added >= max_per_source:
                        break
                    if not item["image_url"] or item["source_url"] in seen_urls:
                        continue
                    if name in MUSEUMS and not is_indian_textile(item["record_text"]):
                        skipped += 1
                        continue
                    data = fetch_image(item["image_url"])
                    if not data:
                        continue
                    md5 = hashlib.md5(data).hexdigest()
                    if md5 in seen_md5:
                        continue
                    seen_md5.add(md5)
                    seen_urls.add(item["source_url"])
                    ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
                    file_name = new_file_name(style, n, ext)
                    n += 1
                    (folder / file_name).write_bytes(data)
                    row = {k: item.get(k, "") for k in
                           ("source", "source_url", "author", "license", "trust_tier", "type", "notes")}
                    row.update(file_name=file_name, style=style, status="candidate",
                               group_id=item["source_url"], quality_flags="")
                    row["notes"] = row["notes"][:200]
                    if not mentions_style(item["record_text"], style):
                        row["quality_flags"] = "label_unconfirmed"
                    rows.append(row)
                    added += 1
                    print(f"  + {file_name} [{name}] {row['notes'][:70]}")
            print(f"  {name}: {added} new, {skipped} skipped (catalogue says not an Indian textile)")
        save_metadata(rows)  # save after each style so nothing is lost if it stops

    print("\nNext:  python src/quality_filter.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Collect candidate images for Vastra Vision.")
    p.add_argument("--style", choices=STYLES)
    p.add_argument("--source", choices=list(SOURCES))
    p.add_argument("--max", type=int, default=40, help="max new images per style per source")
    p.add_argument("--include-vam", action="store_true",
                   help="also use the V&A (free for non-commercial use only)")
    a = p.parse_args()

    if a.source:
        chosen = [a.source]
    else:
        chosen = ["met", "cleveland", "artic"] + (["vam"] if a.include_vam else []) + ["commons"]
    collect([a.style] if a.style else STYLES, chosen, a.max)
