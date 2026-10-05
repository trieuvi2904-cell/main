# -*- coding: utf-8 -*-
"""Lễ tân A.I - Fairy Garden Villa.

Luồng xử lý: giữ phím F2-F7 để nói -> nhả phím -> Whisper (faster-whisper) -> Claude (stream)
-> đọc từng câu bằng edge-tts (dự phòng gTTS) ngay khi câu đầu tiên sẵn sàng.
"""
import os
import sys
import re
import io
import time
import html
import queue
import hashlib
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import sounddevice as sd
import keyboard
import anthropic
import pygame

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSignal, QObject

from ui_letan import Ui_MainWindow          # giao diện (dùng widget gv từ gv.py)
from prompt_letan import SYSTEM_CONTEXT, time_context     # nội dung tư vấn + giờ hiện tại
from doc_chu import prep_for_speech         # chuẩn hoá cách đọc (website, số, khu C...)

# Thư viện giọng nói: ưu tiên bản nhanh, tự lùi về bản cũ nếu chưa cài
try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None
try:
    import whisper as openai_whisper
except ImportError:
    openai_whisper = None
try:
    import edge_tts
except ImportError:
    edge_tts = None
try:
    from gtts import gTTS
except ImportError:
    gTTS = None
try:
    from groq import Groq
except ImportError:
    Groq = None
import wave

# =====================================================================
# CẤU HÌNH (chỉnh ở đây)
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "audio_cache")     # câu cố định đã tạo sẵn
WHISPER_SIZE = os.environ.get("WHISPER_MODEL", "small")   # tiny / base / small
MODEL_VOICE = "claude-haiku-4-5-20251001"
MODEL_TEXT = "claude-haiku-4-5-20251001"               # đổi thành "claude-sonnet-5-5" nếu muốn gõ phím trả lời kỹ hơn
MAX_TOKENS = 350
FS = 16000                  # Whisper dùng 16 kHz -> thu thẳng 16 kHz, không cần đổi tần số
MIN_HOLD = 1.0              # giữ phím dưới số giây này = nhả quá nhanh
TAIL_SECONDS = 0.4          # thu thêm sau khi nhả phím để không cụt đuôi câu
INACTIVITY_MS = 60000       # 60 giây không tương tác thì về màn hình chào
HISTORY_TURNS = 3           # nhớ bao nhiêu lượt hỏi-đáp gần nhất (0 = tắt)
TTS_ENGINE = "gtts"         # "gtts" = giọng Google quen thuộc như bản gốc | "edge" = giọng neural mới (cần pip install edge-tts)
TTS_RATE = "+15%"           # tốc độ đọc so với bình thường (gTTS tăng tốc bằng ffmpeg, giữ nguyên cao độ giọng)
PLAY_ACK = True             # đọc câu "tôi đã nhận được câu hỏi" trong lúc xử lý (False = bỏ để trả lời sớm hơn)
# Mô hình nhận diện tiếng Việt riêng (tuỳ chọn, chính xác hơn với giọng vùng miền):
# đặt biến môi trường WHISPER_VI_MODEL = đường dẫn thư mục mô hình PhoWhisper đã đổi sang CTranslate2 (xem HUONG_DAN_GIONG_VIET.txt)
WHISPER_VI_MODEL = os.environ.get("WHISPER_VI_MODEL", "").strip()
BEAM_VI = 2                 # tiếng Việt: 1 = nhanh nhất, 5 = chính xác nhất nhưng chậm. 2 là mức cân bằng. Ngôn ngữ khác dùng 1
FIRST_CHUNK_CHARS = 15      # câu đầu đọc sớm nhất có thể
NEXT_CHUNK_CHARS = 40       # các câu sau gom lại cho tự nhiên

LANG_MAP = {
    'f2': ('vi', 'Tiếng Việt'),
    'f3': ('en', 'Tiếng Anh'),
    'f4': ('zh', 'Tiếng Trung'),
    'f5': ('es', 'Tiếng Tây Ban Nha'),
    'f6': ('fr', 'Tiếng Pháp'),
    'f7': (None, 'Tự động nhận diện'),
}
TTS_LANGS = ['vi', 'en', 'zh', 'ko', 'ja', 'fr', 'es']
EDGE_VOICES = {
    'vi': 'vi-VN-HoaiMyNeural', 'en': 'en-US-AriaNeural', 'zh': 'zh-CN-XiaoxiaoNeural',
    'es': 'es-ES-ElviraNeural', 'fr': 'fr-FR-DeniseNeural',
    'ja': 'ja-JP-NanamiNeural', 'ko': 'ko-KR-SunHiNeural',
}
GTTS_CODES = {'zh': 'zh-CN'}
WHISPER_HINT_VI = "Villa Hội An: dọn phòng, nhận phòng, trả phòng, xe máy, ăn sáng, wifi, hồ bơi, Agoda, Zalo, WhatsApp."


