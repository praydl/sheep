"""生成《羊了个羊》复刻版所需的全部素材。

只用 Pillow + numpy，不依赖任何外部图片/音频文件：
  assets/icons/*.png   11 个牌面图标（羊 + 10 种牌）
  assets/bgm.wav       8 秒循环背景音乐
  assets/sfx/*.wav     点击 / 消除 / 胜利 / 失败 音效

用法：python tools/gen_assets.py
"""

import math
import os
import struct
import wave

import numpy as np
from PIL import Image, ImageDraw

SR = 22050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(ROOT, "assets", "icons")
SFX_DIR = os.path.join(ROOT, "assets", "sfx")

BASE = 192          # 输出尺寸
SCALE = 4           # 超采样倍数，先画大图再缩小，边缘才平滑
W = BASE * SCALE    # 768

# 调色板
ORANGE = (245, 154, 35)
ORANGE_DARK = (211, 120, 18)
LEAF = (104, 190, 78)
LEAF_DARK = (66, 150, 52)
WHITE = (255, 255, 255)
CREAM = (255, 248, 236)
WOOL_SHADE = (228, 222, 211)
WOOL_LINE = (198, 190, 176)
GOLD = (255, 201, 60)
GOLD_DARK = (235, 160, 0)
BLUE = (111, 168, 220)
BLUE_DARK = (74, 126, 187)
YELLOW = (255, 211, 77)
YELLOW_DARK = (238, 178, 8)
RED = (226, 74, 62)
RED_DARK = (192, 52, 44)
BROWN = (141, 110, 99)
PINK = (255, 170, 160)
DARK = (58, 48, 42)


def new_canvas():
    return Image.new("RGBA", (W, W), (0, 0, 0, 0))


