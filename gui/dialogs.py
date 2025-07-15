# gui/dialogs.py

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox, QLineEdit
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap
import requests  # Assuming requests might be used for image download in some dialogs
from io import BytesIO
from loguru import logger


class CustomMessageDialog(QDialog):
    """
    一个通用的自定义消息对话框。
    """

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
