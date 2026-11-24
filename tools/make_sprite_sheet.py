"""把真人照片或视频做成横向精灵图（一行 N 帧），给 CSS steps() 帧动画用。

背景是纯黑（眼镜上黑色等于透明），人物保留真实明暗，染成眼镜的绿色。

用法：
  python -I make_sprite_sheet.py photos <照片目录> <输出.png> [--size 200] [--rotate 2]
  python -I make_sprite_sheet.py video <视频> <输出.png> --start 106 --end 193 --frames 16
         --crop 0.08,0,0.84,0.88 [--height 280]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_runner_frames import segment_photo  # noqa: E402

GREEN = np.array([0x40, 0xFF, 0x5E], dtype=float)


def tint(tone):
    """0..1 的明暗图 -> 绿色 RGB 图"""
    return Image.fromarray((tone[..., None] * GREEN).clip(0, 255).astype(np.uint8), "RGB")


def photo_frames(folder, size, rotate):
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")))
    heads = {}
    heads_file = os.path.join(folder, "heads.json")
    if os.path.exists(heads_file):
        with open(heads_file, encoding="utf-8") as f:
            heads = json.load(f)
    shots = [segment_photo(os.path.join(folder, n), heads.get(n)) for n in names]

    # 竖直方向所有帧共用一个窗口，保留身体起伏；水平方向每帧按上半身重心对齐
    top = min(np.nonzero(m)[0].min() for _, m, _ in shots)
    bottom = max(np.nonzero(m)[0].max() for _, m, _ in shots)
    height = (bottom - top) * 1.08
    y0 = top - (bottom - top) * 0.04
    frames = []
    for lum, mask, background in shots:
        ys, xs = np.nonzero(mask)
        upper = ys < ys.min() + (ys.max() - ys.min()) * 0.55
        center = xs[upper].mean()
        bright = np.percentile(lum[mask], 97)
        tone = 0.22 + 0.78 * np.clip((lum - background) / max(bright - background, 1e-6), 0.0, 1.0)
        soft = ndimage.gaussian_filter(mask.astype(float), 1.0)          # 边缘羽化，避免锯齿
        image = tint(tone ** 0.9 * soft)
        box = (center - height / 2, y0, center + height / 2, y0 + height)
        frames.append(image.transform((size, size), Image.EXTENT, box, Image.BICUBIC))
    rotate %= len(frames)
    return frames[rotate:] + frames[:rotate]


def video_frames(path, start, end, count, crop, height):
    import cv2
    capture = cv2.VideoCapture(path)
    shots = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        shots.append(frame)
    end = end if end > 0 else len(shots)
    x0, y0, x1, y1 = crop
    frames = []
    for i in range(count):
        frame = shots[min(int(round(start + (end - start) * i / count)), len(shots) - 1)]
        h, w = frame.shape[:2]
        frame = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(float) / 255.0
        lum, sat = hsv[..., 2], hsv[..., 1]
        # 浅色背景：比背景暗或颜色明显的像素是前景（人和器械）
        mask = ndimage.binary_opening((lum < 0.60) | (sat > 0.22), iterations=2)
        soft = ndimage.gaussian_filter(mask.astype(float), 1.5)
        tone = 0.25 + 0.75 * lum
        image = tint(tone * soft)
        width = round(height * image.width / image.height)
        frames.append(image.resize((width, height), Image.LANCZOS))
    return frames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["photos", "video"])
    parser.add_argument("source")
    parser.add_argument("out")
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--rotate", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=0)
    parser.add_argument("--frames", type=int, default=16)
    parser.add_argument("--crop", default="0,0,1,1")
    parser.add_argument("--height", type=int, default=280)
    args = parser.parse_args()

    if args.kind == "photos":
        frames = photo_frames(args.source, args.size, args.rotate)
    else:
        crop = [float(v) for v in args.crop.split(",")]
        frames = video_frames(args.source, args.start, args.end, args.frames, crop, args.height)

    w, h = frames[0].size
    sheet = Image.new("RGB", (w * len(frames), h))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * w, 0))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    sheet.save(args.out, optimize=True)
    print(f"frames={len(frames)} frame={w}x{h} sheet={sheet.width}x{sheet.height} "
          f"bytes={os.path.getsize(args.out)}")


if __name__ == "__main__":
    main()