def save_icon(img, name):
    """裁掉透明边距，再按最长边归一化到画布的 94%，保证每个图标都尽量大且观感一致。"""
    box = img.split()[3].getbbox()
    content = img.crop(box) if box else img

    target = int(round(BASE * 0.94))
    w, h = content.size
    scale = target / float(max(w, h))
    size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    content = content.resize(size, Image.LANCZOS)

    canvas = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    canvas.paste(content, ((BASE - size[0]) // 2, (BASE - size[1]) // 2))

    path = os.path.join(ICON_DIR, name + ".png")
    canvas.save(path, "PNG", optimize=True)
    return path


def paste_layer(base, layer):
    base.alpha_composite(layer)


def clip_ellipse(layer, bbox):
    """把图层裁成椭圆形状（用来画玉米粒网格这种会出界的东西）。"""
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).ellipse(bbox, fill=255)
    alpha = layer.split()[3].point(lambda v: v)
    layer.putalpha(Image.composite(alpha, Image.new("L", (W, W), 0), mask))


# ------------------------------- 各个图标 -------------------------------

def icon_carrot():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    # 叶子
    d.polygon([(384, 300), (250, 96), (348, 168)], fill=LEAF_DARK)
    d.polygon([(384, 300), (518, 96), (420, 168)], fill=LEAF)
    d.line([(384, 300), (384, 110)], fill=LEAF, width=34)
    # 萝卜身体
    d.polygon([(300, 268), (468, 268), (430, 596), (384, 664), (338, 596)], fill=ORANGE)
    # 纹路
    for i, y in enumerate((360, 440, 520)):
        d.line([(330 + i * 8, y), (438 - i * 8, y - 14)], fill=ORANGE_DARK, width=12)
    # 顶部圆角
    d.ellipse([300, 232, 468, 312], fill=ORANGE)
    return img


def icon_grass():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    # 根部土堆
    d.ellipse([250, 596, 518, 700], fill=LEAF_DARK)
    # 草叶彼此重叠，放大后才会读成「一丛草」而不是一排锯齿
    blades = (
        (-72, 236, 46, LEAF_DARK),
        (-28, 300, 52, LEAF),
        (20, 320, 50, LEAF_DARK),
        (68, 250, 44, LEAF),
    )
    for offset, height, half, color in blades:
        x = 384 + offset
        d.polygon(
            [
                (x - half, 660),
                (x - int(half * 0.55), 660 - int(height * 0.55)),
                (x, 660 - height),
                (x + int(half * 0.55), 660 - int(height * 0.55)),
                (x + half, 660),
            ],
            fill=color,
        )
    # 两片亮色高光叶
    d.polygon([(384 - 16, 660), (384 - 4, 400), (384 + 14, 660)], fill=(146, 214, 110))
    return img


def icon_wool():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    # 米色牌面上纯白会糊掉，所以先用深一档的轮廓打底，再叠主体
    d.ellipse([208, 238, 560, 590], fill=WOOL_LINE)
    d.ellipse([220, 250, 548, 578], fill=WOOL_SHADE)
    d.ellipse([236, 266, 532, 562], fill=(248, 244, 236))
    for bbox, start, end in (
        ([262, 292, 506, 536], 200, 340),
        ([262, 292, 506, 536], 20, 160),
        ([292, 322, 476, 506], 160, 300),
    ):
        d.arc(bbox, start, end, fill=WOOL_LINE, width=14)
    d.arc([300, 470, 560, 620], 200, 320, fill=WOOL_LINE, width=14)
    d.ellipse([286, 300, 356, 360], fill=(255, 255, 255))
    return img


def icon_bell():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.ellipse([344, 130, 424, 210], fill=GOLD_DARK)
    d.polygon(
        [(234, 470), (268, 300), (384, 186), (500, 300), (534, 470)],
        fill=GOLD,
    )
    d.rectangle([206, 462, 562, 520], fill=GOLD)
    d.ellipse([206, 486, 562, 560], fill=GOLD)
    d.ellipse([344, 520, 424, 600], fill=GOLD_DARK)
    d.ellipse([252, 320, 316, 384], fill=(255, 235, 170))
    return img


def icon_milk():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([288, 238, 480, 656], radius=44, fill=WHITE, outline=(226, 218, 200), width=6)
    d.rectangle([306, 150, 462, 250], fill=BLUE_DARK)
    d.rounded_rectangle([288, 250, 480, 300], radius=16, fill=BLUE)
    d.rounded_rectangle([288, 392, 480, 566], radius=14, fill=BLUE)
    d.rectangle([310, 436, 458, 470], fill=WHITE)
    d.rectangle([310, 496, 458, 520], fill=WHITE)
    return img


def icon_corn():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.polygon([(264, 350), (150, 250), (232, 520)], fill=LEAF_DARK)
    d.polygon([(504, 350), (618, 250), (536, 520)], fill=LEAF)
    d.ellipse([264, 210, 504, 640], fill=YELLOW)

    grid = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for y in range(250, 640, 58):
        gd.line([(240, y), (528, y)], fill=YELLOW_DARK, width=10)
    for x in range(-80, 100, 56):
        gd.line([(384 + x, 200), (384 + x, 646)], fill=YELLOW_DARK, width=10)
    clip_ellipse(grid, [264, 210, 504, 640])
    paste_layer(img, grid)
    return img


def icon_mushroom():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([338, 340, 430, 640], radius=46, fill=(255, 250, 242), outline=(226, 214, 196), width=6)
    d.pieslice([204, 176, 564, 536], 180, 360, fill=RED)
    d.ellipse([204, 300, 564, 400], fill=RED)
    for cx, cy, r in ((300, 300, 30), (400, 250, 34), (470, 330, 26), (350, 360, 22)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 236, 228))
    return img


def icon_apple():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([374, 160, 394, 300], fill=BROWN)
    d.polygon([(394, 236), (590, 176), (452, 316)], fill=LEAF)
    d.ellipse([214, 320, 434, 640], fill=RED)
    d.ellipse([334, 320, 554, 640], fill=RED)
    d.ellipse([214, 300, 434, 520], fill=RED)
    d.ellipse([334, 300, 554, 520], fill=RED)
    d.ellipse([254, 372, 330, 470], fill=PINK)
    return img


