# -*- coding: utf-8 -*-
"""Lễ tân A.I - Fairy Garden Villa.

Luồng xử lý: giữ phím để nói -> nhả phím -> Whisper (faster-whisper) -> Claude (stream)
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
import thong_bao_mail as mail             # báo email cho chủ nhà khi có khách hỏi
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
TTS_LANGS = ['vi', 'en', 'zh', 'ko', 'ja', 'fr', 'es', 'ru', 'th', 'tl', 'ms', 'hi', 'it']
EDGE_VOICES = {
    'vi': 'vi-VN-HoaiMyNeural', 'en': 'en-US-AriaNeural', 'zh': 'zh-CN-XiaoxiaoNeural',
    'es': 'es-ES-ElviraNeural', 'fr': 'fr-FR-DeniseNeural',
    'ja': 'ja-JP-NanamiNeural', 'ko': 'ko-KR-SunHiNeural',
    'ru': 'ru-RU-SvetlanaNeural', 'th': 'th-TH-PremwadeeNeural', 'tl': 'fil-PH-BlessicaNeural',
    'ms': 'ms-MY-YasminNeural', 'hi': 'hi-IN-SwaraNeural', 'it': 'it-IT-ElsaNeural',
}
GTTS_CODES = {'zh': 'zh-CN', 'ms': 'id'}      # gTTS không có tiếng Malay -> dùng tiếng Indonesia (gần giống) khi không có edge-tts
EDGE_PREFERRED = {'ms'}                        # ngôn ngữ gTTS không có -> ưu tiên edge-tts nếu đã cài
# Tên ngôn ngữ trả về từ Whisper (Groq) -> mã
LANG_NAMES = {'vi': 'Tiếng Việt', 'en': 'English', 'zh': 'Chinese', 'es': 'Spanish', 'fr': 'French', 'ja': 'Japanese',
              'ko': 'Korean', 'ru': 'Russian', 'th': 'Thai', 'tl': 'Filipino (Tagalog)', 'ms': 'Malay', 'hi': 'Hindi',
              'it': 'Italian'}
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
_LANG_NAME = {'vietnamese': 'vi', 'english': 'en', 'chinese': 'zh', 'spanish': 'es', 'french': 'fr',
              'japanese': 'ja', 'korean': 'ko', 'russian': 'ru', 'thai': 'th', 'tagalog': 'tl', 'filipino': 'tl',
              'malay': 'ms', 'hindi': 'hi', 'italian': 'it'}
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
        'vi': "=== ĐÃ CHUYỂN SANG CHẾ ĐỘ: TIẾNG VIỆT ===",
        'en': "=== SWITCHED TO MODE: ENGLISH ===",
        'zh': "=== 已切换至模式：中文 ===",
        'es': "=== CAMBIADO AL MODO: ESPAÑOL ===",
        'fr': "=== PASSÉ EN MODE : FRANÇAIS ===",
        'auto': "=== CHẾ ĐỘ TỰ ĐỘNG NHẬN DIỆN ==="},
    'help_body': {
        'vi': "Cách sử dụng tại quầy: Nhấn và GIỮ phím, nói xong thì thả ra + đợi thêm 1s để hệ thống xử lý.",
        'en': "How to use at the counter: Press and HOLD the key, speak, then release and wait 1s for processing.",
        'zh': "柜台使用方法：按住按键说话，说完后松开并等待 1 秒进行处理。",
        'es': "Cómo usar en el mostrador: Mantenga presionada la tecla, hable, luego suelte y espere 1s.",
        'fr': "Comment utiliser au comptoir : Appuyez et MAINTENEZ la touche, parlez, puis relâchez.",
        'auto': "How to use at the counter: Press and HOLD the key, speak, then release and wait 1s for processing."},
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
    'ja': "わかりました、質問を受け付けました。", 'ko': "알겠습니다, 질문을 접수했습니다.",
    'ru': "Хорошо, я получил ваш вопрос.", 'th': "รับทราบค่ะ ฉันได้รับคำถามของคุณแล้ว",
    'tl': "Sige, natanggap ko na ang inyong tanong.", 'ms': "Baik, saya sudah menerima soalan anda.",
    'hi': "ठीक है, मुझे आपका प्रश्न मिल गया है।", 'it': "Capito, ho ricevuto la sua domanda."}
# Nhấn-nhả quá nhanh HOẶC nhấn mà không nói gì -> cùng một thông báo
WARN_HOLD = {
    'vi': "Quý khách nhấn và nhả phím quá nhanh, hoặc nhấn phím mà không nói gì. Xin hãy nhấn và giữ phím để nói, và chỉ nhả phím khi nói xong.",
    'en': "You pressed and released the key too quickly, or pressed it without speaking. Please press and hold the key to speak, and release it only when you have finished.",
    'zh': "您按键后松开得太快，或者按键后没有说话。请按住按键说话，说完后再松开。",
    'es': "Ha pulsado y soltado la tecla demasiado rápido, o la ha pulsado sin hablar. Por favor, mantenga pulsada la tecla mientras habla y suéltela solo al terminar.",
    'fr': "Vous avez appuyé et relâché la touche trop vite, ou appuyé sans parler. Veuillez maintenir la touche enfoncée pour parler, et ne la relâcher qu'une fois terminé.",
    'ja': "キーを押してすぐに離したか、押したまま話されませんでした。キーを押し続けて話し、話し終えてから離してください。",
    'ko': "키를 너무 빨리 눌렀다 놓으셨거나, 누르고 말씀하지 않으셨습니다. 키를 누른 채 말씀하시고, 말씀이 끝난 후에만 놓아 주세요.",
    'ru': "Вы слишком быстро нажали и отпустили клавишу или нажали её, ничего не сказав. Пожалуйста, нажмите и удерживайте клавишу, пока говорите, и отпустите её только после окончания.",
    'th': "คุณกดแล้วปล่อยปุ่มเร็วเกินไป หรือกดปุ่มแต่ไม่ได้พูดอะไร กรุณากดปุ่มค้างไว้ขณะพูด และปล่อยเมื่อพูดจบเท่านั้น",
    'tl': "Masyadong mabilis ang pagpindot at pagbitaw ninyo sa key, o pinindot ninyo ito nang hindi nagsasalita. Pakipindot at hawakan ang key habang nagsasalita, at bitawan lamang kapag tapos na.",
    'ms': "Anda menekan dan melepaskan kekunci terlalu cepat, atau menekan tanpa bercakap. Sila tekan dan tahan kekunci semasa bercakap, dan lepaskan hanya apabila selesai.",
    'hi': "आपने बटन बहुत जल्दी दबाकर छोड़ दिया, या बटन दबाकर कुछ बोला नहीं। कृपया बोलते समय बटन दबाए रखें, और बोलना खत्म होने पर ही छोड़ें।",
    'it': "Ha premuto e rilasciato il tasto troppo in fretta, oppure lo ha premuto senza parlare. Tenga premuto il tasto mentre parla e lo rilasci solo al termine."}
ERROR_SPOKEN = {
    'vi': "Xin lỗi, hệ thống đang gặp sự cố kết nối. Quý khách vui lòng liên hệ nhân viên qua các cách liên lạc đặt tại quầy.",
    'en': "Sorry, the system has a connection problem. Please contact our staff using the contact details at the counter.",
    'zh': "抱歉，系统连接出现问题。请通过柜台上的联系方式联系工作人员。",
    'es': "Lo siento, hay un problema de conexión. Por favor contacte al personal con los datos del mostrador.",
    'fr': "Désolé, problème de connexion. Veuillez contacter le personnel avec les coordonnées du comptoir.",
    'ja': "申し訳ありません、接続に問題があります。カウンターの連絡先からスタッフにご連絡ください。",
    'ko': "죄송합니다, 연결에 문제가 있습니다. 카운터에 있는 연락처로 직원에게 문의해 주세요.",
    'ru': "Извините, проблема с подключением. Пожалуйста, свяжитесь с персоналом по контактам на стойке.",
    'th': "ขออภัยค่ะ ระบบมีปัญหาการเชื่อมต่อ กรุณาติดต่อพนักงานตามข้อมูลที่เคาน์เตอร์",
    'tl': "Pasensya na, may problema sa koneksyon. Makipag-ugnayan po sa staff gamit ang contact details sa counter.",
    'ms': "Maaf, terdapat masalah sambungan. Sila hubungi kakitangan melalui maklumat di kaunter.",
    'hi': "क्षमा करें, कनेक्शन में समस्या है। कृपया काउंटर पर दिए संपर्क विवरण से स्टाफ से संपर्क करें।",
    'it': "Mi dispiace, c'è un problema di connessione. Contatti il personale con i recapiti al banco."}


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


# Hướng dẫn: tiếng Anh luôn ở trên; dòng dưới luân phiên Việt <-> Trung mỗi WELCOME_SWAP_MS
WELCOME_TEXT = {
    'title': {'en': "HOW TO TALK TO ME", 'vi': "CÁCH NÓI CHUYỆN VỚI TÔI", 'zh': "如何与我对话"},
    's1': {'en': "PRESS and HOLD the corresponding language key",
           'vi': "NHẤN và GIỮ phím ngôn ngữ tương ứng",
           'zh': "按住对应的语言键"},
    's2': {'en': "SPEAK in your own language", 'vi': "NÓI bằng ngôn ngữ của bạn", 'zh': "用您的语言说话"},
    's3': {'en': "RELEASE the key when you finish", 'vi': "NHẢ phím khi nói xong", 'zh': "说完后松开按键"},
    'tip': {'en': "Keep holding while you speak - do not release early",
            'vi': "Giữ phím suốt lúc nói - đừng nhả sớm",
            'zh': "说话时请一直按住，不要过早松开"},
}
WELCOME_KEYS = "VIE&nbsp;·&nbsp;ENG&nbsp;·&nbsp;中&nbsp;·&nbsp;ESP&nbsp;·&nbsp;FRA&nbsp;·&nbsp;AUTO"
WELCOME_SWAP_MS = 5000
_welcome_second = 'vi'


def _step(n, key, second):
    t = WELCOME_TEXT[key]
    return (f"<tr><td width='46' align='center' bgcolor='#1f7a3d'><span style='color:#ffffff; font-size:22pt; font-weight:bold;'>{n}</span></td>"
            f"<td bgcolor='#eef7ef'><span style='color:#14532d; font-size:13pt; font-weight:bold;'>{t['en']}</span><br>"
            f"<span style='color:#2f2f2f; font-size:11pt; font-weight:bold;'>{t[second]}</span></td></tr>")


def welcome_html(second='vi'):
    t = WELCOME_TEXT
    return (
        "<div align='center' style='margin-bottom:6px;'>"
        f"<span style='color:#14532d; font-size:15pt; font-weight:bold;'>{t['title']['en']}</span><br>"
        f"<span style='color:#14532d; font-size:11pt; font-weight:bold;'>{t['title'][second]}</span></div>"
        "<table width='100%' cellspacing='5' cellpadding='5'>"
        + _step("1", 's1', second)
        + "<tr><td></td><td align='center' bgcolor='#14532d'><span style='color:#6bffb0; font-size:11pt; font-weight:bold;'>"
        + WELCOME_KEYS + "</span></td></tr>"
        + _step("2", 's2', second) + _step("3", 's3', second)
        + "</table>"
        "<div align='center' style='margin-top:6px;'>"
        f"<span style='color:#b45309; font-size:10pt; font-weight:bold;'>{t['tip']['en']}<br>{t['tip'][second]}</span></div>"
    )


def print_welcome_instructions():
    print("[Guide] Press and hold the corresponding language key (VIE/ENG/中/ESP/FRA/AUTO) to speak / Nhấn và giữ phím ngôn ngữ tương ứng để nói")
    log_emitter.append_log_signal.emit("\x00html" + welcome_html(_welcome_second))


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
    order = ["edge", "gtts"] if (TTS_ENGINE == "edge" or lang in EDGE_PREFERRED) else ["gtts", "edge"]
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
    for table in (ACK_PHRASES, WARN_HOLD, ERROR_SPOKEN):
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


MAX_GAIN = 8.0              # khuếch đại tối đa khi micro nhỏ (khuếch đại quá tay làm tiếng ồn giống tiếng nói)


def _normalize(audio):
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if 0.001 < peak < 0.6:                       # micro nhỏ -> khuếch đại có giới hạn để nghe rõ hơn
        audio = np.clip(audio * min(0.9 / peak, MAX_GAIN), -1.0, 1.0).astype(np.float32)
    return audio


def _wav_bytes(audio):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


_HALLUCINATIONS = (                          # câu Whisper hay bịa ra khi chỉ có im lặng / tiếng ồn (học từ phụ đề YouTube)
    "subscribe", "đăng ký kênh", "dang ky kenh", "ghiền mì gõ", "ghien mi go", "đừng quên đăng ký", "để không bỏ lỡ",
    "hẹn gặp lại các bạn trong", "cảm ơn các bạn đã xem", "cảm ơn các bạn đã theo dõi", "like và share", "bấm like",
    "thanks for watching", "thank you for watching", "thank you so much for watching", "see you in the next video",
    "like and subscribe", "don't forget to subscribe", "amara.org", "subtitles by", "sous-titres", "sous-titrage",
    "subtítulos", "gracias por ver", "merci d'avoir regardé", "字幕", "请订阅", "请不吝点赞", "感谢观看", "谢谢观看",
    "ご視聴ありがとう", "チャンネル登録", "시청해 주셔서", "구독과 좋아요",
)


def _drop_prompt_echo(text):
    """Bỏ kết quả Whisper bịa: lặp lại câu gợi ý, hoặc là câu 'đăng ký kênh/cảm ơn đã xem' quen thuộc."""
    low = text.lower()
    if any(h in low for h in _HALLUCINATIONS):
        return ""
    t = re.sub(r"[\W_]+", " ", low).strip()
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
    text = _drop_prompt_echo((r.text or "").strip())
    try:                                                   # Whisper tự báo "không có tiếng nói" ở mọi đoạn -> bỏ
        segs = getattr(r, "segments", None) or []
        g = lambda x, k: (x.get(k) if isinstance(x, dict) else getattr(x, k, None))
        if segs and all((g(x, "no_speech_prob") or 0) > 0.6 and (g(x, "avg_logprob") or 0) < -1.0 for x in segs):
            text = ""
    except Exception:
        pass
    return text, detected


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
_SENT_RE = re.compile(r".*?(?:[。！？।]+|[.!?]+(?=\s)|\n+)", re.S)
_TAG_RE = re.compile(r"\s*\[([A-Za-z\-]{2,5})\]\s*")
_VI_CHARS = set("àáãèéìíòóùúýăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ")


def split_sentences(buf):
    out, pos = [], 0
    for m in _SENT_RE.finditer(buf):
        out.append(m.group())
        pos = m.end()
    return out, buf[pos:]


def guess_lang(text):
    if any('぀' <= c <= 'ヿ' for c in text):          # kana -> tiếng Nhật (kiểm tra trước chữ Hán)
        return 'ja'
    if any('가' <= c <= '힣' for c in text):
        return 'ko'
    if any('Ѐ' <= c <= 'ӿ' for c in text):
        return 'ru'
    if any('฀' <= c <= '๿' for c in text):
        return 'th'
    if any('ऀ' <= c <= 'ॿ' for c in text):
        return 'hi'
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


def warn_hold(gen, lang):
    """Phát cảnh báo nhấn-nhả quá nhanh / nhấn mà không nói. Biết ngôn ngữ phím thì nói đúng ngôn ngữ đó;
    chế độ tự động (chưa biết ngôn ngữ) thì tiếng Anh trước rồi tiếng Việt."""
    if lang in WARN_HOLD:
        speak(gen, WARN_HOLD[lang], lang, cached=True)
    else:
        speak(gen, WARN_HOLD['en'], 'en', cached=True)
        speak(gen, WARN_HOLD['vi'], 'vi', cached=True)


SPEECH_RMS = 0.006          # mức năng lượng (RMS) tối thiểu của tiếng nói, khoảng -44 dBFS. Micro rất nhỏ -> giảm; môi trường ồn -> tăng
MIN_SPEECH_FRAMES = 8       # tối thiểu 8 khung 30ms (khoảng 0,25 giây) có tiếng nói
_FRAME = 480                # 30 ms ở 16 kHz


def analyze_audio(audio):
    """Phân tích nhanh bằng năng lượng. Trả về (có_tiếng_nói, audio_đã_cắt_lặng, thông_số_để_in_log)."""
    n = audio.size // _FRAME
    if n < 3:
        return False, audio, {"peak": 0.0, "p95": 0.0, "p10": 0.0, "frames": 0}
    rms = np.sqrt(np.mean(audio[:n * _FRAME].reshape(n, _FRAME) ** 2, axis=1))
    p95, p10 = float(np.percentile(rms, 95)), float(np.percentile(rms, 10))
    thr = max(SPEECH_RMS * 0.6, p10 * 3.0)
    idx = np.where(rms > thr)[0]
    info = {"peak": float(np.max(np.abs(audio))), "p95": p95, "p10": p10, "frames": int(idx.size)}
    contrast = p95 / max(p10, 1e-5)
    ok = p95 >= SPEECH_RMS and (contrast >= 2.0 or p95 >= 0.03) and idx.size >= MIN_SPEECH_FRAMES
    if not ok:
        return False, audio, info
    pad = 8                                                  # giữ thêm khoảng 0,25 giây ở hai đầu cho tự nhiên
    a, b = max(0, int(idx[0]) - pad), min(n, int(idx[-1]) + 1 + pad)
    return True, audio[a * _FRAME:b * _FRAME], info


def report_error(gen, lang, where, e):
    safe_print(f"[{where}]: {e}")
    mail.add("error", lang, reply=f"{where}: {e}")
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
        warn_hold(gen, lang)
        mail.add("empty", shown)
        return

    audio = np.concatenate(r["frames"], axis=0).reshape(-1).astype(np.float32)
    has_speech, audio, info = analyze_audio(audio)
    print(f"[Mic] đỉnh={info['peak']:.3f}  rms95={info['p95']:.4f}  rms10={info['p10']:.4f}  khung_có_tiếng={info['frames']}  -> {'CÓ tiếng nói' if has_speech else 'KHÔNG có tiếng nói'}")
    if not has_speech:                                     # nhấn giữ đủ lâu nhưng không có tiếng nói (im lặng / chỉ tiếng ồn)
        safe_print(msg('no_speech', shown))
        warn_hold(gen, lang)
        mail.add("empty", shown)
        return

    safe_print(msg('processing', shown))
    if lang and PLAY_ACK:
        speak(gen, ACK_PHRASES.get(lang, ACK_PHRASES['en']), lang if lang in ACK_PHRASES else 'en', cached=True)
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
        safe_print(f"[Khách hàng nói ({detected})]: {speech}")

        if not speech:                                     # nhấn nhưng không nói gì (hoặc chỉ có tiếng ồn)
            safe_print(msg('no_speech', shown))
            warn_hold(gen, lang)
            mail.add("empty", detected)
            return

        if not lang and PLAY_ACK:
            speak(gen, ACK_PHRASES.get(detected, ACK_PHRASES['en']), detected if detected in ACK_PHRASES else 'en', cached=True)

        if lang:
            prompt = f"Khách hàng vừa nói bằng {lang_name}: '{speech}'. Hãy trả lời hoàn toàn bằng {lang_name}."
        else:
            reply_lang = LANG_NAMES.get(detected) if detected in TTS_LANGS else "English"
            prompt = f"Khách hàng vừa nói: '{speech}'. Hãy trả lời hoàn toàn bằng {reply_lang}."
        tts_lang = detected if detected in TTS_LANGS else 'en'
        reply = stream_reply(gen, prompt, MODEL_VOICE, "[A.I Staff]", tts_lang)
        if reply:
            mail.add("chat", detected, speech, reply)
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

        self._welcome_only = False                      # True khi ô trắng chỉ có màn hình hướng dẫn
        self.welcome_timer = QtCore.QTimer(self)
        self.welcome_timer.setInterval(WELCOME_SWAP_MS)
        self.welcome_timer.timeout.connect(self.rotate_welcome)
        self.welcome_timer.start()

        log_emitter.poke_timer_signal.connect(self.on_key_activity)
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
        if text.startswith("\x00html"):                 # khối HTML dựng sẵn (màn hình hướng dẫn)
            self.ui.textBrowser.append(text[5:])
            self._welcome_only = True
            self._scroll_bottom()
            return
        safe = html.escape(text).replace("\n", "<br>")
        self.ui.textBrowser.append(f"<div style='margin-bottom:5px;'>{safe}</div>")
        self._scroll_bottom()

    def rotate_welcome(self):
        """Mỗi 5 giây đổi dòng phụ của hướng dẫn: Việt <-> Trung (tiếng Anh luôn ở trên)."""
        global _welcome_second
        if not self._welcome_only:
            return
        _welcome_second = 'zh' if _welcome_second == 'vi' else 'vi'
        self.ui.textBrowser.clear()
        self.ui.textBrowser.append(welcome_html(_welcome_second))

    def append_inline(self, text):
        cur = self.ui.textBrowser.textCursor()
        cur.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cur.insertText(text)
        self.ui.textBrowser.setTextCursor(cur)
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.ui.textBrowser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_key_activity(self):
        """Khách bấm phím = bắt đầu hội thoại: dừng luân phiên hướng dẫn (các dòng log hệ thống không làm dừng)."""
        self._welcome_only = False
        self.poke_inactivity_timer()

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
    MainWindow.showMaximized()          # bung kín màn hình; F11 = bật/tắt toàn màn hình thật (kiosk), Esc = thoát
    QtGui.QShortcut(QtGui.QKeySequence("F11"), MainWindow,
                    activated=lambda: MainWindow.showNormal() if MainWindow.isFullScreen() else MainWindow.showFullScreen())
    QtGui.QShortcut(QtGui.QKeySequence("Esc"), MainWindow, activated=MainWindow.showMaximized)

    threading.Thread(target=_player_loop, daemon=True).start()
    threading.Thread(target=load_models, daemon=True).start()     # nạp mô hình ở nền, cửa sổ hiện ngay

    for key, (lang_code, lang_name) in LANG_MAP.items():
        keyboard.on_press_key(key, lambda e, k=key, lc=lang_code, ln=lang_name: start_recording(k, lc, ln))
        keyboard.on_release_key(key, lambda e, k=key: handle_release(k))

    sys.exit(app.exec())
