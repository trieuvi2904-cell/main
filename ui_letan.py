import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import pyqtProperty
QT6 = True

from gv import gv  # widget tuỳ chỉnh trong gv.py

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_FAMILY = "Be Vietnam Pro"      # font hiện đại, sạch, thiết kế riêng cho tiếng Việt (giấy phép OFL)


def load_fonts():
    """Nạp font đi kèm trong thư mục fonts/ rồi đặt làm font mặc định của ứng dụng."""
    fdir = os.path.join(BASE, "fonts")
    loaded = False
    if os.path.isdir(fdir):
        for name in sorted(os.listdir(fdir)):
            if name.lower().endswith(".ttf"):
                loaded |= QtGui.QFontDatabase.addApplicationFont(os.path.join(fdir, name)) >= 0
    app = QtWidgets.QApplication.instance()
    if loaded and app is not None:
        app.setFont(QtGui.QFont(FONT_FAMILY, 11))
    return loaded

Qt = QtCore.Qt
ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
ALIGN_TOP_CENTER = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
EASE = QtCore.QEasingCurve.Type.InOutSine

# Bảng màu: xanh lá đậm / xám / đen / trắng
WHITE = "#FFFFFF"
GREEN = "#6BFFB0"      # xanh lá sáng để nhấn
GRAY = "#E3EBE6"

BLINK_MS = 1800       # chu kỳ nhấp nháy của dòng hướng dẫn (ms)
BLINK_MIN = 0.35       # độ sáng thấp nhất khi nhấp nháy (0..1)
HINT_BLINK_MS = 1300     # chu kỳ nhấp nháy của khối hướng dẫn nhấn phím (ms)
HINT_BLINK_MIN = 0.12    # độ sáng thấp nhất (0..1): càng nhỏ càng nháy mạnh
FLOAT_PX = 5           # biên độ chữ "nhấp nhô"


def _html(title, line2, sub):
    """Cả khối tiếng Việt và khối tiếng Anh dùng đúng cùng cỡ chữ."""
    return (
        f'<div style="text-align:center;">'
        f'<div style="font-size:36px; font-weight:800; color:{GREEN};">{title}</div>'
        f'<div style="font-size:34px; font-weight:800; color:{WHITE}; margin-top:4px;">{line2}</div>'
        f'<div style="font-size:18px; font-weight:600; color:{GRAY}; margin-top:10px;">{sub}</div>'
        f'</div>'
    )


VN_HTML = _html("TÔI LÀ LỄ TÂN A.I", "HÃY HỎI TÔI BẤT CỨ THỨ GÌ",
                "(mượn đồ, đặt bữa sáng, đặt xe, hướng dẫn mọi thứ v..v)")
EN_HTML = _html("I AM THE A.I RECEPTIONIST", "ASK ME ANYTHING",
                "(borrow items, book breakfast, book a car, guidance on everything, etc.)")

CONTACT_HTML = (
    f'<div style="text-align:center;">'
    f'<div style="color:{GREEN}; font-size:11px; font-weight:700;">Breakfast, services, extend stay, chat with host'
    f' &nbsp;·&nbsp; Ăn sáng, dịch vụ, gia hạn phòng, chat với host</div>'
    f'<div style="color:{WHITE}; font-size:26px; font-weight:800; margin-top:0px;">hoianfairyvilla.com</div>'
    f'<div style="color:{WHITE}; font-size:14px; font-weight:700; margin-top:2px;">'
    f'<span style="color:{GREEN};">Tel / SĐT:</span> +(84) 903532168 &nbsp;|&nbsp; 0902434469'
    f' &nbsp;&nbsp; <span style="color:{GREEN};">Wifi Villa Garden 5g:</span> 88888888</div>'
    f'</div>'
)

