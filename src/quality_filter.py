"""
Step 2 of the pipeline: automatic quality filtering of candidate images.

Hard failures are moved to data/rejected/ straight away:
    corrupt        file cannot be opened
    too_small      shortest side under --min-side pixels (default 256)
    duplicate      looks the same as an image already kept or collected (perceptual hash)

Softer problems are only FLAGGED, so you decide in the review page:
    blurry                 low sharpness
    conflict_with:<style>  the same picture is also in another style's folder
    label_unconfirmed      catalogue text never names the style (set by collect_images.py)
    maybe_not_textile      CLIP thinks it is not a textile photo        (--clip only)
    clip_suggests:<style>  CLIP's best guess is a different style       (--clip only)

CLIP is optional (pip install -r requirements-clip.txt). It is only a hint:
it does not know Mangalagiri from Venkatagiri, so it never rejects anything.

Usage:
    python src/quality_filter.py
    python src/quality_filter.py --style bandhani --clip
"""

import argparse

import cv2
import imagehash
import numpy as np
from PIL import Image

from common import STYLES, add_flag, image_path, load_metadata, move, save_metadata

STYLE_PROMPTS = {
    "kalamkari": "hand-painted Kalamkari cloth with mythological figures and bold outlines",
    "pochampally_ikat": "a Pochampally ikat saree with sharp geometric patterns",
    "mangalagiri": "a plain cotton Mangalagiri saree with a thin gold zari border",
    "banarasi": "a Banarasi silk brocade saree with heavy gold zari floral patterns",
    "bandhani": "Bandhani tie-dye fabric covered in tiny dots",
    "kanjeevaram": "a Kanjeevaram silk saree with a wide contrasting temple border",
}
TEXTILE_PROMPTS = ["a close-up photo of a woven or printed textile", "a photo of a saree",
                   "a photo of a patterned fabric", "a museum photo of an old textile"]
OTHER_PROMPTS = ["a photo of a person's face", "a photo of a building", "a page of printed text",
                 "a photo of jewellery", "a landscape photo", "a photo of a shop or market street"]


def sharpness(img):
    g = np.array(img.convert("L").resize((512, 512)))
    return cv2.Laplacian(g, cv2.CV_64F).var()


class Clip:
    def __init__(self):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
        self.proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    def probs(self, img, texts):
        with self.torch.no_grad():
            x = self.proc(text=texts, images=img, return_tensors="pt", padding=True)
            return self.model(**x).logits_per_image.softmax(dim=-1)[0].tolist()

    def check(self, img):
        p = self.probs(img, TEXTILE_PROMPTS + OTHER_PROMPTS)
        textile = sum(p[: len(TEXTILE_PROMPTS)])
        s = self.probs(img, [f"a photo of {d}" for d in STYLE_PROMPTS.values()])
        best = list(STYLE_PROMPTS)[int(np.argmax(s))]
        return textile, best


def run(styles, min_side, blur_limit, dup_distance, use_clip):
    rows = load_metadata()
    clip = Clip() if use_clip else None
    known = []  # (hash, row) for every accepted image, then each candidate as it passes
    counts = {"rejected": 0, "flagged": 0, "ok": 0}

    for r in rows:
        if r["status"] == "accepted" and image_path(r).exists():
            try:
                known.append((imagehash.phash(Image.open(image_path(r))), r))
            except Exception:
                pass

    for r in rows:
        if r["status"] != "candidate" or r["style"] not in styles:
            continue
        path = image_path(r)
        try:
            img = Image.open(path)
            img.load()
            img = img.convert("RGB")
        except Exception:
            add_flag(r, "corrupt"); move(r, "rejected"); counts["rejected"] += 1
            continue

        if min(img.size) < min_side:
            add_flag(r, "too_small"); move(r, "rejected"); counts["rejected"] += 1
            continue

        h = imagehash.phash(img)
        twin = next((k for k in known if h - k[0] <= dup_distance), None)
        if twin and twin[1]["style"] == r["style"]:
            add_flag(r, f"duplicate_of:{twin[1]['file_name']}"); move(r, "rejected")
            counts["rejected"] += 1
            continue
        if twin:
            add_flag(r, f"conflict_with:{twin[1]['style']}/{twin[1]['file_name']}")
            add_flag(twin[1], f"conflict_with:{r['style']}/{r['file_name']}")

        if sharpness(img) < blur_limit:
            add_flag(r, "blurry")

        if clip:
            textile, best = clip.check(img)
            if textile < 0.5:
                add_flag(r, "maybe_not_textile")
            if best != r["style"]:
                add_flag(r, f"clip_suggests:{best}")

        known.append((h, r))
        counts["flagged" if r["quality_flags"] else "ok"] += 1

    save_metadata(rows)
    print(f"Moved to rejected: {counts['rejected']}   flagged for review: {counts['flagged']}   "
          f"clean: {counts['ok']}")
    print("Next:  python src/review.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Automatic quality filter for candidate images.")
    p.add_argument("--style", choices=STYLES)
    p.add_argument("--min-side", type=int, default=256)
    p.add_argument("--blur", type=float, default=60.0, help="sharpness below this is flagged blurry")
    p.add_argument("--dup-distance", type=int, default=6, help="perceptual-hash distance counted as duplicate")
    p.add_argument("--clip", action="store_true", help="also run CLIP hints (needs requirements-clip.txt)")
    a = p.parse_args()
    run([a.style] if a.style else STYLES, a.min_side, a.blur, a.dup_distance, a.clip)
