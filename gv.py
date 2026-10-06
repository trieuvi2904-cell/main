# -*- coding: utf-8 -*-
"""Widget `gv` dùng trong ui_letan.py: nhãn chữ HTML nền trong suốt, tự xuống dòng, không chặn chuột."""
from PyQt6 import QtCore, QtWidgets


class gv(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
