# tools/gui_logger.py
import sys

from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Signal, QObject, Qt
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor  # 导入 QTextCursor

from tools.logger import logger


class LogSignal(QObject):
    """
    定义一个用于发送日志消息的信号。
    """
    message = Signal(str, str)  # message, level (e.g., "INFO", "ERROR")


log_signal = LogSignal()  # 创建一个全局信号实例


class LogViewer(QTextEdit):
    """
    一个用于在PySide6界面中显示日志的QTextEdit控件。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)  # 日志显示框通常是只读的
        self.setFont(QFont("Monospace", 9))  # 设置等宽字体，方便查看日志
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)

        # 定义不同日志级别的颜色和格式
        self.format_info = QTextCharFormat()
        self.format_info.setForeground(QColor("#333333"))  # 深灰色

        self.format_debug = QTextCharFormat()
        self.format_debug.setForeground(QColor("#666666"))  # 灰色

        self.format_warning = QTextCharFormat()
        self.format_warning.setForeground(QColor("#FFA500"))  # 橙色

        self.format_error = QTextCharFormat()
        self.format_error.setForeground(QColor("#FF0000"))  # 红色
        self.format_error.setFontWeight(QFont.Weight.Bold)

        self.format_critical = QTextCharFormat()
        self.format_critical.setForeground(QColor("#8B0000"))  # 深红色
        self.format_critical.setFontWeight(QFont.Weight.Black)

        self.format_success = QTextCharFormat()
        self.format_success.setForeground(QColor("#008000"))  # 绿色

        # 连接日志信号到槽函数
        log_signal.message.connect(self.append_log_message)

    def append_log_message(self, message: str, level: str):
        """
        接收日志消息并将其添加到QTextEdit中，根据级别应用不同颜色。
        """
        cursor = self.textCursor()
        # 修正: 使用 QTextCursor.End 作为枚举值
        cursor.movePosition(QTextCursor.End)
        cursor.insertBlock()

        current_format = QTextCharFormat()
        if level == "INFO":
            current_format = self.format_info
        elif level == "DEBUG":
            current_format = self.format_debug
        elif level == "WARNING":
            current_format = self.format_warning
        elif level == "ERROR":
            current_format = self.format_error
        elif level == "CRITICAL":
            current_format = self.format_critical
        elif level == "SUCCESS":
            current_format = self.format_success
        else:
            current_format = self.format_info  # 默认信息级别

        cursor.insertText(message, current_format)
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())  # 自动滚动到底部


class GuiLoguruHandler:
    """
    Loguru的自定义Handler，将日志记录通过信号发送到GUI。
    """

    def __init__(self):
        pass

    def write(self, message):
        """
        Loguru调用此方法来写入日志。
        `message` 参数是一个字符串，包含了 Loguru 已经格式化好的日志行。
        """
        # Loguru 传递给 `write` 方法的 `message` 参数已经是格式化后的字符串。
        # 因此，我们不需要再从 `message.record` 中去获取 `formatted` 键。

        record = message.record  # message 参数现在是一个 Loguru 的 Message 对象，它有一个 record 属性
        log_message = str(message).strip()  # 获取整个格式化后的日志字符串
        log_level = record["level"].name  # 获取日志级别名称

        # 发送信号到GUI
        log_signal.message.emit(log_message, log_level)

    def flush(self):
        """
        Loguru调用此方法来刷新缓冲区。
        """
        pass  # 在这里不需要特殊处理，因为消息是即时发送的


def setup_gui_logger(log_viewer_instance: LogViewer):
    """
    配置Loguru，使其将日志输出到GUI。
    :param log_viewer_instance: LogViewer的实例。
    """
    # 移除Loguru的默认处理器，避免重复输出到控制台（如果需要）
    # logger.remove(0) # 移除所有默认处理器

    # 添加自定义GUI处理器
    logger.add(GuiLoguruHandler(), format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {file}:{line} - {message}",
               level="INFO")

    # 如果您还想保留控制台输出，可以这样添加
    logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {file}:{line} - {message}",
               level="INFO")

    logger.info("GUI日志系统已启动。")

