# -*- coding: utf-8 -*-
"""Chuẩn hoá chữ trước khi đọc thành tiếng (website, số điện thoại, wifi, khu C...)."""
import re

_EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0000FE0F\U0000200D]+")
_ZONE_VI = {'a': "a", 'b': "bê", 'c': "xê", 'd': "đê"}


def _domain(vi, m):
    name = m.group(0)
    if name.lower() == "hoianfairyvilla.com":
        return "hội an phe-ri vi-la chấm com" if vi else "hoi an fairy villa dot com"
    return name.replace(".", " chấm " if vi else " dot ")


def _digits(m):
    d = re.sub(r"\D", "", m.group(0))
    return " ".join(d) if len(d) >= 7 else m.group(0)


def prep_for_speech(text, lang):
    """Trả về chữ đã chuẩn hoá cho giọng đọc. lang: mã ngôn ngữ ('vi', 'en', ...)."""
    if not text:
        return ""
    vi = lang == 'vi'
    t = _EMOJI.sub(" ", text)
    t = re.sub(r"https?://", "", t)
    t = re.sub(r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|vn|net|org|info)\b", lambda m: _domain(vi, m), t, flags=re.I)
    t = re.sub(r"\+?\(?\d[\d\s().-]{6,}\d", _digits, t)                  # số điện thoại -> đọc từng chữ số
    t = re.sub(r"\bwi-?fi\b", "wai phai" if vi else "Wi-Fi", t, flags=re.I)
    t = re.sub(r"\b5\s?g\b", "năm gờ" if vi else "5 G", t, flags=re.I)
    t = re.sub(r"\bA\.?I\b", "ây ai" if vi else "A I", t)
    t = re.sub(r"\bTPBank\b", "T P Bank", t, flags=re.I)
    if vi:
        t = re.sub(r"\b([Kk]hu|[Tt]òa|[Dd]ãy)\s+([A-Da-d])\b", lambda m: f"{m.group(1)} {_ZONE_VI[m.group(2).lower()]}", t)
    t = re.sub(r"[~^|<>{}\[\]_*#`]+", " ", t)
    t = re.sub(r"\s*\n+\s*", ". ", t)
    return re.sub(r"\s{2,}", " ", t).strip()