HINT_EN = "PRESS & HOLD the language key to speak, release only when done"
HINT_VN = "NHẤN & GIỮ phím ngôn ngữ để nói, chỉ thả ra khi nói xong"
HINT_ZH = "中文：按住对应的语言键说话，说完再松开"
HINT_ES = "Español: mantenga pulsada la tecla de idioma y suéltela al terminar"
KEY_EN, KEY_VN = "LANGUAGE KEY", "PHÍM NGÔN NGỮ"
ARROW_X = 270          # vị trí mũi tên (trùng số "2168" trước đây) - nằm trên phím ngôn ngữ vật lý ngoài màn hình


def _fx_glow(widget, color, blur, alpha=200):
    fx = QtWidgets.QGraphicsDropShadowEffect(widget)
    c = QtGui.QColor(color)
    c.setAlpha(alpha)
    fx.setColor(c)
    fx.setOffset(0, 0)
    fx.setBlurRadius(blur)
    widget.setGraphicsEffect(fx)
    return fx


def _enum(obj, scope, name):
    sc = getattr(obj, scope, None)
    return getattr(sc, name) if sc is not None and hasattr(sc, name) else getattr(obj, name)


TYPE_EN = "OR TYPE YOUR MESSAGE AND PRESS ENTER"
TYPE_LANGS = [
    "HOẶC GÕ TIN NHẮN VÀ NHẤN ENTER",
    "或输入消息并按回车键发送",
    "O ESCRIBA UN MENSAJE Y PULSE ENTER",
    "OU TAPEZ UN MESSAGE ET APPUYEZ SUR ENTRÉE",
]

