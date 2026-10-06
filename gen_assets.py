# -*- coding: utf-8 -*-
"""Tạo lại ảnh nền + hai mã QR cho giao diện lễ tân. Chạy: python gen_assets.py  (cần: pip install pillow qrcode)
Muốn dùng ảnh nền / QR riêng thì chỉ cần ghi đè các file PNG cùng tên."""
import os
import qrcode
from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
W, H = 1376, 768
WEBSITE = "https://hoianfairyvilla.com"
BANK_BIN, BANK_ACC = "970423", "10001689000"          # TPBank - số tài khoản 1000 1689 000


def background():
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):                                 # nền xanh lá đậm chuyển sắc
        for x in range(0, W):
            t = (x / W) * 0.45 + (y / H) * 0.55
            px[x, y] = (int(8 + 12 * t), int(40 + 52 * t), int(24 + 30 * t))
    d = ImageDraw.Draw(img, "RGBA")
    for cx, cy, r, a in [(120, 90, 190, 26), (700, 700, 260, 20), (1250, 650, 200, 24), (400, 330, 150, 14)]:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(107, 255, 176, a))      # vệt sáng mờ
    img = img.filter(ImageFilter.GaussianBlur(30))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle((8, 8, W - 9, H - 9), 34, outline=(107, 255, 176, 170), width=4)     # viền xanh
    d.rounded_rectangle((856, 150, 1348, 592), 30, fill=(238, 245, 240, 236))                 # ô trắng hiển thị
    d.rounded_rectangle((856, 150, 1348, 592), 30, outline=(255, 255, 255, 255), width=3)
    mx, my = 1322, 184                                                                           # biểu tượng micro
    d.rounded_rectangle((mx - 8, my - 16, mx + 8, my + 10), 8, fill=(22, 35, 28, 255))
    d.arc((mx - 15, my - 6, mx + 15, my + 22), 0, 180, fill=(22, 35, 28, 255), width=3)
    d.line((mx, my + 22, mx, my + 32), fill=(22, 35, 28, 255), width=3)
    d.line((mx - 9, my + 32, mx + 9, my + 32), fill=(22, 35, 28, 255), width=3)
    img.save(os.path.join(BASE, "anh nen app.png"))


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