def icon_sun():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    cx, cy = 384, 400
    for i in range(8):
        angle = math.radians(i * 45)
        for sign in (-1, 1):
            a = angle + sign * 0.26
            p1 = (cx + math.cos(a) * 150, cy + math.sin(a) * 150)
            p2 = (cx + math.cos(a) * 300, cy + math.sin(a) * 300)
            p3 = (cx + math.cos(angle + sign * 0.44) * 150, cy + math.sin(angle + sign * 0.44) * 150)
            d.polygon([p1, p2, p3], fill=GOLD_DARK)
    d.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], fill=GOLD)
    d.ellipse([cx - 90, cy - 90, cx + 40, cy + 40], fill=(255, 233, 160))
    return img


def icon_clover():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.line([(384, 400), (430, 660)], fill=LEAF_DARK, width=22)
    for cx, cy in ((300, 320), (468, 320), (300, 486), (468, 486)):
        d.ellipse([cx - 96, cy - 96, cx + 96, cy + 96], fill=LEAF)
    d.ellipse([344, 364, 424, 444], fill=LEAF_DARK)
    for cx, cy in ((300, 320), (468, 320), (300, 486), (468, 486)):
        d.ellipse([cx - 36, cy - 36, cx + 36, cy + 36], fill=(140, 214, 116))
    return img


def icon_sheep():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    fluff = [
        (384, 230, 130),
        (270, 300, 110),
        (498, 300, 110),
        (300, 420, 110),
        (468, 420, 110),
    ]
    # 耳朵
    d.ellipse([150, 250, 260, 350], fill=WOOL_LINE)
    d.ellipse([160, 260, 250, 340], fill=CREAM)
    d.ellipse([508, 250, 618, 350], fill=WOOL_LINE)
    d.ellipse([518, 260, 608, 340], fill=CREAM)
    # 绒毛：先用轮廓色画一圈，再用白色盖住，形成描边，米色底上才看得见
    for cx, cy, r in fluff:
        d.ellipse([cx - r - 9, cy - r - 9, cx + r + 9, cy + r + 9], fill=WOOL_LINE)
    for cx, cy, r in fluff:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
    # 脸
    d.ellipse([300, 300, 468, 500], fill=CREAM)
    d.ellipse([300, 300, 468, 500], outline=(226, 214, 196), width=6)
    # 眼睛
    d.ellipse([334, 366, 372, 404], fill=DARK)
    d.ellipse([396, 366, 434, 404], fill=DARK)
    d.ellipse([344, 376, 358, 390], fill=WHITE)
    d.ellipse([406, 376, 420, 390], fill=WHITE)
    # 腮红 + 嘴
    d.ellipse([306, 420, 346, 450], fill=PINK)
    d.ellipse([422, 420, 462, 450], fill=PINK)
    d.arc([354, 414, 414, 470], 20, 160, fill=DARK, width=10)
    return img


ICONS = {
    "carrot": icon_carrot,
    "grass": icon_grass,
    "wool": icon_wool,
    "bell": icon_bell,
    "milk": icon_milk,
    "corn": icon_corn,
    "mushroom": icon_mushroom,
    "apple": icon_apple,
    "sun": icon_sun,
    "clover": icon_clover,
    "sheep": icon_sheep,
}


# ------------------------------- 音频合成 -------------------------------

def midi_to_freq(note):
    return 440.0 * (2 ** ((note - 69) / 12.0))


def envelope(n, rate):
    t = np.arange(n) / SR
    return np.exp(-t * rate)


def tone(freq, dur, vol, rate, harmonics=(1.0,), detune=0.0):
    n = int(dur * SR)
    if n <= 0:
        return np.zeros(0)
    t = np.arange(n) / SR
    wave_data = np.zeros(n)
    for i, amp in enumerate(harmonics):
        f = freq * (i + 1) * (1.0 + detune)
        wave_data += amp * np.sin(2 * np.pi * f * t)
    return wave_data * envelope(n, rate) * vol


def add_at(buf, start_sec, data):
    start = int(start_sec * SR)
    end = start + len(data)
    if start >= len(buf):
        return
    end = min(end, len(buf))
    buf[start:end] += data[: end - start]