class GlowText(QtWidgets.QWidget):
    """Khối chữ HTML tự vẽ: có bóng đen, ánh sáng xanh 'thở', mờ dần và nhấp nhô.
    (Tự vẽ nên không cần QGraphicsEffect, chạy ổn định trên cả PyQt5/PyQt6.)"""

    def __init__(self, parent, rect, html, glow_color="#00E676"):
        super().__init__(parent)
        self.setGeometry(rect)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        w, h = rect.width(), rect.height()
        fmt = _enum(QtGui.QImage, "Format", "Format_ARGB32_Premultiplied")

        doc = QtGui.QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html)
        doc.setTextWidth(w)
        oy = max(0.0, (h - doc.size().height()) / 2)

        base = QtGui.QImage(w, h, fmt)
        base.fill(0)
        p = QtGui.QPainter(base)
        p.setRenderHint(_enum(QtGui.QPainter, "RenderHint", "TextAntialiasing"), True)
        p.translate(0, oy)
        doc.drawContents(p)
        p.end()

        self._base = base
        self._shadow = self._tint(base, QtGui.QColor(0, 0, 0))
        small = base.scaled(max(1, w // 6), max(1, h // 6),
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        blur = small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        self._glow_img = self._tint(blur, QtGui.QColor(glow_color))
        self._fade, self._glow, self._dy = 1.0, 0.6, 0.0

    @staticmethod
    def _tint(img, color):
        out = QtGui.QImage(img)
        p = QtGui.QPainter(out)
        p.setCompositionMode(_enum(QtGui.QPainter, "CompositionMode", "CompositionMode_SourceIn"))
        p.fillRect(out.rect(), color)
        p.end()
        return out

    def paintEvent(self, _):
        if self._fade <= 0.001:
            return
        p = QtGui.QPainter(self)
        p.translate(0, self._dy)
        p.setOpacity(self._fade * 0.75)
        p.drawImage(2, 2, self._shadow)
        p.setOpacity(self._fade * self._glow)
        p.drawImage(0, 0, self._glow_img)
        p.drawImage(0, 0, self._glow_img)
        p.setOpacity(self._fade)
        p.drawImage(0, 0, self._base)

    def _get_fade(self): return self._fade
    def _set_fade(self, v): self._fade = float(v); self.update()
    def _get_glow(self): return self._glow
    def _set_glow(self, v): self._glow = float(v); self.update()
    def _get_dy(self): return self._dy
    def _set_dy(self, v): self._dy = float(v); self.update()
    fade = pyqtProperty(float, _get_fade, _set_fade)
    glow = pyqtProperty(float, _get_glow, _set_glow)
    dy = pyqtProperty(float, _get_dy, _set_dy)


class ArrowDown(QtWidgets.QWidget):
    """Mũi tên xanh viền trắng chỉ xuống, nảy lên xuống để thu hút sự chú ý."""

    def __init__(self, parent, cx, top, w=64, h=60, amp=8):
        super().__init__(parent)
        self.setGeometry(cx - w // 2, top, w, h + amp)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._w, self._h, self._dy = w, h, 0.0

    def paintEvent(self, _):
        w, h = self._w, self._h
        p = QtGui.QPainter(self)
        p.setRenderHint(_enum(QtGui.QPainter, "RenderHint", "Antialiasing"), True)
        p.translate(0, self._dy)
        sw, hw, head = w * 0.34, w - 6, h * 0.5            # bề rộng thân, bề rộng đầu, chiều cao đầu
        cx = w / 2.0
        poly = QtGui.QPolygonF([
            QtCore.QPointF(cx - sw / 2, 3), QtCore.QPointF(cx + sw / 2, 3),
            QtCore.QPointF(cx + sw / 2, h - head), QtCore.QPointF(cx + hw / 2, h - head),
            QtCore.QPointF(cx, h - 2), QtCore.QPointF(cx - hw / 2, h - head),
            QtCore.QPointF(cx - sw / 2, h - head)])
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 170), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(poly)                                 # viền đen nền để nổi trên nền xanh
        g = QtGui.QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QtGui.QColor("#B6FFD6"))
        g.setColorAt(1, QtGui.QColor("#00E676"))
        p.setPen(QtGui.QPen(QtGui.QColor("#FFFFFF"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QtGui.QBrush(g))
        p.drawPolygon(poly)

    def _get_dy(self): return self._dy
    def _set_dy(self, v): self._dy = float(v); self.update()
    dy = pyqtProperty(float, _get_dy, _set_dy)


class FitView(QtWidgets.QGraphicsView):
    """Khung nhìn tự co giao diện vừa khít cửa sổ (giữ tỉ lệ, không cắt); phần thừa hai bên được phủ bằng
    chính ảnh nền phóng to và làm mờ nên luôn tràn kín màn hình, không có viền đen."""
    _backdrop_src = None
    _backdrop = None

    def set_backdrop(self, pm):
        if pm is not None and not pm.isNull():
            self._backdrop_src = pm.scaled(64, max(1, round(64 * pm.height() / pm.width())),
                                           Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._backdrop = None

    def drawBackground(self, painter, rect):
        if self._backdrop_src is None:
            return super().drawBackground(painter, rect)
        vp = self.viewport().size()
        if self._backdrop is None or self._backdrop.size() != vp:
            big = self._backdrop_src.scaled(vp, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                            Qt.TransformationMode.SmoothTransformation)
            x, y = (big.width() - vp.width()) // 2, (big.height() - vp.height()) // 2
            pm = big.copy(x, y, vp.width(), vp.height())
            p = QtGui.QPainter(pm)
            p.fillRect(pm.rect(), QtGui.QColor(0, 0, 0, 70))
            p.end()
            self._backdrop = pm
        painter.save()
        painter.resetTransform()
        painter.drawPixmap(0, 0, self._backdrop)
        painter.restore()

    def _fit(self):
        if self.scene() is not None:
            self.fitInView(self.scene().sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def showEvent(self, e):
        super().showEvent(e)
        self._fit()


class Ui_MainWindow(object):
    W, H = 1376, 768            # vùng nội dung
    M = 30                      # lề trang trí quanh nội dung (khung/dây leo nằm trong lề, không đè chữ)

    def setupUi(self, MainWindow):
        load_fonts()
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(self.W + 2 * self.M, self.H + 2 * self.M)
        MainWindow.setMinimumSize(640, 360)

        self.centralwidget = QtWidgets.QWidget()
        self.centralwidget.setObjectName("centralwidget")
        self.centralwidget.setFixedSize(self.W, self.H)

        # ---- Ảnh nền: đặt trong scene (kích thước nội dung + lề 2*M), nội dung nằm giữa ----
        self.label = QtWidgets.QLabel(self.centralwidget)          # giữ lại để tương thích, trong suốt
        self.label.setGeometry(0, 0, self.W, self.H)
        self.label.setObjectName("label")
        self.centralwidget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._art = QtGui.QPixmap(os.path.join(BASE, "anh nen app.png"))

        # ---- Khung phía trên bên phải: thông tin website / điện thoại / wifi ----
        self.info = GlowText(self.centralwidget, QtCore.QRect(752, 20, 606, 90), CONTACT_HTML)
        self.info._glow = 0.35
        self.info.setObjectName("info")

        # ---- Ô trắng hiển thị lệnh từ hệ thống (nhỏ hơn, nằm sát phải) ----
        self.textBrowser = QtWidgets.QTextBrowser(self.centralwidget)
        self.textBrowser.setGeometry(QtCore.QRect(878, 172, 420, 400))   # kéo dài xuống phần ô gõ phím cũ
        self.textBrowser.setAutoFillBackground(False)
        self.textBrowser.setObjectName("textBrowser")
        self.textBrowser.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.textBrowser.setStyleSheet(
            f"background: transparent; color:#16231C; font-family:'{FONT_FAMILY}'; font-size:16px; font-weight:600;")

        # ---- Ô gõ tin nhắn thủ công (nằm trong ô trắng) ----
        self.gv_type = gv(self.centralwidget)
        self.gv_type.setGeometry(QtCore.QRect(878, 490, 448, 36))
        self.gv_type.setObjectName("gv_type")
        self.gv_type.setStyleSheet(f"background:transparent; font-family:'{FONT_FAMILY}';")
        self.type = QtWidgets.QTextEdit(self.centralwidget)
        self.type.setGeometry(QtCore.QRect(878, 528, 448, 44))
        self.type.setObjectName("type")
        self.type.setPlaceholderText("Type here / Nhập tại đây…")
        # Khách chỉ nói bằng giọng nói: ẩn dòng hướng dẫn gõ phím và ô gõ (vẫn giữ widget để rec.py không bị lỗi)
        self.gv_type.setVisible(False)
        self.type.setVisible(False)
        self.type.setStyleSheet(
            f"QTextEdit {{ background:#F1F5F2; color:#16231C; border:1px solid #6FA88A; border-radius:8px; "
            f"padding:4px 8px; font-family:'{FONT_FAMILY}'; font-size:14px; font-weight:600; }}")

        # ---- Khung trái: tiếng Anh (trên) và tiếng Việt (dưới), cỡ chữ bằng nhau ----
        self.en_block = GlowText(self.centralwidget, QtCore.QRect(62, 188, 665, 172), EN_HTML)
        self.vn_block = GlowText(self.centralwidget, QtCore.QRect(62, 388, 665, 172), VN_HTML)
        self.divider = QtWidgets.QFrame(self.centralwidget)
        self.divider.setGeometry(150, 372, 490, 2)
        self.divider.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(107,255,176,0), stop:0.5 rgba(107,255,176,230), stop:1 rgba(107,255,176,0));")

        # ---- Khối hướng dẫn nhấn phím (phía dưới bên trái), nhấp nháy ----
        size = self._fit_px(max(HINT_EN, HINT_VN, key=len), 700, start=26, lo=13)
        tag = ('background-color:#00E676; color:#06210F; font-weight:900;')      # nhãn xanh sáng, chữ đen: tương phản cao
        self.hint = GlowText(self.centralwidget, QtCore.QRect(34, 636, 726, 70), (
            f'<div style="text-align:center;">'
            f'<div style="font-size:{size}px; font-weight:800; color:{WHITE};">'
            f'<span style="{tag}">&nbsp;PRESS &amp; HOLD&nbsp;</span>{HINT_EN[len("PRESS & HOLD"):]}</div>'
            f'<div style="font-size:{size}px; font-weight:800; color:{WHITE}; margin-top:4px;">'
            f'<span style="{tag}">&nbsp;NHẤN &amp; GIỮ&nbsp;</span>{HINT_VN[len("NHẤN & GIỮ"):]}</div></div>'))
        self.hint._glow = 0.2
        self.arrow = ArrowDown(self.centralwidget, ARROW_X, 699)
        self.key_label = QtWidgets.QLabel(
            f'<div style="color:{GREEN}; font-size:15px; font-weight:800;">{KEY_EN} &nbsp;·&nbsp; {KEY_VN}</div>'
            f'<div style="color:{GRAY}; font-size:12px; font-weight:600;">{HINT_ZH}</div>'
            f'<div style="color:{GRAY}; font-size:12px; font-weight:600;">{HINT_ES}</div>', self.centralwidget)
        self.key_label.setGeometry(ARROW_X + 44, 712, 440, 54)
        self.key_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # ---- Hai mã QR ở góc phải phía dưới ----
        self.qr_host_tile, self.qr_host_text = self._make_qr(
            770, "qr_host.png",
            '<div style="color:%s; font-size:14px; font-weight:800;">Scan the website to talk directly with the host</div>'
            '<div style="color:%s; font-size:12px; font-weight:600;">(choose <b>Quick chat</b> in the left corner of the website)</div>'
            '<div style="color:%s; font-size:13px; font-weight:700; margin-top:5px;">Quét mã web để nói chuyện trực tiếp với host</div>'
            '<div style="color:%s; font-size:12px; font-weight:600;">(chọn <b>Chat nhanh</b> ở góc trái website)</div>'
            % (GREEN, GRAY, WHITE, GRAY), 176)
        self.qr_bank_tile, self.qr_bank_text = self._make_qr(
            1092, "qr_bank.png",
            '<div style="color:%s; font-size:14px; font-weight:800;">QR for money transfer</div>'
            '<div style="color:%s; font-size:13px; font-weight:700;">MÃ QR chuyển tiền</div>'
            '<div style="color:%s; font-size:14px; font-weight:800; margin-top:5px;">TPBank</div>'
            '<div style="color:%s; font-size:14px; font-weight:800;">1000 1689 000</div>'
            '<div style="color:%s; font-size:12px; font-weight:600;">BIET THU DU LICH VUON CO TICH</div>' % (GREEN, WHITE, WHITE, WHITE, GRAY), 138)

        # Bọc giao diện 1376x768 trong một khung nhìn để tự co giãn theo cửa sổ (giữ đúng tỉ lệ)
        self.view = FitView(MainWindow)
        self.view.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.view.setStyleSheet("background:#07140E;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scene = QtWidgets.QGraphicsScene(self.view)
        self.view.setScene(self.scene)
        SW, SH = self.W + 2 * self.M, self.H + 2 * self.M
        if not self._art.isNull():
            self.art_item = self.scene.addPixmap(self._art.scaled(SW, SH, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                                  Qt.TransformationMode.SmoothTransformation))
            self.art_item.setZValue(-10)
        self.view.set_backdrop(self._art)
        self.proxy = self.scene.addWidget(self.centralwidget)
        self.proxy.setPos(self.M, self.M)
        self.scene.setSceneRect(0, 0, SW, SH)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setRenderHints(QtGui.QPainter.RenderHint.SmoothPixmapTransform | QtGui.QPainter.RenderHint.TextAntialiasing)
        MainWindow.setCentralWidget(self.view)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        self._type_idx = -1
        self.type_lang_timer = QtCore.QTimer(MainWindow)
        self.type_lang_timer.timeout.connect(self.switch_type_language)
        self.type_lang_timer.start(4000)
        self.switch_type_language()
        self._start_animations()

    def _make_qr(self, x, image, html, text_w=132):
        """Ô trắng chứa mã QR (vùng yên tĩnh trắng giúp quét dễ) + chú thích bên phải."""
        tile = QtWidgets.QLabel(self.centralwidget)
        tile.setGeometry(x, 612, 132, 132)
        tile.setStyleSheet("background:#FFFFFF; border-radius:10px;")
        tile.setAlignment(ALIGN_CENTER)
        pm = QtGui.QPixmap(os.path.join(BASE, image))
        tile.setPixmap(pm.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation))
        text = QtWidgets.QLabel(html, self.centralwidget)
        text.setGeometry(x + 138, 603, text_w, 154)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        return tile, text

    def fit_to_window(self, w=0, h=0):
        self.view._fit()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "A.I Receptionist"))

    # ------------------------------------------------------------------
    # Chuyển động nhẹ
    # ------------------------------------------------------------------
    def _start_animations(self):
        self._anims = []

        # 1) Chữ nhấp nhô lên xuống rất nhẹ + 2) ánh sáng xanh "thở" chậm
        for blk in (self.vn_block, self.en_block):
            a = QtCore.QPropertyAnimation(blk, b"dy", blk)
            a.setDuration(4200)
            a.setLoopCount(-1)
            a.setEasingCurve(EASE)
            a.setKeyValueAt(0.0, 0.0)
            a.setKeyValueAt(0.5, -float(FLOAT_PX))
            a.setKeyValueAt(1.0, 0.0)
            a.start()
            g = QtCore.QPropertyAnimation(blk, b"glow", blk)
            g.setDuration(2800)
            g.setLoopCount(-1)
            g.setEasingCurve(EASE)
            g.setKeyValueAt(0.0, 0.25)
            g.setKeyValueAt(0.5, 0.85)
            g.setKeyValueAt(1.0, 0.25)
            g.start()
            self._anims += [a, g]

        # 3) Khối hướng dẫn nhấn phím: nhấp nháy; mũi tên nảy lên xuống
        blink = QtCore.QPropertyAnimation(self.hint, b"fade", self.hint)
        blink.setDuration(HINT_BLINK_MS)
        blink.setLoopCount(-1)
        blink.setEasingCurve(EASE)
        blink.setKeyValueAt(0.0, 1.0)
        blink.setKeyValueAt(0.5, HINT_BLINK_MIN)
        blink.setKeyValueAt(1.0, 1.0)
        blink.start()
        bounce = QtCore.QPropertyAnimation(self.arrow, b"dy", self.arrow)
        bounce.setDuration(750)
        bounce.setLoopCount(-1)
        bounce.setEasingCurve(EASE)
        bounce.setKeyValueAt(0.0, 0.0)
        bounce.setKeyValueAt(0.5, 8.0)
        bounce.setKeyValueAt(1.0, 0.0)
        bounce.start()
        self._anims += [blink, bounce]

    def _fit_px(self, text, max_w, start=30, lo=11):
        family = FONT_FAMILY if FONT_FAMILY in QtGui.QFontDatabase.families() else QtGui.QFont().family()
        size = start
        while size > lo:
            f = QtGui.QFont(family)
            f.setPixelSize(size)
            f.setBold(True)
            if QtGui.QFontMetrics(f).horizontalAdvance(text) <= max_w:
                break
            size -= 1
        return size

    def switch_type_language(self):
        self._type_idx = (self._type_idx + 1) % len(TYPE_LANGS)
        self.gv_type.setText(
            f'<div style="color:#2E4A3B; font-size:12px; font-weight:700;">{TYPE_EN}</div>'
            f'<div style="color:#2E4A3B; font-size:12px; font-weight:600;">{TYPE_LANGS[self._type_idx]}</div>')


