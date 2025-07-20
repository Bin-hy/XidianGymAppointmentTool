# gui/widgets.py

import webbrowser
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTextEdit,
    QFrame, QStackedWidget, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QTextCursor, QPixmap, QPainter, QBrush, QColor, QPainterPath, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from loguru import logger
from config.credentials_config import credentials_manager  # 用于用户状态组件
from tools.gui_logger import LogViewer, setup_gui_logger  # 导入日志查看器和设置函数


# --- LogWidget (集成日志查看器) ---
class LogWidget(QWidget):
    """日志显示组件，集成LogViewer"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        # 配置 Loguru 将日志输出到此 LogViewer
        setup_gui_logger(self.log_viewer)

    def initUI(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        log_group = QGroupBox("📋 应用日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(15, 15, 15, 15)
        log_layout.setSpacing(10)

        log_toolbar = QHBoxLayout()

        self.status_indicator = QLabel("🟢 准备就绪")
        self.status_indicator.setObjectName("statusIndicator")  # 用于 QSS 样式

        log_toolbar.addWidget(self.status_indicator)
        log_toolbar.addStretch()

        clear_btn = QPushButton("🗑️ 清空日志")
        clear_btn.setMaximumWidth(150)
        clear_btn.clicked.connect(self.clear_log)
        log_toolbar.addWidget(clear_btn)

        log_layout.addLayout(log_toolbar)

        self.log_viewer = LogViewer()  # 使用专用的日志查看器
        self.log_viewer.setObjectName("LogViewer")  # 用于 QSS 样式
        self.log_viewer.setMinimumHeight(150)
        self.log_viewer.setPlaceholderText("日志消息将在此处显示...")
        log_layout.addWidget(self.log_viewer)

        main_layout.addWidget(log_group)

    def clear_log(self):
        """清空日志"""
        self.log_viewer.clear()
        self.status_indicator.setText("🟢 准备就绪")

    def set_status(self, status_text):
        """设置状态指示器"""
        self.status_indicator.setText(status_text)


# --- UserStatusWidget (替换主窗口顶部行) ---
class UserStatusWidget(QWidget):
    """
    显示用户状态（登录/未登录）、用户名和头像，并包含登录/退出按钮。
    """
    login_logout_clicked = Signal()  # 信号：登录/注销按钮被点击

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_logged_in = False
        self.network_manager = QNetworkAccessManager(self)  # 用于头像下载
        self.initUI()
        self._load_initial_user_status()  # 初始化时加载状态

    def initUI(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 用户头像
        self.user_photo_label = QLabel()
        self.user_photo_label.setFixedSize(60, 60)  # 组件内头像略小
        self.user_photo_label.setScaledContents(True)
        self.user_photo_label.setStyleSheet("""
            QLabel {
                border-radius: 30px; /* 固定尺寸的一半，用于圆形 */
                background-color: #f0f0f0;
                border: 1px solid #ccc;
            }
        """)
        self.user_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.user_photo_label)

        # 用户名
        self.user_name_label = QLabel("用户名: 未登录")
        self.user_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.user_name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.user_name_label)
        layout.addStretch(1)

        # 登录/注销按钮
        self.login_logout_button = QPushButton("登录")
        self.login_logout_button.setObjectName("loginButton")  # 用于 QSS 样式
        self.login_logout_button.setFixedSize(100, 35)  # 按钮略小
        self.login_logout_button.clicked.connect(self.login_logout_clicked.emit)
        layout.addWidget(self.login_logout_button)

    def _load_initial_user_status(self):
        """根据凭证加载初始用户状态。"""
        if credentials_manager.get_cookies():
            self.set_logged_in_state(True)
            self._fetch_and_display_user_info()  # 如果有凭证，尝试获取并显示用户信息
        else:
            self.set_logged_in_state(False)

    def set_logged_in_state(self, is_logged_in: bool):
        """根据登录状态更新 UI。"""
        self.is_logged_in = is_logged_in
        if is_logged_in:
            self.login_logout_button.setText("注销")
            self.user_name_label.setText("用户名: 加载中...")  # 初始设置为加载中
        else:
            self.login_logout_button.setText("登录")
            self.user_name_label.setText("用户名: 未登录")
            self.user_photo_label.clear()  # 清空头像

    def _fetch_and_display_user_info(self):
        """获取用户信息并更新 UI。"""
        logger.info("UserStatusWidget: 正在尝试获取用户信息...")
        try:
            from API.User.API import GetUserInfo  # 延迟导入 GetUserInfo，避免循环依赖
            user_data_list = GetUserInfo()
            logger.debug(f"UserStatusWidget: GetUserInfo API 原始响应: {user_data_list}")  # 新增日志

            if user_data_list and isinstance(user_data_list, list) and len(user_data_list) > 0:
                user_info = user_data_list[0]
                logger.debug(f"UserStatusWidget: 解析后的用户信息: {user_info}")  # 新增日志

                user_name = user_info.get("MemberName", "未知用户")  # 将 "UserName" 改为 "MemberName"
                user_photo_url = user_info.get("Photo")

                self.user_name_label.setText(f"用户名: {user_name}")
                logger.info(f"UserStatusWidget: 已获取用户名: {user_name}")

                if user_photo_url:
                    self._load_and_display_avatar(user_photo_url)
                else:
                    self.user_photo_label.setText("无头像")
                    logger.warning("UserStatusWidget: 未获取到用户头像 URL。")
            else:
                self.user_name_label.setText("用户名: 获取失败 (数据为空或格式不正确)")  # 更具体的消息
                self.user_photo_label.setText("头像获取失败")
                logger.warning("UserStatusWidget: 获取用户信息成功，但返回数据为空或格式不正确。")
        except Exception as e:
            self.user_name_label.setText("用户名: 错误")
            self.user_photo_label.setText("头像错误")
            logger.error(f"UserStatusWidget: 获取用户信息时发生错误: {e}")

    def _load_and_display_avatar(self, url: str):
        """异步加载并显示头像图片。"""
        logger.info(f"UserStatusWidget: 正在加载头像: {url}")
        request = QNetworkRequest(QUrl(url))
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._on_avatar_download_finished(reply))

    def _on_avatar_download_finished(self, reply: QNetworkReply):
        """头像图片下载完成后的槽函数。"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            image_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                rounded_pixmap = QPixmap(pixmap.size())
                rounded_pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(rounded_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QBrush(pixmap))
                painter.setPen(Qt.NoPen)

                path = QPainterPath()
                path.addEllipse(rounded_pixmap.rect())
                painter.setClipPath(path)

                painter.drawRect(rounded_pixmap.rect())
                painter.end()

                scaled_pixmap = rounded_pixmap.scaled(self.user_photo_label.size(),
                                                      Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation)
                self.user_photo_label.setPixmap(scaled_pixmap)
                logger.info("UserStatusWidget: 头像加载成功。")
            else:
                self.user_photo_label.setText("头像加载失败")
                logger.error("UserStatusWidget: 无法从下载数据加载图片。")
        else:
            self.user_photo_label.setText("头像下载失败")
            logger.error(f"UserStatusWidget: 头像下载失败: {reply.errorString()}")
        reply.deleteLater()


