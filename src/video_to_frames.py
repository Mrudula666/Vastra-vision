"""
Turn a short phone video of a saree into many training images, automatically.

Record a 30–60 second video slowly moving over the saree (full view, border,
pallu, body close-ups). This script saves one sharp frame every second and
skips blurry ones. One 1-minute video gives about 40–60 images.

Usage (run from the repo root):
    python src/video_to_frames.py saree1.mp4 --style mangalagiri --saree-id mang_s01
    python src/video_to_frames.py videos/ --style kalamkari --saree-id kal_s02 --every 0.5

--saree-id is important: frames from the same saree look almost the same, so
during training all frames of one saree must stay together in either the
training set or the test set (otherwise the accuracy number looks fake-good).
"""

import argparse
import csv
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "data" / "images"
METADATA = ROOT / "data" / "metadata.csv"
FIELDS = ["file_name", "style", "source", "source_url", "author", "license", "type", "notes"]
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".m4v"}


def sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def resize(frame, max_side=1024):
    h, w = frame.shape[:2]
    scale = max_side / max(h, w)
    return frame if scale >= 1 else cv2.resize(frame, (int(w * scale), int(h * scale)))


def next_index(folder, prefix):
    nums = [int(p.stem.split("_")[-1]) for p in folder.glob(f"{prefix}_*.jpg") if p.stem.split("_")[-1].isdigit()]
    return max(nums, default=0) + 1


def extract(video, style, saree_id, every, min_sharp):
    folder = IMAGES / style
    folder.mkdir(parents=True, exist_ok=True)
    prefix = f"{style[:3]}_v"
    idx = next_index(folder, prefix)

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(fps * every))
    rows, frame_no, saved, blurry = [], 0, 0, 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_no % step == 0:
            if sharpness(frame) < min_sharp:
                blurry += 1
            else:
                name = f"{prefix}_{idx:04d}.jpg"
                cv2.imwrite(str(folder / name), resize(frame), [cv2.IMWRITE_JPEG_QUALITY, 92])
                rows.append({
                    "file_name": name, "style": style, "source": "own_video",
                    "source_url": video.name, "author": "self", "license": "own",
                    "type": "craft", "notes": f"saree_id={saree_id}; frame={frame_no}",
                })
                idx += 1
                saved += 1
        frame_no += 1
    cap.release()
    print(f"{video.name}: saved {saved} frames, skipped {blurry} blurry")
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract training frames from saree videos.")
    p.add_argument("path", help="a video file or a folder of videos")
    p.add_argument("--style", required=True,
                   choices=["kalamkari", "pochampally_ikat", "mangalagiri", "banarasi", "bandhani", "kanjeevaram"])
    p.add_argument("--saree-id", required=True, help="a short name for this saree, e.g. mang_s01")
    p.add_argument("--every", type=float, default=1.0, help="seconds between saved frames (default 1)")
    p.add_argument("--min-sharp", type=float, default=80.0, help="blur threshold; raise it to skip more blurry frames")
    a = p.parse_args()

    src = Path(a.path)
    videos = sorted(v for v in src.iterdir() if v.suffix.lower() in VIDEO_EXT) if src.is_dir() else [src]

    new_rows = []
    for v in videos:
        new_rows += extract(v, a.style, a.saree_id, a.every, a.min_sharp)

    exists = METADATA.exists() and METADATA.stat().st_size > 0
    with METADATA.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(new_rows)
    print(f"Added {len(new_rows)} rows to data/metadata.csv")