def _load_api_key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not k:
        p = os.path.join(BASE_DIR, "api_key.txt")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                k = f.read().strip()
    if not k:
        print("THIẾU API KEY: hãy tạo file api_key.txt (chỉ chứa khoá) hoặc đặt biến ANTHROPIC_API_KEY")
        sys.exit(1)
    return k


def _load_groq_key():
    k = os.environ.get("GROQ_API_KEY", "").strip()
    p = os.path.join(BASE_DIR, "groq_key.txt")
    if not k and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            k = f.read().strip()
    return k


client = anthropic.Anthropic(api_key=_load_api_key(), timeout=25.0, max_retries=2)
STT_CLOUD = True                          # False = chỉ dùng Whisper trên máy
GROQ_MODEL = "whisper-large-v3-turbo"
_gk = _load_groq_key()
groq_client = Groq(api_key=_gk, timeout=8.0, max_retries=1) if (Groq and _gk) else None
_LANG_NAME = {'vietnamese': 'vi', 'english': 'en', 'chinese': 'zh', 'spanish': 'es',
              'french': 'fr', 'japanese': 'ja', 'korean': 'ko'}
SYSTEM_BLOCKS = [{"type": "text", "text": SYSTEM_CONTEXT, "cache_control": {"type": "ephemeral"}}]
pygame.mixer.init()

# =====================================================================
# THÔNG BÁO ĐA NGÔN NGỮ (một chỗ duy nhất)
# =====================================================================
MSG = {
    'interrupt': {
        'vi': "[Hệ thống] Đã ngắt giọng AI theo yêu cầu của khách.",
        'en': "[System] Interrupting AI speech per guest request.",
        'zh': "[系统] 正在根据客人的要求打断AI讲话。",
        'es': "[Sistema] Interrumpiendo la voz de la IA a petición del huésped.",
        'fr': "[Système] Interruption de la voix de l'IA à la demande du client."},
    'help_title': {
        'vi': "=== ĐÃ CHUYỂN SANG CHẾ ĐỘ: TIẾNG VIỆT (F2) ===",
        'en': "=== SWITCHED TO MODE: ENGLISH (F3) ===",
        'zh': "=== 已切换至模式：中文 (F4) ===",
        'es': "=== CAMBIADO AL MODO: ESPAÑOL (F5) ===",
        'fr': "=== PASSÉ EN MODE : FRANÇAIS (F6) ===",
        'auto': "=== CHẾ ĐỘ TỰ ĐỘNG NHẬN DIỆN (F7) ==="},
    'help_body': {
        'vi': "Cách sử dụng tại quầy: Nhấn và GIỮ phím F2, nói xong thì thả ra + đợi thêm 1s để hệ thống xử lý.",
        'en': "How to use at the counter: Press and HOLD F3, speak, then release and wait 1s for processing.",
        'zh': "柜台使用方法：按住 F4 键说话，说完后松开并等待 1 秒进行处理。",
        'es': "Cómo usar en el mostrador: Mantenga presionada la tecla F5, hable, luego suelte y espere 1s.",
        'fr': "Comment utiliser au comptoir : Appuyez et MAINTENEZ F6, parlez, puis relâchez.",
        'auto': "How to use at the counter: Press and HOLD F7, speak, then release and wait 1s for processing."},
    'recording': {
        'vi': "[Hệ thống] Đang thu âm...", 'en': "[System] Recording audio...", 'zh': "[系统] 正在录音...",
        'es': "[Sistema] Grabando audio...", 'fr': "[Système] Enregistrement audio..."},
    'hold': {
        'vi': "[Hệ thống] Thời gian giữ phím: {d:.2f} giây", 'en': "[System] Key hold duration: {d:.2f} seconds",
        'zh': "[系统] 按键保持时间: {d:.2f} 秒", 'es': "[Sistema] Duración de la pulsación de la tecla: {d:.2f} segundos",
        'fr': "[Système] Durée de maintien de la touche : {d:.2f} secondes"},
    'too_quick': {
        'vi': "[Hệ thống] Khách hàng nhả phím quá nhanh, chưa kịp nói.",
        'en': "[System] Key released too quickly, no speech detected.",
        'zh': "[系统] 按键释放过快，未检测到语音。",
        'es': "[Sistema] Tecla soltada demasiado rápido, no se detectó voz.",
        'fr': "[Système] Touche relâchée trop rapidement, aucune parole détectée."},
    'processing': {
        'vi': "[Hệ thống] Đang xử lý giọng nói...", 'en': "[System] Processing audio...", 'zh': "[系统] 正在处理语音...",
        'es': "[Sistema] Procesando audio...", 'fr': "[Système] Traitement de l'audio..."},
    'transcribing': {
        'vi': "[Hệ thống] Đang chuyển đổi giọng nói...", 'en': "[System] Transcribing speech...",
        'zh': "[系统] 正在转写语音...", 'es': "[Sistema] Transcribiendo voz...", 'fr': "[Système] Transcription vocale..."},
    'no_speech': {
        'vi': "[Hệ thống] Không phát hiện nội dung giọng nói.", 'en': "[System] No speech content detected.",
        'zh': "[系统] 未检测到语音内容。", 'es': "[Sistema] No se detectó contenido de voz.",
        'fr': "[Système] Aucun contenu vocal détecté."},
    'starting': {
        'vi': "[Hệ thống] Hệ thống đang khởi động, vui lòng đợi vài giây rồi thử lại.",
        'en': "[System] The system is starting up, please wait a few seconds and try again."},
}
# Câu đọc thành tiếng cố định -> tạo sẵn một lần, các lần sau phát lại ngay
ACK_PHRASES = {
    'vi': "Được rồi, tôi đã nhận được câu hỏi.", 'en': "Got it, I have received your question.",
    'zh': "好的，我已经收到您的提问了。", 'es': "Entendido, he recibido su pregunta.",
    'fr': "C'est compris, j'ai bien reçu votre question.",
    'ja': "わかりました、質問を受け付けました。", 'ko': "알겠습니다, 질문을 접수했습니다."}
