# -*- coding: utf-8 -*-
"""Tạo lại ảnh nền + hai mã QR cho giao diện lễ tân. Chạy: python gen_assets.py  (cần: pip install pillow qrcode)
Muốn dùng ảnh nền / QR riêng thì chỉ cần ghi đè các file PNG cùng tên."""
import math
import os
import random
import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
W, H = 1376, 768                                       # vùng nội dung của giao diện (ui_letan.py)
M = 30                                                 # lề trang trí quanh nội dung -> viền không bao giờ đè lên chữ
SW, SH = W + 2 * M, H + 2 * M                          # kích thước ảnh nền (1436 x 828)
WEBSITE = "https://hoianfairyvilla.com"
BANK_BIN, BANK_ACC = "970423", "10001689000"          # TPBank - số tài khoản 1000 1689 000
GOLD = (233, 216, 166)
MINT = (107, 255, 176)
LEAF = (52, 168, 104)
LEAF_DARK = (28, 110, 70)


def _leaf(d, cx, cy, length, width, ang, fill, vein=None):
    pts = []
    n = 16
    for i in range(n + 1):
        u = i / n
        pts.append((u * length, (width / 2) * math.sin(math.pi * u) ** 0.85))
    for i in range(n, -1, -1):
        u = i / n
        pts.append((u * length, -(width / 2) * math.sin(math.pi * u) ** 0.85))
    ca, sa = math.cos(ang), math.sin(ang)
    rot = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
    d.polygon(rot, fill=fill)
    if vein:
        d.line([(cx, cy), (cx + length * ca, cy + length * sa)], fill=vein, width=max(1, int(width / 9)))


def _bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def _vine(d, pts4, S, leaves=9, size=16, alpha=210):
    """Dây leo bằng đường cong Bezier, lá mọc xen kẽ hai bên."""
    seg = [_bezier(*pts4, i / 60) for i in range(61)]
    d.line(seg, fill=LEAF_DARK + (alpha,), width=int(2.4 * S), joint="curve")
    for k in range(leaves):
        t = (k + 0.7) / (leaves + 0.4)
        x, y = _bezier(*pts4, t)
        x2, y2 = _bezier(*pts4, min(1, t + 0.02))
        tang = math.atan2(y2 - y, x2 - x)
        side = 1 if k % 2 == 0 else -1
        sz = size * (1.0 - 0.45 * t) * S
        _leaf(d, x, y, sz, sz * 0.46, tang + side * 0.95, LEAF + (alpha,), MINT + (150,))


def _glow_layer(size, spots, blur):
    """spots: [(x, y, bán kính, màu RGBA)] -> lớp ánh sáng mờ."""
    g = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for x, y, r, c in spots:
        gd.ellipse((x - r, y - r, x + r, y + r), fill=c)
    return g.filter(ImageFilter.GaussianBlur(blur))


