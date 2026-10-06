# -*- coding: utf-8 -*-
"""Gửi email báo cho chủ nhà khi khách trò chuyện với lễ tân A.I.

Cách dùng: tạo file mail_password.txt (cạnh rec.py) chỉ chứa "Mật khẩu ứng dụng" 16 ký tự của Gmail gửi thư
(xem README_MAIL.txt). Không có file này thì tính năng tự tắt, ứng dụng vẫn chạy bình thường.
Các lượt hỏi-đáp liên tiếp được gom vào MỘT email (gửi sau khi khách yên lặng DEBOUNCE giây) để không bị spam."""
import os
import smtplib
import threading
import time
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIL_TO = os.environ.get("MAIL_TO", "fairygardenhoian@gmail.com")          # người nhận
MAIL_FROM = os.environ.get("MAIL_FROM", "fairygardenhoian@gmail.com")      # Gmail dùng để gửi (có thể trùng người nhận)
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
DEBOUNCE = 60            # giây không có lượt mới -> gửi email
MAX_WAIT = 300           # tối đa chờ bao nhiêu giây kể từ lượt đầu (khách nói liên tục vẫn được báo)
INCLUDE_EMPTY = False    # True: báo cả lần khách bấm phím nhưng không nói gì

_lock = threading.Lock()
_events = []
_first_ts = 0.0
_last_ts = 0.0
_worker = None
_warned = False


def _password():
    p = os.environ.get("MAIL_APP_PASSWORD", "").strip()
    f = os.path.join(BASE_DIR, "mail_password.txt")
    if not p and os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            p = fh.read().strip()
    return p.replace(" ", "")          # Gmail hiển thị mật khẩu ứng dụng có dấu cách, bỏ đi


def enabled():
    return bool(_password())


def add(kind, lang="", guest="", reply=""):
    """kind: 'chat' | 'empty' | 'error'. Gọi từ bất kỳ luồng nào, không chặn."""
    global _first_ts, _last_ts, _worker, _warned
    if kind == "empty" and not INCLUDE_EMPTY:
        return
    if not enabled():
        if not _warned:
            _warned = True
            print("[Mail] Chưa có mail_password.txt nên không gửi email thông báo (xem README_MAIL.txt).")
        return
    now = time.time()
    with _lock:
        if not _events:
            _first_ts = now
        _last_ts = now
        _events.append({"t": time.strftime("%H:%M:%S"), "kind": kind, "lang": lang, "guest": guest, "reply": reply})
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, daemon=True)
            _worker.start()


def _build(events):
    n_chat = sum(1 for e in events if e["kind"] == "chat")
    lines = [f"Có {len(events)} hoạt động với lễ tân A.I tại villa ({time.strftime('%d/%m/%Y')}):", ""]
    for e in events:
        if e["kind"] == "chat":
            lines += [f"[{e['t']}] Ngôn ngữ: {e['lang'] or '?'}",
                      f"  Khách nói : {e['guest']}",
                      f"  A.I trả lời: {e['reply'] or '(không có)'}", ""]
        elif e["kind"] == "empty":
            lines += [f"[{e['t']}] Khách bấm phím nhưng không nói gì / nhả quá nhanh.", ""]
        else:
            lines += [f"[{e['t']}] LỖI HỆ THỐNG: {e['reply'] or e['guest']}", ""]
    msg = EmailMessage()
    msg["Subject"] = f"[Lễ tân A.I] {n_chat} lượt hỏi đáp lúc {events[0]['t'][:5]}" if n_chat else "[Lễ tân A.I] Có hoạt động mới"
    if any(e["kind"] == "error" for e in events):
        msg["Subject"] += " - CÓ LỖI"
    msg["From"], msg["To"] = MAIL_FROM, MAIL_TO
    msg.set_content("\n".join(lines))
    return msg


def _send(events):
    msg = _build(events)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=25) as s:
        s.login(MAIL_FROM, _password())
        s.send_message(msg)


def _run():
    global _events
    while True:
        time.sleep(1)
        with _lock:
            if not _events:
                return                                   # hết việc: luồng tự dừng, lần sau add() sẽ tạo lại
            now = time.time()
            ready = (now - _last_ts >= DEBOUNCE) or (now - _first_ts >= MAX_WAIT)
            if not ready:
                continue
            batch, _events = _events, []
        try:
            _send(batch)
            print(f"[Mail] Đã gửi email thông báo tới {MAIL_TO} ({len(batch)} hoạt động)")
        except Exception as e:
            print(f"[Mail] Gửi email lỗi: {type(e).__name__}: {e}")