WARN_QUICK = {
    'vi': "Xin lỗi, bạn vừa nhấn và nhả phím thu âm quá nhanh, hãy nhấn giữ, đồng thời nói trong lúc bạn giữ phím, chỉ thả phím ra khi bạn nói xong.",
    'en': "Sorry, you released the record key too quick. Please press and hold while speaking, and release only when finished.",
    'zh': "抱歉，您松开录音键太快了。请按住并说话，说完后再松开。",
    'es': "Lo siento, soltó la tecla demasiado rápido. Mantenga presionado mientras habla y suéltelo al terminar.",
    'fr': "Désolé, vous avez relâché la touche trop vite. Maintenez-la enfoncée en parlant."}
NOT_HEARD = {
    'vi': "Xin lỗi, tôi không nghe rõ. Vui lòng chọn đúng phím ngôn ngữ và nói lại rõ hơn nhé.",
    'en': "Sorry, I didn't catch that. Please press the correct language key and speak more clearly.",
    'zh': "抱歉，我没听清。请按下正确的语言键，并再说清楚一点。",
    'es': "Lo siento, no entendí. Por favor, presione la tecla del idioma correcto y hable más claro.",
    'fr': "Désolé, je n'ai pas bien entendu. Veuillez choisir la bonne touche de langue et parler plus clairement."}
ERROR_SPOKEN = {
    'vi': "Xin lỗi, hệ thống đang gặp sự cố kết nối. Quý khách vui lòng liên hệ nhân viên qua các cách liên lạc đặt tại quầy.",
    'en': "Sorry, the system has a connection problem. Please contact our staff using the contact details at the counter.",
    'zh': "抱歉，系统连接出现问题。请通过柜台上的联系方式联系工作人员。",
    'es': "Lo siento, hay un problema de conexión. Por favor contacte al personal con los datos del mostrador.",
    'fr': "Désolé, problème de connexion. Veuillez contacter le personnel avec les coordonnées du comptoir."}


def msg(key, lang, **kw):
    table = MSG[key]
    text = table.get(lang) or table.get('en') or table['vi']
    return text.format(**kw) if kw else text


# =====================================================================
# GHI LOG LÊN MÀN HÌNH
# =====================================================================
class LogEmitter(QObject):
    append_log_signal = pyqtSignal(str)      # thêm một dòng mới
    inline_log_signal = pyqtSignal(str)      # nối tiếp vào dòng cuối (dùng khi trả lời theo từng câu)
    poke_timer_signal = pyqtSignal()         # reset bộ đếm 60 giây (an toàn khi gọi từ luồng khác)


log_emitter = LogEmitter()


def safe_print(text):
    print(text)
    log_emitter.append_log_signal.emit(text)