def background():
    S = 2                                              # vẽ gấp đôi rồi thu nhỏ cho mịn
    w, h = SW * S, SH * S
    grad = Image.linear_gradient("L").resize((w, h))
    img = ImageOps.colorize(grad, black=(13, 58, 38), white=(5, 24, 16)).convert("RGBA")
    # ánh sáng nền (bokeh lớn)
    img = Image.alpha_composite(img, _glow_layer((w, h), [
        (260 * S, 150 * S, 230 * S, MINT + (46,)), (760 * S, 640 * S, 300 * S, (60, 200, 130, 34)),
        (1230 * S, 700 * S, 210 * S, GOLD + (30,)), (1080 * S, 130 * S, 190 * S, MINT + (30,)),
        (430 * S, 400 * S, 240 * S, (80, 230, 160, 22))], 70 * S))
    d = ImageDraw.Draw(img, "RGBA")

    # vòng sáng mờ trang trí phía sau khối chữ bên trái (vẽ trên lớp riêng rồi làm mờ cho mịn, không răng cưa)
    cx, cy = (62 + 332 + M) * S, (380 + M) * S
    rings = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rings)
    for r, a, wd in ((330, 60, 5), (286, 44, 4), (242, 30, 3)):
        rd.ellipse((cx - r * S, cy - r * S, cx + r * S, cy + r * S), outline=MINT + (a,), width=wd * S)
    img = Image.alpha_composite(img, rings.filter(ImageFilter.GaussianBlur(1.6 * S)))
    d = ImageDraw.Draw(img, "RGBA")

    # đom đóm / hạt sáng
    rnd = random.Random(7)
    sp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sp)
    for _ in range(70):
        x, y = rnd.uniform(40, SW - 40), rnd.uniform(40, SH - 40)
        if 856 + M - 20 < x < 1348 + M + 20 and 150 + M - 20 < y < 592 + M + 20:
            continue                                   # không đặt trong ô trắng
        if (40 + M < x < 760 + M and 170 + M < y < 580 + M) or (740 + M < x < 1370 + M and 10 + M < y < 120 + M) \
                or (30 + M < x < 760 + M and 620 + M < y < 750 + M):
            continue                                   # tránh các vùng có chữ
        r = rnd.choice((1.5, 2, 2.5, 3.5))
        sd.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=(255, 245, 200, rnd.randint(120, 230)))
    img = Image.alpha_composite(img, sp.filter(ImageFilter.GaussianBlur(5 * S)))
    img = Image.alpha_composite(img, sp)

    # dây leo + lá chạy dọc rìa trong dải lề (nằm ngoài vùng nội dung)
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    mid = M * S / 2
    for i in range(0, 2):
        pass
    t = 120
    while t < SW - 120:                                # trên và dưới
        for yy, sgn in ((mid, 1), (h - mid, -1)):
            x = t * S
            _leaf(od, x, yy, 17 * S, 7 * S, sgn * (math.pi / 2) * 0.0 + (0.9 if (t // 46) % 2 else -0.9) * sgn,
                  LEAF + (190,), MINT + (130,))
        t += 46
    t = 120
    while t < SH - 120:                                # trái và phải
        for xx, sgn in ((mid, 1), (w - mid, -1)):
            y = t * S
            _leaf(od, xx, y, 17 * S, 7 * S, math.pi / 2 + (0.9 if (t // 46) % 2 else -0.9) * sgn,
                  LEAF + (190,), MINT + (130,))
        t += 46
    # dây mảnh nối các lá
    od.line([(120 * S, mid), ((SW - 120) * S, mid)], fill=LEAF_DARK + (150,), width=2 * S)
    od.line([(120 * S, h - mid), ((SW - 120) * S, h - mid)], fill=LEAF_DARK + (150,), width=2 * S)
    od.line([(mid, 120 * S), (mid, (SH - 120) * S)], fill=LEAF_DARK + (150,), width=2 * S)
    od.line([(w - mid, 120 * S), (w - mid, (SH - 120) * S)], fill=LEAF_DARK + (150,), width=2 * S)

    # họa tiết góc: vẽ một góc rồi lật ra bốn góc
    cs = 118 * S
    corner = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
    cd = ImageDraw.Draw(corner)
    _vine(cd, ((10 * S, 104 * S), (14 * S, 48 * S), (44 * S, 16 * S), (104 * S, 10 * S)), S, leaves=8, size=17)
    _vine(cd, ((10 * S, 70 * S), (16 * S, 40 * S), (36 * S, 22 * S), (68 * S, 14 * S)), S, leaves=4, size=12, alpha=170)
    for px, py, r in ((11, 11, 5), (46, 14, 2.5), (14, 46, 2.5)):
        cd.ellipse(((px - r) * S, (py - r) * S, (px + r) * S, (py + r) * S), fill=GOLD + (235,))
    ov.alpha_composite(corner, (0, 0))
    ov.alpha_composite(corner.transpose(Image.FLIP_LEFT_RIGHT), (w - cs, 0))
    ov.alpha_composite(corner.transpose(Image.FLIP_TOP_BOTTOM), (0, h - cs))
    ov.alpha_composite(corner.transpose(Image.ROTATE_180), (w - cs, h - cs))
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img, "RGBA")

    # khung đôi: vàng ngoài, xanh sáng trong (đều nằm trong dải lề, không chạm chữ)
    d.rounded_rectangle((5 * S, 5 * S, w - 5 * S, h - 5 * S), 26 * S, outline=GOLD + (210,), width=2 * S)
    d.rounded_rectangle((27 * S, 27 * S, w - 27 * S, h - 27 * S), 14 * S, outline=MINT + (170,), width=2 * S)
    for x, y in ((w / 2, 5 * S), (w / 2, h - 5 * S), (5 * S, h / 2), (w - 5 * S, h / 2)):   # kim cương giữa cạnh
        r = 8 * S
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=GOLD + (255,), outline=(120, 90, 30, 255))

    # ô trắng hiển thị: bóng + thẻ + viền kép + micro
    px0, py0, px1, py1 = (856 + M) * S, (150 + M) * S, (1348 + M) * S, (592 + M) * S
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((px0, py0 + 8 * S, px1, py1 + 8 * S), 30 * S, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(14 * S)))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((px0 - 6 * S, py0 - 6 * S, px1 + 6 * S, py1 + 6 * S), 34 * S, outline=MINT + (200,), width=3 * S)
    d.rounded_rectangle((px0, py0, px1, py1), 30 * S, fill=(240, 246, 242, 244))
    d.rounded_rectangle((px0 + 7 * S, py0 + 7 * S, px1 - 7 * S, py1 - 7 * S), 24 * S, outline=(120, 180, 150, 150), width=2 * S)
    mx, my = (1322 + M) * S, (184 + M) * S
    ink = (22, 35, 28, 255)
    d.rounded_rectangle((mx - 8 * S, my - 16 * S, mx + 8 * S, my + 10 * S), 8 * S, fill=ink)
    d.arc((mx - 15 * S, my - 6 * S, mx + 15 * S, my + 22 * S), 0, 180, fill=ink, width=3 * S)
    d.line((mx, my + 22 * S, mx, my + 32 * S), fill=ink, width=3 * S)
    d.line((mx - 9 * S, my + 32 * S, mx + 9 * S, my + 32 * S), fill=ink, width=3 * S)

    # lá nhỏ ôm hai góc của ô trắng
    lv = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lv)
    for (x, y, a) in ((px0 - 6 * S, py0 - 6 * S, -2.35), (px0 - 6 * S, py0 - 6 * S, -2.95), (px0 - 6 * S, py0 - 6 * S, -1.75),
                      (px1 + 6 * S, py1 + 6 * S, 0.8), (px1 + 6 * S, py1 + 6 * S, 0.2), (px1 + 6 * S, py1 + 6 * S, 1.4)):
        _leaf(ld, x, y, 30 * S, 13 * S, a, LEAF + (235,), MINT + (170,))
    img = Image.alpha_composite(img, lv)

    img.resize((SW, SH), Image.LANCZOS).convert("RGB").save(os.path.join(BASE, "anh nen app.png"))


def _tlv(tag, val):
    return f"{tag}{len(val):02d}{val}"


def _crc16(s):
    crc = 0xFFFF
    for b in s.encode():
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def vietqr(bin_, acc):
    acct = _tlv("00", bin_) + _tlv("01", acc)
    info = _tlv("00", "A000000727") + _tlv("01", acct) + _tlv("02", "QRIBFTTA")
    s = _tlv("00", "01") + _tlv("01", "11") + _tlv("38", info) + _tlv("53", "704") + _tlv("58", "VN") + "6304"
    return s + _crc16(s)


def qr(data, name):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1, box_size=10)
    q.add_data(data)
    q.make(fit=True)
    q.make_image(fill_color="black", back_color="white").convert("RGB").save(os.path.join(BASE, name))


if __name__ == "__main__":
    background()
    qr(WEBSITE, "qr_host.png")
    qr(vietqr(BANK_BIN, BANK_ACC), "qr_bank.png")
    print("Đã tạo: anh nen app.png, qr_host.png, qr_bank.png")
