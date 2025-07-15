import sys
import time
import os
import datetime # 导入 datetime 模块
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, \
    QSizePolicy, QStackedWidget
from PySide6.QtCore import Qt, QUrl, QSize # 移除了 QTimer，因为不再需要周期性测试任务
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QPainterPath, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from loguru import logger  # 假设 logger 已正确导入并配置
import json
from typing import Dict, Any, Optional

# 导入凭证配置管理器
from config.credentials_config import credentials_manager
# 导入配置管理器
from config.app_config import config_manager
# 导入定时任务管理器
from core.schedule_task import scheduler_manager

# 导入各个预约子界面和登录页面
from gui.login_page import LoginPage
from gui.badminton_booking_page import BadmintonBookingPage
from gui.pingpong_booking_page import PingpongBookingPage
from gui.basketball_booking_page import BasketballBookingPage
from gui.fitness_booking_page import FitnessBookingPage

# --- Main Window Class ---
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("场馆预约工具")
        self.setGeometry(100, 100, 800, 600)  # 调整窗口大小，适应更多内容和QStackedWidget

        self.main_layout = QVBoxLayout(self)  # 主垂直布局

        # 顶部水平布局：头像、用户名、登录/退出按钮
        self.top_row_layout = QHBoxLayout()
        self.top_row_layout.setContentsMargins(20, 10, 20, 10)  # 设置边距
        self.top_row_layout.setSpacing(20)  # 设置控件间距

        # 用户头像
        self.user_photo_label = QLabel()
        self.user_photo_label.setFixedSize(80, 80)  # 设置头像大小
        self.user_photo_label.setScaledContents(True)  # 允许图片缩放以适应QLabel大小
        # 设置圆角样式
        self.user_photo_label.setStyleSheet("""
            QLabel {
                border-radius: 40px; /* 半径为宽度/高度的一半，实现圆形 */
                background-color: #f0f0f0; /* 默认背景色 */
                border: 1px solid #ccc; /* 边框 */
            }
        """)
        self.user_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_row_layout.addWidget(self.user_photo_label)

        # 用户名
        self.user_name_label = QLabel("用户名: 未登录")
        self.user_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.top_row_layout.addWidget(self.user_name_label)
        self.top_row_layout.addStretch(1)  # 添加伸缩空间，将登录按钮推到右侧

        # 登录/退出按钮
        self.login_logout_button = QPushButton("点击登录")
        self.login_logout_button.clicked.connect(self._handle_login_logout)
        self.login_logout_button.setFixedSize(120, 40)  # 设置按钮固定大小
        self.login_logout_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; /* 绿色背景 */
                color: white; /* 白色文字 */
                border-radius: 10px; /* 圆角 */
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049; /* 鼠标悬停时的颜色 */
            }
            QPushButton:pressed {
                background-color: #367c39; /* 鼠标按下时的颜色 */
            }
        """)
        self.top_row_layout.addWidget(self.login_logout_button)

        self.main_layout.addLayout(self.top_row_layout)  # 将顶部水平布局添加到主垂直布局

        # 状态标签（保持在第二行）
        self.status_label = QLabel("欢迎使用场馆预约工具！")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #555;")
        self.main_layout.addWidget(self.status_label)

        # 新增：运动图标行 (保持不变)
        self.sport_icons_layout = QHBoxLayout()
        self.sport_icons_layout.setContentsMargins(20, 20, 20, 20)
        self.sport_icons_layout.setSpacing(30)
        self.sport_icons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 居中对齐

        # 获取项目根目录，用于加载图片
        self.project_root = os.path.dirname(os.path.abspath(__file__))  # gui/main_window.py 所在目录
        # 向上回溯找到项目根目录 (假设 config 文件夹在项目根目录)
        while not os.path.exists(os.path.join(self.project_root, 'config')) and self.project_root != os.path.dirname(
                self.project_root):
            self.project_root = os.path.dirname(self.project_root)

        assets_path = os.path.join(self.project_root, 'assets')

        sports = {
            "羽毛球": "羽毛球.png",
            "乒乓球": "乒乓球.png",
            "篮球": "篮球.png",
            "健身": "健身.png"
        }

        self.sport_buttons = {}  # 存储运动按钮，方便后续启用/禁用
        for sport_name, icon_file in sports.items():
            icon_path = os.path.join(assets_path, icon_file)
            if not os.path.exists(icon_path):
                logger.warning(f"图标文件未找到: {icon_path}")
                icon = QIcon()  # 使用空图标
            else:
                icon = QIcon(icon_path)

            button = QPushButton(sport_name)
            button.setIcon(icon)
            button.setIconSize(QSize(64, 64))  # 设置图标大小
            button.setFixedSize(120, 120)  # 设置按钮固定大小
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
            button.clicked.connect(lambda checked, s=sport_name: self._on_sport_selected(s))
            button.setEnabled(False)  # 初始禁用，登录成功后启用
            self.sport_buttons[sport_name] = button
            self.sport_icons_layout.addWidget(button)

        self.main_layout.addLayout(self.sport_icons_layout)  # 将运动图标布局添加到主布局

        # QStackedWidget 用于显示不同的子界面 (包括登录页和预约页)
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # 添加登录页和预约子界面
        self._create_pages()

        self.setLayout(self.main_layout)  # 设置主布局

        self.network_manager = QNetworkAccessManager(self)  # 用于下载头像图片

        # 启动调度器
        scheduler_manager.start()
        logger.info("MainWindow: 定时任务调度器已启动。")

        # 移除了测试任务的添加
        # self._add_test_scheduler_job()

        # 初始加载用户状态（如果credentials.json存在）
        self._load_initial_user_status()

    # 移除了 _add_test_scheduler_job 方法
    # def _add_test_scheduler_job(self):
    #     """
    #     添加一个简单的、每5秒执行一次的测试任务，用于确认APScheduler是否在运行。
    #     """
    #     def test_job():
    #         logger.info(f"MainWindow: APScheduler 测试任务正在执行！当前时间: {datetime.datetime.now().strftime('%H:%M:%S')}")
    #         print(f"DEBUG: APScheduler 测试任务正在执行！当前时间: {datetime.datetime.now().strftime('%H:%M:%S')}")

    #     try:
    #         scheduler_manager._scheduler.add_job(
    #             test_job,
    #             'interval',
    #             seconds=5,
    #             id='test_scheduler_job',
    #             name='APScheduler Test Job',
    #             replace_existing=True
    #         )
    #         logger.info("MainWindow: 已添加每5秒执行一次的APScheduler测试任务。")
    #     except Exception as e:
    #         logger.error(f"MainWindow: 添加APScheduler测试任务失败: {e}")


    def closeEvent(self, event):
        """
        重写 closeEvent，在窗口关闭时关闭调度器。
        """
        logger.info("MainWindow: 应用程序即将关闭，正在关闭定时任务调度器...")
        scheduler_manager.shutdown()
        logger.info("MainWindow: 定时任务调度器已关闭。")
        super().closeEvent(event)


    def _create_pages(self):
        """
        创建并添加所有页面到 QStackedWidget。
        """
        # 登录页面 (索引 0)
        self.login_page = LoginPage()
        self.login_page.login_successful.connect(self._on_login_successful_from_page)  # 连接登录页的成功信号
        self.stacked_widget.addWidget(self.login_page)

        # 默认首页 (索引 1) - 在登录成功后显示
        self.default_main_page = QWidget()
        default_layout = QVBoxLayout(self.default_main_page)
        default_label = QLabel("请选择一个运动项目进行预约")
        default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_label.setStyleSheet("font-size: 20px; color: #666; padding: 50px;")
        default_layout.addWidget(default_label)
        self.stacked_widget.addWidget(self.default_main_page)

        # 各个预约子界面
        self.badminton_page = BadmintonBookingPage()
        self.stacked_widget.addWidget(self.badminton_page)  # Index 2

        self.pingpong_page = PingpongBookingPage()
        self.stacked_widget.addWidget(self.pingpong_page)  # Index 3

        self.basketball_page = BasketballBookingPage()
        self.stacked_widget.addWidget(self.basketball_page)  # Index 4

        self.fitness_page = FitnessBookingPage()
        self.stacked_widget.addWidget(self.fitness_page)  # Index 5

    def _handle_login_logout(self):
        """
        处理登录/退出按钮点击事件。
        """
        if self.login_logout_button.text() == "点击登录":
            # 当前未登录，切换到登录页面
            self.stacked_widget.setCurrentWidget(self.login_page)
            self.status_label.setText("请在登录页面完成登录。")
            self.login_logout_button.setEnabled(False)  # 登录过程中禁用主界面的登录按钮
        else:
            # 当前已登录，执行退出登录操作
            self._logout_user()

    def _logout_user(self):
        """
        执行用户退出登录操作。
        """
        logger.info("用户退出登录。")
        credentials_manager.clear_credentials()  # 清空凭证
        # 清除界面显示
        self.user_name_label.setText("用户名: 未登录")
        self.user_photo_label.clear()
        self.status_label.setText("您已退出登录。")
        self.login_logout_button.setText("点击登录")
        self.login_logout_button.setEnabled(True)
        self._enable_sport_buttons(False)  # 禁用运动按钮
        self.stacked_widget.setCurrentWidget(self.default_main_page)  # 返回默认主页或登录页

    def _on_login_successful_from_page(self, credentials: dict):
        """
        处理来自 LoginPage 的登录成功信号。
        """
        logger.info("从登录页面接收到登录成功信号。")
        self.status_label.setText("登录成功！")
        self.login_logout_button.setText("退出登录")  # 登录成功后按钮变为“退出登录”
        self.login_logout_button.setEnabled(True)  # 启用退出登录按钮
        self._enable_sport_buttons(True)  # 登录成功后启用运动按钮
        self.stacked_widget.setCurrentWidget(self.default_main_page)  # 切换到主界面

        # 登录成功后，尝试获取并显示用户信息
        self._fetch_and_display_user_info()

    def _on_sport_selected(self, sport_name: str):
        """
        处理运动图标点击事件，切换到对应的子界面。
        """
        logger.info(f"点击了 {sport_name} 图标。")
        # 根据运动名称切换 QStackedWidget 的页面
        if sport_name == "羽毛球":
            self.stacked_widget.setCurrentWidget(self.badminton_page)
        elif sport_name == "乒乓球":
            self.stacked_widget.setCurrentWidget(self.pingpong_page)
        elif sport_name == "篮球":
            self.stacked_widget.setCurrentWidget(self.basketball_page)
        elif sport_name == "健身":
            self.stacked_widget.setCurrentWidget(self.fitness_page)
        else:
            self.stacked_widget.setCurrentWidget(self.default_main_page)  # 回到默认页

        self.status_label.setText(f"已进入 {sport_name} 预约界面。")

    def _load_initial_user_status(self):
        """
        在应用启动时，如果已存在凭证，则尝试加载并显示用户信息。
        """
        logger.info("尝试加载初始用户状态...")
        if credentials_manager.get_cookies():
            self.login_logout_button.setText("退出登录")  # 显示为退出登录
            self.login_logout_button.setEnabled(True)
            self._enable_sport_buttons(True)  # 启用运动按钮
            self._fetch_and_display_user_info()  # 获取并显示用户信息
            self.status_label.setText("已加载上次登录状态。")
            self.stacked_widget.setCurrentWidget(self.default_main_page)  # 直接显示主界面
        else:
            self.login_logout_button.setText("点击登录")  # 显示为点击登录
            self.login_logout_button.setEnabled(True)
            self._enable_sport_buttons(False)  # 禁用运动按钮
            self.user_name_label.setText("用户名: 未登录")
            self.user_photo_label.clear()
            self.status_label.setText("点击 '点击登录' 按钮进行登录。")
            self.stacked_widget.setCurrentWidget(self.default_main_page)  # 初始显示主界面的默认页

    def _fetch_and_display_user_info(self):
        """
        获取用户信息并更新界面。
        """
        logger.info("尝试获取用户信息...")
        try:
            # 延迟导入 GetUserInfo，避免可能的循环依赖
            from API.User.API import GetUserInfo
            user_data_list = GetUserInfo()  # 调用API函数
            if user_data_list and isinstance(user_data_list, list) and len(user_data_list) > 0:
                user_info = user_data_list[0]  # 假设返回的是一个包含单个用户信息的列表
                user_name = user_info.get("UserName", "未知用户")
                user_photo_url = user_info.get("Photo")

                self.user_name_label.setText(f"用户名: {user_name}")
                logger.info(f"获取到用户名: {user_name}")

                if user_photo_url:
                    self._load_and_display_avatar(user_photo_url)
                else:
                    self.user_photo_label.setText("无头像")
                    logger.warning("未获取到用户头像URL。")
            else:
                self.user_name_label.setText("用户名: 获取失败")
                self.user_photo_label.setText("头像获取失败")
                logger.warning("获取用户信息失败或返回数据为空。")
        except Exception as e:
            self.user_name_label.setText("用户名: 获取失败")
            self.user_photo_label.setText("头像获取失败")
            logger.error(f"获取用户信息时发生错误: {e}")

    def _load_and_display_avatar(self, url: str):
        """
        异步加载头像图片并显示。
        """
        logger.info(f"正在加载头像: {url}")
        request = QNetworkRequest(QUrl(url))
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self._on_avatar_download_finished(reply))

    def _on_avatar_download_finished(self, reply: QNetworkReply):
        """
        头像图片下载完成后的槽函数。
        """
        if reply.error() == QNetworkReply.NetworkError.NoError:
            image_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                # 创建一个圆形的QPixmap
                rounded_pixmap = QPixmap(pixmap.size())
                rounded_pixmap.fill(Qt.GlobalColor.transparent)  # 填充透明背景

                painter = QPainter(rounded_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 抗锯齿
                painter.setBrush(QBrush(pixmap))  # 用原图填充
                painter.setPen(Qt.PenStyle.NoPen)  # 无边框

                # 绘制圆形路径
                path = QPainterPath()
                path.addEllipse(rounded_pixmap.rect())
                painter.setClipPath(path)  # 设置裁剪路径为圆形

                painter.drawRect(rounded_pixmap.rect())  # 绘制矩形，但会被裁剪成圆形
                painter.end()

                scaled_pixmap = rounded_pixmap.scaled(self.user_photo_label.size(),
                                                      Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation)
                self.user_photo_label.setPixmap(scaled_pixmap)
                logger.info("头像加载成功。")
            else:
                self.user_photo_label.setText("头像加载失败")
                logger.error("无法从下载的数据加载图片。")
        else:
            self.user_photo_label.setText("头像下载失败")
            logger.error(f"头像下载失败: {reply.errorString()}")
        reply.deleteLater()  # 清理reply对象

    def _enable_sport_buttons(self, enable: bool):
        """
        启用或禁用运动图标按钮。
        """
        for button in self.sport_buttons.values():
            button.setEnabled(enable)


# --- run_gui Function ---
def run_gui():
    """
    Function to run the GUI application.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