def print_welcome_instructions():
    safe_print("1. NHẤN VÀ GIỮ PHÍM TƯƠNG ỨNG BÊN GÓC TRÁI ĐỂ NÓI CHUYỆN BẰNG GIỌNG NÓI (NHẢ PHÍM KHI NÓI XONG)\nPRESS AND HOLD THE CORRESPONDING KEY ON THE LEFT TO SPEAK USING VOICE (RELEASE KEY WHEN FINISHED)")
    safe_print("ẤN và GIỮ/PRESS and HOLD:\nVIE: Tiếng Việt\nEng: English\n中: 中文\nEsp: Espanol\nFra: Francais\nAuto: Language detect")
    safe_print("HOẶC DÙNG BÀN PHÍM ĐỂ GÕ THỦ CÔNG\nOR USE KEYBOARD TO TYPE MANUALLY")


# =====================================================================
# PHÁT ÂM THANH: một hàng đợi duy nhất, có số thứ tự lượt để huỷ câu cũ
# =====================================================================
_gen = 0
_gen_lock = threading.Lock()
player_q = queue.Queue()
tts_pool = ThreadPoolExecutor(max_workers=3)
last_lang = 'vi'


def current_gen():
    return _gen


def stop_ai_speaking(lang=None):
    """Ngắt giọng đang đọc và huỷ mọi câu trả lời đang chờ (kể cả câu đang được tạo)."""
    global _gen
    with _gen_lock:
        _gen += 1
        new = _gen
    while True:
        try:
            player_q.get_nowait()
        except queue.Empty:
            break
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        safe_print("\n" + msg('interrupt', lang or last_lang))
    return new


