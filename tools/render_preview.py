"""渲染一张近似效果图（preview.png），用来快速检查配色和图标大小。

不是真机截图：按 game.wxss 的参数用 Pillow 复刻，
牌堆数据直接从 game/logic.js 里跑出来（需要 node），拿不到就退化成近似牌局。

用法：
    python tools/render_preview.py            # 默认 alpha 0.24、seed 7
    python tools/render_preview.py 0.30 12    # 指定压暗程度和牌局种子
"""

import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(ROOT, "assets", "icons")

W, H = 750, 1334
TILE = 84
PAD = 6  # 与 .tile 的 padding 一致
PAGE_PAD = 24

# 与 game.wxss 的 .tile--* 一一对应：(渐变起, 渐变止, 描边, 底部投影)
COLORS = {
    "carrot": ("#ffefe0", "#ffd9bf", "#f2c69b", "#e2ab78"),
    "grass": ("#eef9e3", "#dcefcf", "#bbdca0", "#a5ca8a"),
    "wool": ("#f3f2fb", "#e4e1f1", "#c9c4de", "#b1abcb"),
    "bell": ("#fff8d3", "#ffe9a6", "#f0d27c", "#dcbb63"),
    "milk": ("#dcecfa", "#c6dff5", "#9ec6e6", "#86b1d5"),
    "corn": ("#fffae2", "#fff0bc", "#eddc97", "#d9c67c"),
    "mushroom": ("#fdede6", "#f8d8cc", "#e9b6a6", "#d79e8c"),
    "apple": ("#fbd9dc", "#f4bfc6", "#e0929c", "#cc7d88"),
    "sun": ("#fff5d8", "#ffe4a6", "#f3cd82", "#dfb663"),
    "clover": ("#e7f7f0", "#cdebdf", "#a8d8c6", "#90c4b1"),
}

LAYERS = [
    {"cols": 6, "rows": 5, "ox": 0, "oy": 0},
    {"cols": 5, "rows": 4, "ox": 1, "oy": 1},
    {"cols": 4, "rows": 3, "ox": 2, "oy": 2},
    {"cols": 2, "rows": 2, "ox": 4, "oy": 3},
]

ICONS = {}


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def icon_of(name):
    if name not in ICONS:
        img = Image.open(os.path.join(ICON_DIR, name + ".png")).convert("RGBA")
        ICONS[name] = img.resize((TILE - 2 * PAD, TILE - 2 * PAD), Image.LANCZOS)
    return ICONS[name]


def fallback_tiles():
    """拿不到 node 时的近似牌局：布局真、牌型是循环分配的。"""
    types = list(COLORS.keys())
    tiles = []
    tid = 1
    for layer, cfg in enumerate(LAYERS):
        for r in range(cfg["rows"]):
            for c in range(cfg["cols"]):
                ux = cfg["ox"] + c * 2
                uy = cfg["oy"] + r * 2
                tiles.append(
                    {
                        "id": tid,
                        "layer": layer,
                        "left": ux * TILE // 2,
                        "top": uy * TILE // 2,
                        "z": layer * 1000 + r * 10 + c,
                        "type": types[(tid - 1) % len(types)],
                    }
                )
                tid += 1
    return tiles


def load_tiles(seed):
    node = os.environ.get("NODE_BIN") or shutil.which("node") or shutil.which("node.exe")
    if not node:
        print("提示：没找到 node，用近似牌局渲染（配色和尺寸仍然准确）")
        return fallback_tiles()

    script = (
        "const l=require('./game/logic');"
        "const g=l.createGame({seed:%d});"
        "process.stdout.write(JSON.stringify(g.tiles));" % seed
    )
    try:
        out = subprocess.run(
            [node, "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
        print("提示：node 执行失败，用近似牌局渲染\n", (out.stderr or "")[:300])
    except Exception as exc:  # noqa: BLE001
        print("提示：调用 node 出错，用近似牌局渲染：", exc)
    return fallback_tiles()


def covered_ids(tiles):
    result = set()
    for t in tiles:
        for o in tiles:
            if o["layer"] > t["layer"] and abs(o["left"] - t["left"]) < TILE and abs(o["top"] - t["top"]) < TILE:
                result.add(t["id"])
                break
    return result


def draw_tile(canvas, x, y, tile, covered, alpha):
    size = TILE + 20
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg1, bg2, border, shadow = COLORS.get(tile["type"], COLORS["corn"])

    d = ImageDraw.Draw(layer)
    # 底部投影
    d.rounded_rectangle([10, 16, 10 + TILE, 16 + TILE], radius=14, fill=hex_rgb(shadow) + (150,))

    # 牌面：先铺竖向渐变，再用圆角遮罩裁出来
    grad = Image.new("RGB", (TILE, TILE))
    gd = ImageDraw.Draw(grad)
    c1, c2 = hex_rgb(bg1), hex_rgb(bg2)
    for row in range(TILE):
        k = row / max(1, TILE - 1)
        color = tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))
        gd.line([(0, row), (TILE, row)], fill=color)

    mask = Image.new("L", (TILE, TILE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, TILE - 1, TILE - 1], radius=14, fill=255)
    face = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
    face.paste(grad, (0, 0), mask)
    layer.alpha_composite(face, (10, 10))

    d.rounded_rectangle(
        [10, 10, 10 + TILE, 10 + TILE], radius=14, outline=hex_rgb(border) + (255,), width=2
    )
    canvas.alpha_composite(layer, (x - 10, y - 10))

    canvas.alpha_composite(icon_of(tile["type"]), (x + PAD, y + PAD))

    if covered:
        over = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(over).rounded_rectangle(
            [10, 10, 10 + TILE, 10 + TILE], radius=14, fill=(0, 0, 0, int(round(alpha * 255)))
        )
        canvas.alpha_composite(over, (x - 10, y - 10))