def make_bgm():
    bpm = 120
    beat = 60.0 / bpm
    eighth = beat / 2
    bars = 4
    total = int(bars * 4 * beat * SR)
    buf = np.zeros(total)

    melody = [
        [72, 76, 79, 76, 74, 77, 79, 77],
        [74, 77, 81, 77, 72, 76, 79, 76],
        [79, 83, 86, 83, 81, 79, 77, 76],
        [74, 77, 81, 84, 79, 76, 72, 0],
    ]
    chords = [
        {"root": 48, "tones": [60, 64, 67]},
        {"root": 43, "tones": [55, 59, 62]},
        {"root": 45, "tones": [57, 60, 64]},
        {"root": 41, "tones": [53, 57, 60]},
    ]

    for bar in range(bars):
        chord = chords[bar]
        bar_start = bar * 4 * beat

        # 低音：每小节两个长音
        for k in range(2):
            note = chord["root"] + (7 if k == 1 else 0)
            add_at(
                buf,
                bar_start + k * 2 * beat,
                tone(midi_to_freq(note), 2 * beat, 0.22, 2.2, (1.0, 0.25)),
            )

        # 琶音
        for k in range(8):
            note = chord["tones"][k % 3] + 12
            add_at(buf, bar_start + k * eighth, tone(midi_to_freq(note), eighth * 1.6, 0.07, 13))

        # 主旋律
        for k in range(8):
            note = melody[bar][k]
            if not note:
                continue
            add_at(
                buf,
                bar_start + k * eighth,
                tone(midi_to_freq(note), eighth * 1.9, 0.24, 8.5, (1.0, 0.3, 0.12)),
            )

        # 轻打击：第一、三拍
        for k in (0, 2):
            n = int(0.05 * SR)
            noise = np.random.RandomState(bar * 10 + k).randn(n) * np.exp(-np.arange(n) / (0.008 * SR))
            add_at(buf, bar_start + k * beat, noise * 0.05)

    # 循环点淡入淡出，避免爆音
    fade = int(0.012 * SR)
    buf[:fade] *= np.linspace(0, 1, fade)
    buf[-fade:] *= np.linspace(1, 0, fade)
    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.85
    return buf


def make_tap():
    n = int(0.07 * SR)
    t = np.arange(n) / SR
    freq = 900 - 250 * (t / t[-1])
    wave_data = np.sin(2 * np.pi * freq * t) * np.exp(-t * 55)
    return wave_data * 0.5


def make_match():
    buf = np.zeros(int(0.34 * SR))
    add_at(buf, 0.0, tone(midi_to_freq(88), 0.30, 0.34, 11, (1.0, 0.35, 0.1)))
    add_at(buf, 0.05, tone(midi_to_freq(95), 0.28, 0.26, 11, (1.0, 0.3)))
    return buf


def make_win():
    buf = np.zeros(int(0.95 * SR))
    for i, note in enumerate((72, 76, 79, 84)):
        add_at(buf, i * 0.11, tone(midi_to_freq(note), 0.45, 0.28, 7, (1.0, 0.3, 0.12)))
    for note in (72, 76, 79, 84):
        add_at(buf, 0.45, tone(midi_to_freq(note), 0.5, 0.12, 4.5, (1.0, 0.2)))
    return buf


def make_lose():
    buf = np.zeros(int(0.8 * SR))
    for i, note in enumerate((67, 63, 60)):
        add_at(buf, i * 0.16, tone(midi_to_freq(note), 0.4, 0.26, 6, (1.0, 0.4), detune=0.004))
    return buf


def write_wav(path, data):
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak * 0.9
    pcm = (data * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return os.path.getsize(path)


def main():
    os.makedirs(ICON_DIR, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)

    for name, factory in ICONS.items():
        path = save_icon(factory(), name)
        print("icon  %-9s %6d bytes" % (name, os.path.getsize(path)))

    bgm = os.path.join(ROOT, "assets", "bgm.wav")
    size = write_wav(bgm, make_bgm())
    print("bgm   %-9s %6d bytes (%.2fs)" % ("bgm", size, size / (SR * 2)))

    for name, factory in (
        ("tap", make_tap),
        ("match", make_match),
        ("win", make_win),
        ("lose", make_lose),
    ):
        path = os.path.join(SFX_DIR, name + ".wav")
        size = write_wav(path, factory())
        print("sfx   %-9s %6d bytes" % (name, size))


if __name__ == "__main__":
    main()