# --- SportSelectionWidget ---
class SportSelectionWidget(QWidget):
    """
    显示运动图标按钮，并处理运动选择。
    """
    sport_selected = Signal(str)  # 信号：发射选定运动的名称

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sport_buttons = {}  # 存储导航项按钮的引用
        self.initUI()
        # 移除了 set_buttons_enabled 的调用，因为它现在在 initUI 的末尾被调用

    def initUI(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 调整边距
        layout.setSpacing(30)  # 导航项之间的间距
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 获取项目根目录以加载图片资源
        project_root = os.path.dirname(os.path.abspath(__file__))
        # 回溯查找项目根目录 (假设 assets 文件夹在 project_root/assets)
        while not os.path.exists(os.path.join(project_root, 'config')) and project_root != os.path.dirname(
                project_root):
            project_root = os.path.dirname(project_root)
        assets_path = os.path.join(project_root, 'assets')

        sports = {
            "羽毛球": "羽毛球.png",
            "乒乓球": "乒乓球.png",
            "篮球": "篮球.png",
            "健身": "健身.png"
        }

        for sport_name, icon_file in sports.items():
            icon_path = os.path.join(assets_path, icon_file)
            if not os.path.exists(icon_path):
                logger.warning(f"SportSelectionWidget: 未找到图标文件: {icon_path}")
                icon = QIcon()  # 使用空图标
            else:
                icon = QIcon(icon_path)

            button = QPushButton(sport_name)
            button.setIcon(icon)
            button.setIconSize(QSize(64, 64))
            button.setFixedSize(120, 120)
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)  # 图标在右侧，文字在左侧
            button.setStyleSheet("""
                QPushButton {
                    background-color: #f8f8f8;
                    border: 1px solid #ddd;
                    border-radius: 15px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #333;
                    padding: 10px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border: 1px solid #bbb;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                    border: 1px solid #aaa;
                }
                QPushButton:disabled {
                    background-color: #f0f0f0;
                    color: #aaa;
                    border: 1px solid #eee;
                }
            """)
            button.clicked.connect(lambda checked, s=sport_name: self.sport_selected.emit(s))
            self.sport_buttons[sport_name] = button
            layout.addWidget(button)

        # 在所有按钮创建完成后，调用 set_buttons_enabled
        self.set_buttons_enabled(False)  # 初始禁用

    def set_buttons_enabled(self, enable: bool):
        """启用或禁用运动图标按钮。"""
        for button in self.sport_buttons.values():
            button.setEnabled(enable)
