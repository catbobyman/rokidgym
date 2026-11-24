"""生成字符画跑步帧，输出为 AIUI 页面可以 import 的 JS 模块。

两种来源：
  1. 默认：内置的 3D 人体模型。按跑步的关节角度摆姿势，打一盏灯做明暗，
     再把每个字符格子的平均亮度映射成字符。
  2. --from-photos 目录：真人连拍照片（深色背景、人物较亮，按文件名排序）。
     先把人物从背景里抠出来，各帧按上半身对齐，再转成字符帧。
     --rotate N 可以把第 N 帧挪到最前，让脚落地的那一帧对上拍点。
  3. --from-video 文件：浅色背景的实拍视频（例如白墙前的器械训练）。
     取 --start 到 --end 帧之间的一个完整动作，均匀抽 --frames 帧；--crop 用比例裁掉不要的部分。
     例：--from-video ../assets-src/gym/lat-pulldown.webm --start 106 --end 193 --frames 16
         --crop 0.08,0,0.84,0.88 --cols 28 --rows 28 --prefix PULLDOWN
  4. --from-images 目录：已经处理干净的图片，不抠图，直接按亮度转换；浅色背景加 --invert。

用法：
  python make_runner_frames.py --out ../my-agent/lib/runner-frames.js
  python make_runner_frames.py --from-photos ../assets-src/muybridge-run --rotate 2 --out ../my-agent/lib/runner-frames.js
"""
import argparse
import json
import math
import os

import numpy as np

RAMP = " .:-=+*#%@"   # 由暗到亮
COLS, ROWS = 52, 26   # 人物占用的字符格数
CELL_ASPECT = 0.5     # 字符格 宽 / 高（AIUI 运行时的等宽字体实测约 0.5em 宽，行高 1em）
FRAMES = 16           # 一个跑步周期的帧数


# ---------------------------------------------------------------- 姿势

def rad(deg):
    return deg * math.pi / 180.0


def wrap_dist(a, b):
    """相位在 0..1 环上的距离"""
    d = abs((a - b) % 1.0)
    return min(d, 1.0 - d)


def leg_angles(phase):
    """返回 (髋角, 膝屈角, 踝跖屈角)，单位度。phase=0 为该腿前摆到最前、即将落地。"""
    p = phase % 1.0
    hip = 12 + 38 * math.cos(2 * math.pi * p)
    knee = 22 + 14 * math.exp(-(wrap_dist(p, 0.14) / 0.09) ** 2)
    u = min(max((p - 0.50) / 0.44, 0.0), 1.0)
    knee += 88 * math.sin(math.pi * u) ** 1.2
    plantar = 30 * math.exp(-(wrap_dist(p, 0.5) / 0.1) ** 2)
    plantar -= 8 * math.exp(-(wrap_dist(p, 0.0) / 0.08) ** 2)
    return hip, knee, plantar


def sag(angle_deg, length):
    """矢状面内，从竖直向下起算、向前为正的方向向量"""
    a = rad(angle_deg)
    return np.array([math.sin(a) * length, -math.cos(a) * length, 0.0])


