"""
Turn a short phone video of a VERIFIED saree into many training images (trust tier A).

Record 30–60 seconds slowly moving over the saree (full view, border, pallu,
body close-ups). The script keeps one sharp frame per second and skips blurry
ones. One minute of video gives about 40–60 images.

    python src/video_to_frames.py saree1.mp4 --style mangalagiri --group mang_s01 \
        --proof "GI tag on label" --source "APCO Vijayawada"

Use only pieces whose authenticity you checked (GI tag, Handloom / Silk Mark,
bought from a GI cooperative). Use a new --group for every saree: frames of one
saree look almost the same, so they must stay together in either the training
or the test set, or the accuracy number will look falsely high.
"""

import argparse
from pathlib import Path

import cv2

from common import FOLDERS, STYLES, load_metadata, new_file_name, next_number, save_metadata

VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".m4v"}


def sharpness(frame):
    return cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def resize(frame, max_side=1024):
    h, w = frame.shape[:2]
    s = max_side / max(h, w)
    return frame if s >= 1 else cv2.resize(frame, (int(w * s), int(h * s)))


def extract(video, a, n):
    dest = FOLDERS["accepted"] / a.style
    dest.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    step = max(1, int((cap.get(cv2.CAP_PROP_FPS) or 30) * a.every))
    rows, frame_no, blurry = [], 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_no % step == 0:
            if sharpness(frame) < a.min_sharp:
                blurry += 1
            else:
                name = new_file_name(a.style, n)
                cv2.imwrite(str(dest / name), resize(frame), [cv2.IMWRITE_JPEG_QUALITY, 92])
                rows.append({"file_name": name, "style": a.style, "status": "accepted",
                             "trust_tier": "A", "source": a.source, "source_url": video.name,
                             "author": "self", "license": "own", "type": "craft",
                             "group_id": a.group, "quality_flags": "",
                             "notes": f"proof: {a.proof}; frame {frame_no}"})
                n += 1
        frame_no += 1
    cap.release()
    print(f"{video.name}: saved {len(rows)} frames, skipped {blurry} blurry")
    return rows, n


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract training frames from verified saree videos.")
    p.add_argument("path", help="a video file or a folder of videos")
    p.add_argument("--style", required=True, choices=STYLES)
    p.add_argument("--group", required=True, help="one id per saree, e.g. mang_s01")
    p.add_argument("--proof", required=True, help="how authenticity was checked, e.g. 'GI tag on label'")
    p.add_argument("--source", default="own collection", help="where the saree is from")
    p.add_argument("--every", type=float, default=1.0, help="seconds between frames")
    p.add_argument("--min-sharp", type=float, default=80.0, help="raise to skip more blurry frames")
    a = p.parse_args()

    src = Path(a.path).expanduser()
    videos = sorted(v for v in src.iterdir() if v.suffix.lower() in VIDEO_EXT) if src.is_dir() else [src]
    rows, n = load_metadata(), next_number(a.style)
    for v in videos:
        new, n = extract(v, a, n)
        rows += new
    save_metadata(rows)