def render_board(tiles, alpha):
    covered = covered_ids(tiles)
    bw = max(t["left"] for t in tiles) + TILE
    bh = max(t["top"] for t in tiles) + TILE
    canvas = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    for t in sorted(tiles, key=lambda item: item["z"]):
        draw_tile(canvas, t["left"], t["top"], t, t["id"] in covered, alpha)
    return canvas


def gradient_bg(width, height):
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    top, mid, bottom = (127, 216, 88), (83, 176, 67), (63, 145, 66)
    for y in range(height):
        t = y / height
        if t < 0.45:
            k = t / 0.45
            color = tuple(int(top[i] + (mid[i] - top[i]) * k) for i in range(3))
        else:
            k = (t - 0.45) / 0.55
            color = tuple(int(mid[i] + (bottom[i] - mid[i]) * k) for i in range(3))
        d.line([(0, y), (width, y)], fill=color)
    return img.convert("RGBA")


def main():
    alpha = float(sys.argv[1]) if len(sys.argv) > 1 else 0.24
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7

    tiles = load_tiles(seed)
    img = gradient_bg(W, H)
    draw = ImageDraw.Draw(img)

    font_big = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 34)
    font_mid = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)

    hud_y = 12
    draw.text((PAGE_PAD + 6, hud_y + 26), "剩余", font=font_mid, fill=(240, 255, 235))
    draw.text((PAGE_PAD + 74, hud_y + 12), str(len(tiles)), font=font_big, fill=(255, 255, 255))
    draw.text((W // 2 - 78, hud_y + 14), "羊了个羊", font=font_big, fill=(255, 255, 255))
    chip = [W - PAGE_PAD - 132, hud_y + 14, W - PAGE_PAD, hud_y + 66]
    draw.rounded_rectangle(chip, radius=26, fill=(255, 255, 255, 255))
    draw.text((chip[0] + 34, chip[1] + 7), "音效", font=font_mid, fill=(47, 107, 42))

    bw = max(t["left"] for t in tiles) + TILE
    bh = max(t["top"] for t in tiles) + TILE
    board = render_board(tiles, alpha)

    cell, gap = 72, 8
    slot_w = 7 * cell + 6 * gap + 24
    slot_h = cell + 24

    stage_top = 12 + 72
    stage_bottom = H - 36
    group_h = bh + 44 + slot_h
    board_y = stage_top + (stage_bottom - stage_top - group_h) // 2
    sy = board_y + bh + 44
    sx = (W - slot_w) // 2

    img.alpha_composite(board, ((W - bw) // 2, board_y))

    bar = Image.new("RGBA", (slot_w, slot_h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rounded_rectangle([0, 0, slot_w, slot_h], radius=24, fill=(124, 79, 34, 255))
    bd.rounded_rectangle([2, 2, slot_w - 2, slot_h // 2 + 6], radius=22, fill=(169, 116, 63, 255))
    for i in range(7):
        cx = 12 + i * (cell + gap)
        bd.rounded_rectangle([cx, 12, cx + cell, 12 + cell], radius=12, fill=(92, 58, 24, 255))
    img.alpha_composite(bar, (sx, sy))

    out = os.path.join(ROOT, "preview.png")
    img.convert("RGB").save(out, "PNG")
    print("saved", out, img.size, "| alpha =", alpha, "| seed =", seed)


if __name__ == "__main__":
    main()
