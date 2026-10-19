"""
Add images from a VERIFIED source straight into the training set (trust tier A).

Use this for photos you took of a piece whose authenticity you checked
(GI tag, Handloom Mark / Silk Mark label, bought from a GI cooperative or
state emporium), or images a cooperative or weaver sent you with permission.

    python src/add_verified.py ~/Pictures/mang_saree1 --style mangalagiri \
        --source "APCO Vijayawada" --group mang_s01 \
        --proof "GI tag photographed" --license own

    python src/add_verified.py ./from_coop --style pochampally_ikat \
        --source "Pochampally weavers cooperative" --group poc_s03 \
        --proof "sent by cooperative" --license "permission granted 2026-10-20"

Keep one --group per physical piece, so all photos of one saree stay together
when the data is split into train and test sets.
"""

import argparse
import shutil
from pathlib import Path

from PIL import Image

from common import FOLDERS, STYLES, load_metadata, new_file_name, next_number, save_metadata

EXT = {".jpg", ".jpeg", ".png", ".webp"}

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Add verified images (tier A).")
    p.add_argument("folder")
    p.add_argument("--style", required=True, choices=STYLES)
    p.add_argument("--source", required=True, help="who or where the piece came from")
    p.add_argument("--group", required=True, help="one id per physical piece, e.g. mang_s01")
    p.add_argument("--proof", required=True, help="how authenticity was checked")
    p.add_argument("--license", default="own", help="own, or the permission you received")
    p.add_argument("--type", default="craft", choices=["craft", "artifact"])
    a = p.parse_args()

    files = sorted(f for f in Path(a.folder).expanduser().iterdir() if f.suffix.lower() in EXT)
    rows = load_metadata()
    dest = FOLDERS["accepted"] / a.style
    dest.mkdir(parents=True, exist_ok=True)
    n = next_number(a.style)
    added = 0
    for f in files:
        try:
            with Image.open(f) as im:
                if min(im.size) < 256:
                    print(f"  skip {f.name}: too small {im.size}")
                    continue
        except Exception:
            print(f"  skip {f.name}: not a readable image")
            continue
        name = new_file_name(a.style, n, ".png" if f.suffix.lower() == ".png" else ".jpg")
        if f.suffix.lower() in (".webp",):
            Image.open(f).convert("RGB").save(dest / name, quality=92)
        else:
            shutil.copy2(f, dest / name)
        n += 1
        rows.append({"file_name": name, "style": a.style, "status": "accepted", "trust_tier": "A",
                     "source": a.source, "source_url": f.name, "author": "self",
                     "license": a.license, "type": a.type, "group_id": a.group,
                     "quality_flags": "", "notes": f"proof: {a.proof}"})
        added += 1
    save_metadata(rows)
    print(f"Added {added} tier-A images to data/images/{a.style}/")