def rot_y(v, deg):
    a = rad(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([v[0] * c - v[2] * s, v[1], v[0] * s + v[2] * c])


def build_pose(phase, ground=None):
    """返回若干 (a, b, ra, rb) 的锥形胶囊体，描述整个人体。x 向前，y 向上，z 朝向镜头。"""
    parts = []
    pelvis = np.array([0.0, 0.95, 0.0])
    lean = 9.0
    spine = np.array([math.sin(rad(lean)), math.cos(rad(lean)), 0.0])
    twist = 12 * math.cos(2 * math.pi * phase)

    chest = pelvis + 0.30 * spine
    neck = pelvis + 0.53 * spine
    head = neck + np.array([0.035, 0.17, 0.0])

    parts.append((pelvis + np.array([0, 0, -0.07]), pelvis + np.array([0, 0, 0.07]), 0.115, 0.115))
    parts.append((pelvis, chest, 0.125, 0.150))
    parts.append((chest, neck - 0.06 * spine, 0.150, 0.125))
    parts.append((neck, head - np.array([0, 0.06, 0]), 0.055, 0.055))
    parts.append((head - np.array([0.0, 0.025, 0.0]), head + np.array([0.01, 0.035, 0.0]), 0.098, 0.105))

    lowest = 1e9
    for side, offset in ((1, 0.0), (-1, 0.5)):       # 右侧（靠近镜头）、左侧
        p = phase + offset
        # 腿
        hip_a, knee_a, plantar = leg_angles(p)
        hip = pelvis + np.array([0.0, -0.02, 0.095 * side])
        knee = hip + sag(hip_a, 0.44)
        ankle = knee + sag(hip_a - knee_a, 0.43)
        toe = ankle + sag(hip_a - knee_a + 90 - plantar, 0.19)
        heel = ankle - sag(hip_a - knee_a + 90 - plantar, 0.05)
        parts.append((hip, knee, 0.088, 0.058))
        parts.append((knee, ankle, 0.060, 0.036))
        parts.append((heel, toe, 0.042, 0.030))
        lowest = min(lowest, heel[1] - 0.042, toe[1] - 0.030)

        # 手臂：与同侧腿反相
        swing = 8 - 34 * math.cos(2 * math.pi * p)
        flex = 85 - 15 * math.cos(2 * math.pi * p)
        shoulder = neck + rot_y(np.array([0.0, -0.04, 0.195 * side]), twist)
        elbow = shoulder + sag(swing, 0.29) + np.array([0, 0, 0.02 * side])
        wrist = elbow + sag(swing + flex, 0.25)
        hand = wrist + sag(swing + flex, 0.07)
        parts.append((neck - np.array([0, 0.03, 0]), shoulder, 0.07, 0.062))
        parts.append((shoulder, elbow, 0.055, 0.043))
        parts.append((elbow, wrist, 0.043, 0.032))
        parts.append((wrist, hand, 0.038, 0.036))

    if ground is None:
        return lowest
    # 地面取整个周期里脚的最低点（腾空的帧会自然离地），再整体转向镜头一点，露出身体的厚度
    shift = np.array([0.0, -ground, 0.0])
    yaw = 24.0
    return [(rot_y(a + shift, yaw), rot_y(b + shift, yaw), ra, rb) for a, b, ra, rb in parts]


# ---------------------------------------------------------------- 渲染

def scene_sdf(points, parts, k=0.03):
    """所有部件的平滑并集距离场"""
    dist = None
    for a, b, ra, rb in parts:
        ab = b - a
        denom = float(ab @ ab) or 1e-9
        h = np.clip(((points - a) @ ab) / denom, 0.0, 1.0)
        d = np.linalg.norm(points - (a + h[:, None] * ab), axis=1) - (ra + (rb - ra) * h)
        if dist is None:
            dist = d
        else:
            hh = np.maximum(k - np.abs(dist - d), 0.0) / k
            dist = np.minimum(dist, d) - hh * hh * k * 0.25
    return dist


def render_brightness(parts, sub_x=4, sub_y=6):
    """正交投影 + 球面步进，返回 ROWS x COLS 的亮度（0..1）"""
    world_h = 1.90
    cell_h = world_h / ROWS
    cell_w = cell_h * CELL_ASPECT
    world_w = cell_w * COLS
    nx, ny = COLS * sub_x, ROWS * sub_y
    xs = (np.arange(nx) + 0.5) / nx * world_w - world_w / 2 + 0.03
    ys = world_h - 0.04 - (np.arange(ny) + 0.5) / ny * world_h
    gx, gy = np.meshgrid(xs, ys)
    origin = np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, 1.5)], axis=1)
    t = np.zeros(gx.size)
    direction = np.array([0.0, 0.0, -1.0])
    hit = np.zeros(gx.size, dtype=bool)
    alive = np.ones(gx.size, dtype=bool)
    for _ in range(56):
        idx = np.nonzero(alive)[0]
        if idx.size == 0:
            break
        d = scene_sdf(origin[idx] + t[idx, None] * direction, parts)
        t[idx] += d * 0.9
        done = d < 0.003
        hit[idx[done]] = True
        alive[idx[done]] = False
        alive[idx[t[idx] > 3.0]] = False

    shade = np.zeros(gx.size)
    idx = np.nonzero(hit)[0]
    if idx.size:
        p = origin[idx] + t[idx, None] * direction
        eps = 0.004
        normal = np.zeros_like(p)
        for axis in range(3):
            step = np.zeros(3)
            step[axis] = eps
            normal[:, axis] = scene_sdf(p + step, parts) - scene_sdf(p - step, parts)
        normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9
        light = np.array([0.30, 0.78, 0.55])
        light /= np.linalg.norm(light)
        lambert = np.clip(normal @ light, 0.0, 1.0)
        depth = 0.72 + 0.28 * np.clip((p[:, 2] + 0.30) / 0.60, 0.0, 1.0)   # 远侧肢体稍暗
        shade[idx] = (0.20 + 0.80 * lambert) * depth

    shade = shade.reshape(ROWS, sub_y, COLS, sub_x)
    mask = hit.reshape(ROWS, sub_y, COLS, sub_x).astype(float)
    cover = mask.mean(axis=(1, 3))
    value = shade.mean(axis=(1, 3))
    value[cover < 0.10] = 0.0
    # 每格内左右、上下两半的覆盖率之差，用来判断轮廓的走向
    gx = mask[:, :, :, sub_x // 2:].mean(axis=(1, 3)) - mask[:, :, :, :sub_x // 2].mean(axis=(1, 3))
    gy = mask[:, sub_y // 2:, :, :].mean(axis=(1, 3)) - mask[:, :sub_y // 2, :, :].mean(axis=(1, 3))
    return value, cover, gx, gy


def segment_photo(path, head=None):
    """返回 (亮度, 人物蒙版, 背景亮度)。针对暗背景上有细网格线、底部有亮色跑道的连拍照片。"""
    from PIL import Image, ImageFilter
    from scipy import ndimage
    im = Image.open(path).convert("L")
    w, h = im.size
    lum = np.asarray(im, dtype=float) / 255.0
    smooth = np.asarray(im.filter(ImageFilter.MedianFilter(7)), dtype=float) / 255.0   # 中值滤波抹掉细网格线
    cut = int(h * 0.872)                    # 跑道和刻度条在这条线以下
    edge = int(w * 0.04)
    smooth[cut:, :] = 0
    smooth[:, :edge] = 0
    smooth[:, w - edge:] = 0
    background = float(np.median(smooth[:cut]))
    mask = ndimage.binary_opening(smooth > background + 0.085)
    labels, count = ndimage.label(mask)
    if count:
        sizes = ndimage.sum(mask, labels, range(1, count + 1))
        keep = np.zeros(count + 1, bool)
        keep[1:] = sizes > 0.12 * sizes.max()            # 丢掉零碎的小亮块
        mask = keep[labels]
    mask = ndimage.binary_closing(mask, iterations=2)
    # 贴着地面的细横线不是脚：用竖直方向的开运算去掉
    floor = int(h * 0.80)
    mask[floor:] = ndimage.binary_opening(mask[floor:], structure=np.ones((7, 1), bool))
    labels, count = ndimage.label(mask)
    if count > 1:                                        # 开运算后剩下的地面碎块
        sizes = ndimage.sum(mask, labels, range(1, count + 1))
        keep = np.zeros(count + 1, bool)
        keep[1:] = sizes > 0.12 * sizes.max()
        mask = keep[labels]
    # 头部在这类照片里和背景差不多暗，按亮度抠不出来：用人工标注的头部位置补一个椭圆
    if head is not None:
        hx, hy = head[0] * w, head[1] * h
        rx, ry = 0.050 * w, 0.047 * h
        # 在标注点附近找偏暗的头发，把中心往它那边修正一半
        r0, r1 = max(int(hy - ry * 1.6), 0), int(hy + ry * 1.6)
        c0, c1 = max(int(hx - rx * 1.6), 0), int(hx + rx * 1.6)
        dark = smooth[r0:r1, c0:c1] < background - 0.05
        if dark.sum() > 40:
            dy, dx = np.nonzero(dark)
            hx = 0.5 * hx + 0.5 * (c0 + dx.mean())
            hy = 0.5 * hy + 0.5 * (r0 + dy.mean())
        yy, xx = np.mgrid[0:h, 0:w]
        mask = mask | (((xx - hx) / rx) ** 2 + ((yy - hy) / ry) ** 2 <= 1.0)
        mask = ndimage.binary_closing(mask, iterations=3)
    # 只补小孔，保留手臂和躯干之间的空隙
    holes = ndimage.binary_fill_holes(mask) & ~mask
    hole_labels, hole_count = ndimage.label(holes)
    if hole_count:
        hole_sizes = ndimage.sum(holes, hole_labels, range(1, hole_count + 1))
        small = np.zeros(hole_count + 1, bool)
        small[1:] = hole_sizes < 60
        mask = mask | small[hole_labels]
    return lum, mask, background


def photos_cells(folder, sub_x=4, sub_y=6):
    """把一组连拍照片变成和 render_brightness 相同格式的 (亮度, 覆盖率, gx, gy)"""
    from PIL import Image
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")))
    heads = {}
    heads_file = os.path.join(folder, "heads.json")      # 可选：{"文件名": [x 比例, y 比例]}
    if os.path.exists(heads_file):
        with open(heads_file, encoding="utf-8") as f:
            heads = json.load(f)
    shots = [segment_photo(os.path.join(folder, n), heads.get(n)) for n in names]

    # 竖直方向所有帧共用一个窗口，保留真实的身体起伏；水平方向每帧按上半身重心对齐
    tops = [np.nonzero(m)[0].min() for _, m, _ in shots]
    bottoms = [np.nonzero(m)[0].max() for _, m, _ in shots]
    top, bottom = min(tops), max(bottoms)
    height = (bottom - top) * 1.10
    y0 = top - (bottom - top) * 0.05
    width = height * COLS * CELL_ASPECT / ROWS
    out = []
    for lum, mask, background in shots:
        ys, xs = np.nonzero(mask)
        upper = ys < ys.min() + (ys.max() - ys.min()) * 0.55
        center = xs[upper].mean()
        box = (center - width / 2, y0, center + width / 2, y0 + height)
        size = (COLS * sub_x, ROWS * sub_y)
        m = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).transform(
            size, Image.EXTENT, box, Image.BILINEAR), dtype=float) / 255.0
        m = (m > 0.5).astype(float)
        l = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).transform(
            size, Image.EXTENT, box, Image.BILINEAR), dtype=float) / 255.0
        bright = np.percentile(lum[mask], 97)
        tone = 0.30 + 0.70 * np.clip((l - background) / max(bright - background, 1e-6), 0.0, 1.0)
        shade = (tone * m).reshape(ROWS, sub_y, COLS, sub_x)
        cells = m.reshape(ROWS, sub_y, COLS, sub_x)
        cover = cells.mean(axis=(1, 3))
        value = shade.mean(axis=(1, 3))
        value[cover < 0.10] = 0.0
        gx = cells[:, :, :, sub_x // 2:].mean(axis=(1, 3)) - cells[:, :, :, :sub_x // 2].mean(axis=(1, 3))
        gy = cells[:, sub_y // 2:, :, :].mean(axis=(1, 3)) - cells[:, :sub_y // 2, :, :].mean(axis=(1, 3))
        out.append((value, cover, gx, gy))
    return out


def video_cells(path, start, end, count, crop, sub_x=4, sub_y=6):
    """浅色背景的实拍视频：抽帧、裁剪、抠出前景，返回每帧的 (亮度, 覆盖率, gx, gy)。

    比背景暗或者颜色明显的像素算作前景，所以人和器械都会被画出来；
    肤色和浅色头发最亮，深色衣服和器械较暗但保底可见。
    """
    import cv2
    from scipy import ndimage
    capture = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    end = end if end > 0 else len(frames)
    picks = [int(round(start + (end - start) * i / count)) for i in range(count)]
    x0, y0, x1, y1 = crop
    out = []
    for index in picks:
        frame = frames[min(index, len(frames) - 1)]
        h, w = frame.shape[:2]
        frame = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        frame = cv2.resize(frame, (COLS * sub_x, ROWS * sub_y), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(float) / 255.0
        lum, sat = hsv[..., 2], hsv[..., 1]
        mask = ndimage.binary_opening((lum < 0.60) | (sat > 0.22)).astype(float)
        tone = 0.32 + 0.68 * lum
        shade = (tone * mask).reshape(ROWS, sub_y, COLS, sub_x)
        cells = mask.reshape(ROWS, sub_y, COLS, sub_x)
        cover = cells.mean(axis=(1, 3))
        value = shade.mean(axis=(1, 3))
        value[cover < 0.10] = 0.0
        gx = cells[:, :, :, sub_x // 2:].mean(axis=(1, 3)) - cells[:, :, :, :sub_x // 2].mean(axis=(1, 3))
        gy = cells[:, sub_y // 2:, :, :].mean(axis=(1, 3)) - cells[:, :sub_y // 2, :, :].mean(axis=(1, 3))
        out.append((value, cover, gx, gy))
    return out


def images_brightness(folder, invert):
    from PIL import Image
    names = sorted(n for n in os.listdir(folder) if n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")))
    out = []
    for name in names:
        img = Image.open(os.path.join(folder, name)).convert("L").resize((COLS, ROWS), Image.LANCZOS)
        v = np.asarray(img, dtype=float) / 255.0
        out.append(1.0 - v if invert else v)
    return out


def to_chars(value, cover=None, gx=None, gy=None):
    """身体内部按亮度选字符；落在轮廓上的格子按轮廓走向选 | / \ _ -，让外形更清晰。"""
    rows = []
    top = len(RAMP) - 1
    for r in range(value.shape[0]):
        line = ""
        for c in range(value.shape[1]):
            v = value[r, c]
            if v <= 0.0:
                line += " "
                continue
            if cover is not None and cover[r, c] < 0.72:
                nx, ny = gx[r, c] * 2.0, gy[r, c]      # 格子高是宽的两倍，换算成等比例的法线
                if math.hypot(nx, ny) > 0.30:
                    if abs(nx) > 2.2 * abs(ny):
                        line += "|"
                    elif abs(ny) > 2.2 * abs(nx):
                        line += "_" if ny > 0 else "-"
                    else:
                        line += "/" if nx * ny > 0 else "\\"
                    continue
            line += RAMP[max(1, min(top, int(math.ceil((v ** 0.6) * top))))]
        rows.append(line)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-photos")
    ap.add_argument("--from-video")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=0)
    ap.add_argument("--frames", type=int, default=16)
    ap.add_argument("--crop", default="0,0,1,1")
    ap.add_argument("--cols", type=int)
    ap.add_argument("--rows", type=int)
    ap.add_argument("--prefix", default="RUNNER")
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--from-images")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--preview")
    args = ap.parse_args()

    global COLS, ROWS
    COLS, ROWS = args.cols or COLS, args.rows or ROWS

    if args.from_video:
        crop = [float(v) for v in args.crop.split(",")]
        rendered = video_cells(args.from_video, args.start, args.end, args.frames, crop)
        peak = max(float(v.max()) for v, _, _, _ in rendered) or 1.0
        frames = [to_chars(np.clip(v / peak, 0.0, 1.0), cover, gx, gy) for v, cover, gx, gy in rendered]
    elif args.from_photos:
        rendered = photos_cells(args.from_photos)
        peak = max(float(v.max()) for v, _, _, _ in rendered) or 1.0
        frames = [to_chars(np.clip(v / peak, 0.0, 1.0), cover, gx, gy) for v, cover, gx, gy in rendered]
    elif args.from_images:
        values = images_brightness(args.from_images, args.invert)
        peak = max(float(v.max()) for v in values) or 1.0
        frames = [to_chars(np.clip(v / peak, 0.0, 1.0)) for v in values]
    else:
        ground = min(build_pose(i / FRAMES) for i in range(FRAMES))
        rendered = [render_brightness(build_pose(i / FRAMES, ground)) for i in range(FRAMES)]
        peak = max(float(v.max()) for v, _, _, _ in rendered) or 1.0
        frames = [to_chars(np.clip(v / peak, 0.0, 1.0), cover, gx, gy) for v, cover, gx, gy in rendered]

    if args.rotate:
        frames = frames[args.rotate:] + frames[:args.rotate]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("// 由 tools/make_runner_frames.py 生成，请勿手改。\n")
        f.write("// 每帧是 %d 行、每行 %d 个字符；一个动作周期共 %d 帧。\n" % (ROWS, COLS, len(frames)))
        f.write("export const %s_COLS = %d;\n" % (args.prefix, COLS))
        f.write("export const %s_ROWS = %d;\n" % (args.prefix, ROWS))
        f.write("export const %s_FRAMES = %s;\n" % (args.prefix, json.dumps(frames, indent=1)))
    if args.preview:
        with open(args.preview, "w", encoding="utf-8") as f:
            for i, frame in enumerate(frames):
                f.write("--- frame %d\n" % i)
                f.write("\n".join("|" + row + "|" for row in frame) + "\n")
    print("wrote %d frames to %s" % (len(frames), args.out))


if __name__ == "__main__":
    main()