def _player_loop():
    while True:
        gen, src = player_q.get()
        if gen != current_gen():
            continue
        try:
            data = src.result(timeout=40) if hasattr(src, "result") else src
        except Exception as e:
            safe_print(f"[Lỗi tạo giọng nói]: {e}")
            continue
        if not data or gen != current_gen():
            continue
        try:
            pygame.mixer.music.load(io.BytesIO(data), "mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and gen == current_gen():
                time.sleep(0.03)
        except Exception as e:
            safe_print(f"[Lỗi phát âm thanh]: {e}")


def clean_for_speech(text):
    return re.sub(r"[*#`_]+", "", text).strip()


_reported = set()
last_engine = None


def report_once(text):
    if text not in _reported:
        _reported.add(text)
        safe_print(text)


def _speed_factor():
    try:
        return 1.0 + int(TTS_RATE.replace("%", "").replace("+", "")) / 100.0
    except ValueError:
        return 1.0


def _ffmpeg_path():
    for p in (shutil.which("ffmpeg"), r"C:\ffmpeg\bin\ffmpeg.exe"):
        if p and os.path.exists(p):
            return p
    return None


def speed_up_mp3(data):
    """Dự phòng khi dùng gTTS (không có tham số tốc độ): tăng tốc bằng ffmpeg. Không có ffmpeg thì giữ nguyên."""
    ff, k = _ffmpeg_path(), min(_speed_factor(), 2.0)
    if not ff or k <= 1.01:
        report_once("[Giọng đọc] KHÔNG tìm thấy ffmpeg nên không tăng tốc được giọng gTTS. Kiểm tra C:\\ffmpeg\\bin\\ffmpeg.exe")
        return data
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run([ff, "-loglevel", "quiet", "-i", "pipe:0", "-filter:a", f"atempo={k:.2f}", "-f", "mp3", "pipe:1"],
                             input=data, capture_output=True, timeout=20, creationflags=flags)
        return out.stdout or data
    except Exception:
        return data


def synth(text, lang):
    """Chữ -> mp3 (bytes). Theo TTS_ENGINE; nếu engine chính lỗi thì dùng engine còn lại."""
    global last_engine
    text = prep_for_speech(clean_for_speech(text), lang)
    if not text:
        return b""
    order = ["edge", "gtts"] if TTS_ENGINE == "edge" else ["gtts", "edge"]
    for eng in order:
        if eng == "edge" and edge_tts is not None:
            try:
                import asyncio

                async def _run():
                    buf = bytearray()
                    comm = edge_tts.Communicate(text, EDGE_VOICES.get(lang, EDGE_VOICES['en']), rate=TTS_RATE)
                    async for ch in comm.stream():
                        if ch["type"] == "audio":
                            buf.extend(ch["data"])
                    return bytes(buf)

                data = asyncio.run(asyncio.wait_for(_run(), 20))
                if data:
                    last_engine = 'edge-tts'
                    return data
            except Exception as e:
                report_once(f"[Giọng đọc] edge-tts bị lỗi: {type(e).__name__}: {e}. Hãy chạy: pip install -U edge-tts")
        elif eng == "gtts" and gTTS is not None:
            try:
                buf = io.BytesIO()
                gTTS(text=text, lang=GTTS_CODES.get(lang, lang), slow=False).write_to_fp(buf)
                last_engine = 'gTTS'
                return speed_up_mp3(buf.getvalue())
            except Exception as e:
                report_once(f"[Giọng đọc] gTTS bị lỗi: {type(e).__name__}: {e}")
    raise RuntimeError("Không tạo được giọng nói (kiểm tra mạng, hoặc pip install gTTS edge-tts)")


def synth_cached(text, lang):
    """Dùng cho câu cố định: lần đầu tạo và lưu đĩa, lần sau đọc từ đĩa (chạy được cả khi mất mạng)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, hashlib.md5(f"{TTS_ENGINE}|{lang}|{TTS_RATE}|{text}".encode("utf-8")).hexdigest() + ".mp3")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    data = synth(text, lang)
    if data:
        with open(path, "wb") as f:
            f.write(data)
    return data


def speak(gen, text, lang, cached=False):
    """Xếp một câu vào hàng đợi phát (tạo giọng chạy song song, phát đúng thứ tự)."""
    player_q.put((gen, tts_pool.submit(synth_cached if cached else synth, text, lang)))


def _tts_selftest():
    try:
        synth("Xin chào", 'vi')
        safe_print(f"[Giọng đọc] Đang dùng {last_engine} - tốc độ {TTS_RATE}")
    except Exception as e:
        safe_print(f"[Giọng đọc] Không tạo được giọng nói: {e}")


def prewarm_phrases():
    """Tạo sẵn các câu cố định ở nền khi khởi động."""
    for table in (ACK_PHRASES, WARN_QUICK, NOT_HEARD, ERROR_SPOKEN):
        for lang, text in table.items():
            try:
                synth_cached(text, lang)
            except Exception as e:
                print(f"[Không tạo sẵn được '{lang}']: {e}")
                return


# =====================================================================
# NHẬN DIỆN GIỌNG NÓI
# =====================================================================
stt_model = None
stt_vi = None
stt_kind = None
models_ready = threading.Event()


def _load_one(size):
    global stt_model, stt_kind, stt_vi
    if WhisperModel is not None:
        threads = max(2, min(8, (os.cpu_count() or 4) // 2 + 1))
        stt_model = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=threads)
        stt_kind = "faster"
        if WHISPER_VI_MODEL and stt_vi is None:
            stt_vi = WhisperModel(WHISPER_VI_MODEL, device="cpu", compute_type="int8", cpu_threads=threads)
    elif openai_whisper is not None:
        stt_model = openai_whisper.load_model(size)
        stt_kind = "openai"
    else:
        raise RuntimeError("Chưa cài faster-whisper hoặc openai-whisper")
    # làm nóng thật: dùng tiếng ồn + tắt VAD để encoder/decoder thực sự chạy (im lặng sẽ bị VAD loại hết)
    noise = (np.random.randn(FS * 2) * 0.05).astype(np.float32)
    for lg in ('vi', 'en'):
        transcribe_local(noise, lg, warmup=True)


def load_models():
    """Nạp mô hình giọng nói. Thiếu RAM thì tự thử mô hình nhỏ hơn (small -> base -> tiny)."""
    global stt_model
    import gc
    safe_print("Đang tải mô hình nhận diện giọng nói... (lần đầu có thể mất vài phút để tải về)")
    chain = [WHISPER_SIZE] + [m for m in ("base", "tiny") if m != WHISPER_SIZE]
    for size in chain:
        try:
            _load_one(size)
            if size != WHISPER_SIZE:
                safe_print(f"[Cảnh báo] Không đủ RAM cho mô hình '{WHISPER_SIZE}', đang dùng '{size}' (nhận diện kém chính xác hơn). Hãy đóng bớt chương trình khác.")
            break
        except Exception as e:
            safe_print(f"[Lỗi tải mô hình '{size}']: {e}")
            stt_model = None
            gc.collect()
    else:
        safe_print("[Lỗi] Không nạp được mô hình giọng nói. Hãy đóng bớt chương trình, tăng bộ nhớ ảo, rồi chạy lại.")
        return
    safe_print("Đã tải xong mô hình nhận diện giọng nói!")
    models_ready.set()
    log_emitter.append_log_signal.emit("\x00welcome")     # báo cho cửa sổ in màn hình chào
    threading.Thread(target=prewarm_phrases, daemon=True).start()
    threading.Thread(target=_tts_selftest, daemon=True).start()


def _normalize(audio):
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if 0.001 < peak < 0.6:                       # micro nhỏ -> khuếch đại để nghe rõ hơn
        audio = np.clip(audio * (0.9 / peak), -1.0, 1.0).astype(np.float32)
    return audio


def _wav_bytes(audio):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def _drop_prompt_echo(text):
    """Bỏ kết quả chỉ là lặp lại câu gợi ý (Whisper bịa khi không nghe rõ)."""
    t = re.sub(r"[\W_]+", " ", text.lower()).strip()
    hint = re.sub(r"[\W_]+", " ", WHISPER_HINT_VI.lower())
    return "" if t and t in hint else text


def transcribe_cloud(audio, lang):
    audio = _normalize(audio)
    t0 = time.time()
    kw = {}                                     # KHÔNG truyền prompt: Whisper hay lặp lại đúng câu gợi ý khi âm thanh nhỏ/không rõ
    if lang:
        kw["language"] = lang
    r = groq_client.audio.transcriptions.create(
        file=("audio.wav", _wav_bytes(audio)), model=GROQ_MODEL,
        temperature=0.0, response_format="verbose_json", **kw)
    print(f"[Groq] nhận diện mất {time.time() - t0:.1f}s cho {audio.size / FS:.1f}s âm thanh")
    detected = lang or _LANG_NAME.get(str(getattr(r, "language", "")).lower(), 'en')
    return _drop_prompt_echo((r.text or "").strip()), detected


def transcribe(audio, lang):
    """Ưu tiên Groq (nhanh); lỗi mạng/API thì tự dùng Whisper trên máy."""
    if STT_CLOUD and groq_client is not None:
        try:
            return transcribe_cloud(audio, lang)
        except Exception as e:
            print(f"[Groq] lỗi, chuyển sang Whisper local: {type(e).__name__}: {e}")
    return transcribe_local(audio, lang)


def transcribe_local(audio, lang, warmup=False):
    """audio: float32 mono 16 kHz. Trả về (text, ngôn ngữ nhận diện)."""
    prompt = WHISPER_HINT_VI if lang == 'vi' else None
    audio = _normalize(audio)
    if stt_kind == "faster":
        t0 = time.time()
        model = stt_vi if (lang == 'vi' and stt_vi is not None) else stt_model
        segs, info = model.transcribe(audio, language=lang, beam_size=BEAM_VI if lang == 'vi' else 1,
                                      temperature=0.0, initial_prompt=prompt, condition_on_previous_text=False,
                                      without_timestamps=True, vad_filter=not warmup,
                                      vad_parameters={"min_silence_duration_ms": 700})
        text = _drop_prompt_echo("".join(s.text for s in segs).strip())
        print(f"[Whisper] nhận diện mất {time.time() - t0:.1f}s cho {audio.size / FS:.1f}s âm thanh")
        return text, (lang or info.language or 'vi')
    r = stt_model.transcribe(audio, language=lang, fp16=False, temperature=0.0,
                             initial_prompt=prompt, condition_on_previous_text=False)
    return r["text"].strip(), (lang or r.get("language") or 'vi')


# =====================================================================
# CLAUDE: trả lời dạng stream, đọc từng câu ngay khi có
# =====================================================================
_hist_lock = threading.Lock()
history = []          # [(user, assistant)]
_SENT_RE = re.compile(r".*?(?:[。！？]+|[.!?]+(?=\s)|\n+)", re.S)
_TAG_RE = re.compile(r"\s*\[([A-Za-z\-]{2,5})\]\s*")
_VI_CHARS = set("ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ")


def split_sentences(buf):
    out, pos = [], 0
    for m in _SENT_RE.finditer(buf):
        out.append(m.group())
        pos = m.end()
    return out, buf[pos:]


def guess_lang(text):
    if any('一' <= c <= '鿿' for c in text):
        return 'zh'
    if any(c in _VI_CHARS for c in text.lower()):
        return 'vi'
    return 'en'


def history_messages():
    with _hist_lock:
        msgs = []
        for u, a in history[-HISTORY_TURNS:] if HISTORY_TURNS else []:
            msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        return msgs


def stream_reply(gen, user_content, model, label, lang, detect_tag=False, fallback_text=""):
    """Gọi Claude (stream), hiện chữ và xếp giọng đọc theo từng câu. Trả về toàn văn câu trả lời."""
    buf, pending, full = "", "", []
    state = {"first": True, "tag_done": not detect_tag, "lang": lang}

    def flush(piece):
        piece = re.sub(r"[*#`]+", "", piece)
        if not piece.strip():
            return
        if state["first"]:
            safe_print(f"{label}: {piece.strip()}")
            state["first"] = False
        else:
            log_emitter.inline_log_signal.emit(piece)
        speak(gen, piece, state["lang"])
        full.append(piece)

    with client.messages.stream(model=model, max_tokens=MAX_TOKENS, system=SYSTEM_BLOCKS + [{"type": "text", "text": time_context()}],
                                messages=history_messages() + [{"role": "user", "content": user_content}]) as st:
        for chunk in st.text_stream:
            if gen != current_gen():
                return ""                      # khách đã nói/gõ câu mới -> bỏ lượt này
            buf += chunk
            if not state["tag_done"]:
                m = _TAG_RE.match(buf)
                if m:
                    code = m.group(1).lower().split("-")[0]
                    state["lang"] = code if code in TTS_LANGS else guess_lang(fallback_text)
                    buf = buf[m.end():]
                    state["tag_done"] = True
                elif len(buf) > 12 or "]" in buf:
                    state["lang"] = guess_lang(fallback_text)
                    state["tag_done"] = True
                else:
                    continue
            sents, buf = split_sentences(buf)
            for s in sents:
                pending += s
                need = FIRST_CHUNK_CHARS if state["first"] else NEXT_CHUNK_CHARS
                if len(pending.strip()) >= need:
                    flush(pending)
                    pending = ""
        if gen != current_gen():
            return ""
        if not state["tag_done"]:
            m = _TAG_RE.match(buf)
            state["lang"] = (m.group(1).lower().split("-")[0] if m and m.group(1).lower() in TTS_LANGS
                             else guess_lang(fallback_text))
            buf = buf[m.end():] if m else buf
        flush(pending + buf)
    text = "".join(full).strip()
    if text:
        with _hist_lock:
            history.append((user_content, text))
            del history[:-max(HISTORY_TURNS, 1)]
    return text


def report_error(gen, lang, where, e):
    safe_print(f"[{where}]: {e}")
    speak(gen, ERROR_SPOKEN.get(lang, ERROR_SPOKEN['en']), lang if lang in ERROR_SPOKEN else 'en', cached=True)


# =====================================================================
# THU ÂM
# =====================================================================
_rec_lock = threading.Lock()
_rec = None
_held = set()
_session = 0


def start_recording(key, lang_code, lang_name):
    global _rec, _session, last_lang
    log_emitter.poke_timer_signal.emit()
    if key in _held:                       # phím đang giữ bị lặp sự kiện -> bỏ qua
        return
    _held.add(key)
    if not models_ready.is_set():
        safe_print(msg('starting', 'vi') + "\n" + msg('starting', 'en'))
        return
    with _rec_lock:
        if _rec is not None and _rec["end"] is None:
            return                         # đang thu bằng phím khác
        if _rec is not None:               # còn đang "thu đuôi" của lượt trước -> bỏ lượt đó
            try:
                _rec["stream"].close()
            except Exception:
                pass
    shown = lang_code or 'en'
    last_lang = shown
    stop_ai_speaking(shown)
    frames = []
    try:
        stream = sd.InputStream(samplerate=FS, channels=1, dtype="float32",
                                callback=lambda indata, n, t, s: frames.append(indata.copy()))
        stream.start()
    except Exception as e:
        safe_print(f"[Lỗi micro]: {e}")
        return
    with _rec_lock:
        _session += 1
        _rec = {"id": _session, "key": key, "lang": lang_code, "name": lang_name,
                "start": time.time(), "end": None, "frames": frames, "stream": stream}
    help_key = lang_code if lang_code in MSG['help_title'] else 'auto'
    safe_print("\n" + msg('help_title', help_key))
    safe_print(msg('help_body', help_key))
    safe_print(msg('recording', shown))


def handle_release(key):
    _held.discard(key)
    with _rec_lock:
        r = _rec
        if r is None or r["end"] is not None or r["key"] != key:
            return
        r["end"] = time.time()
    threading.Timer(TAIL_SECONDS, finish_recording, args=(r["id"],)).start()


def finish_recording(rid):
    global _rec
    with _rec_lock:
        r = _rec
        if r is None or r["id"] != rid:
            return                         # đã có lượt thu mới thay thế
        _rec = None
    try:
        r["stream"].stop()
        r["stream"].close()
    except Exception:
        pass
    lang = r["lang"]
    shown = lang or 'en'
    duration = r["end"] - r["start"]
    safe_print(msg('hold', shown, d=duration))
    gen = current_gen()

    if duration < MIN_HOLD or not r["frames"]:
        safe_print(msg('too_quick', shown))
        speak(gen, WARN_QUICK.get(shown, WARN_QUICK['vi']), shown if shown in WARN_QUICK else 'vi', cached=True)
        return

    safe_print(msg('processing', shown))
    if lang and PLAY_ACK:
        speak(gen, ACK_PHRASES.get(lang, ACK_PHRASES['en']), lang if lang in ACK_PHRASES else 'en', cached=True)
    audio = np.concatenate(r["frames"], axis=0).reshape(-1).astype(np.float32)
    threading.Thread(target=process_audio_pipeline, args=(gen, audio, lang, r["name"]), daemon=True).start()


# =====================================================================
# HAI LUỒNG XỬ LÝ: GIỌNG NÓI và GÕ PHÍM
# =====================================================================
def process_audio_pipeline(gen, audio, lang, lang_name):
    shown = lang or 'en'
    try:
        safe_print(msg('transcribing', shown) if lang else "[System] Detecting language...")
        speech, detected = transcribe(audio, lang)
        if gen != current_gen():
            return
        if not lang and PLAY_ACK:
            speak(gen, ACK_PHRASES.get(detected, ACK_PHRASES['en']), detected if detected in ACK_PHRASES else 'en', cached=True)
        safe_print(f"[Khách hàng nói ({detected})]: {speech}")

        if not speech:
            safe_print(msg('no_speech', shown))
            tl = lang if lang in NOT_HEARD else (detected if detected in NOT_HEARD else 'vi')
            speak(gen, NOT_HEARD[tl], tl, cached=True)
            return

        if lang:
            prompt = f"Khách hàng vừa nói bằng {lang_name}: '{speech}'. Hãy trả lời hoàn toàn bằng {lang_name}."
        else:
            prompt = speech
        tts_lang = detected if detected in TTS_LANGS else 'en'
        stream_reply(gen, prompt, MODEL_VOICE, "[A.I Staff]", tts_lang)
    except Exception as e:
        report_error(gen, lang or 'en', "Lỗi hệ thống", e)


def process_text_pipeline(user_text):
    gen = stop_ai_speaking()
    try:
        safe_print(f"[Khách gõ phím]: {user_text}")
        prompt = (f"Khách hàng vừa gõ tin nhắn: '{user_text}'. Hãy xác định ngôn ngữ của khách hàng và trả lời hoàn toàn bằng "
                  f"chính ngôn ngữ đó. Hãy bắt đầu câu trả lời bằng mã ngôn ngữ trong ngoặc vuông "
                  f"(ví dụ [vi], [en], [zh], [es], [fr]) rồi mới viết nội dung.")
        stream_reply(gen, prompt, MODEL_TEXT, "[Claude Lễ Tân]", guess_lang(user_text),
                     detect_tag=True, fallback_text=user_text)
    except Exception as e:
        report_error(gen, guess_lang(user_text), "Lỗi xử lý văn bản", e)


# =====================================================================
# CỬA SỔ CHÍNH
# =====================================================================
class ResizableMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.inactivity_timer = QtCore.QTimer(self)
        self.inactivity_timer.setInterval(INACTIVITY_MS)
        self.inactivity_timer.setSingleShot(True)
        self.inactivity_timer.timeout.connect(self.reset_to_welcome_screen)

        log_emitter.poke_timer_signal.connect(self.poke_inactivity_timer)
        log_emitter.append_log_signal.connect(self.append_line)
        log_emitter.inline_log_signal.connect(self.append_inline)
        self.ui.type.installEventFilter(self)

    # --- hiển thị log (chỉ nối thêm, không dựng lại toàn bộ như trước) ---
    def append_line(self, text):
        if text == "\x00welcome":
            self.ui.textBrowser.clear()
            print_welcome_instructions()
            self.poke_inactivity_timer()
            return
        safe = html.escape(text).replace("\n", "<br>")
        self.ui.textBrowser.append(f"<div style='margin-bottom:5px;'>{safe}</div>")
        self._scroll_bottom()

    def append_inline(self, text):
        cur = self.ui.textBrowser.textCursor()
        cur.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cur.insertText(text)
        self.ui.textBrowser.setTextCursor(cur)
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.ui.textBrowser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def poke_inactivity_timer(self):
        self.inactivity_timer.start()

    def reset_to_welcome_screen(self):
        with _hist_lock:
            history.clear()
        self.ui.textBrowser.clear()
        stop_ai_speaking()
        print_welcome_instructions()

    def eventFilter(self, obj, event):
        if obj == self.ui.type and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                # Shift+Enter: xuống dòng; Enter: gửi
                if not (QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier):
                    text = self.ui.type.toPlainText().strip()
                    if text:
                        self.poke_inactivity_timer()
                        self.ui.type.clear()
                        threading.Thread(target=process_text_pipeline, args=(text,), daemon=True).start()
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ui.fit_to_window(self.width(), self.height())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = ResizableMainWindow()
    MainWindow.show()

    threading.Thread(target=_player_loop, daemon=True).start()
    threading.Thread(target=load_models, daemon=True).start()     # nạp mô hình ở nền, cửa sổ hiện ngay

    for key, (lang_code, lang_name) in LANG_MAP.items():
        keyboard.on_press_key(key, lambda e, k=key, lc=lang_code, ln=lang_name: start_recording(k, lc, ln))
        keyboard.on_release_key(key, lambda e, k=key: handle_release(k))

    sys.exit(app.exec())
