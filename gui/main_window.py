import sys
import os
import datetime
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, \
    QMainWindow, QPushButton
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QPainterPath, QIcon

from loguru import logger

# 导入配置和凭证管理器
from config.credentials_config import credentials_manager
from config.app_config import config_manager
# 导入定时任务管理器
from core.schedule_task import scheduler_manager
# 导入 Firebase 管理器
from core.firebase_manager import firebase_manager  # 导入 firebase_manager

# 导入重构后的 GUI 组件
from gui.styles import STYLE_SHEET
from gui.widgets import LogWidget, UserStatusWidget, SportSelectionWidget

# 导入各个预约子界面和登录页面
from gui.login_page import LoginPage
from gui.booking_page.badminton_booking_page import BadmintonBookingPage
from gui.booking_page.pingpong_booking_page import PingpongBookingPage
from gui.booking_page.basketball_booking_page import BasketballBookingPage
from gui.booking_page.fitness_booking_page import FitnessBookingPage
# 导入任务管理页面
from gui.task_management_page import TaskManagementPage


# --- Main Window Class ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("场馆预约工具")
        self.setGeometry(100, 100, 900, 750)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        self.setStyleSheet(STYLE_SHEET)

        self.user_status_widget = UserStatusWidget()
        self.user_status_widget.login_logout_clicked.connect(self._handle_login_logout)
        self.main_layout.addWidget(self.user_status_widget)

        self.status_label = QLabel("欢迎使用场馆预约工具！")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #555; margin-top: 5px; margin-bottom: 5px;")
        self.main_layout.addWidget(self.status_label)

        self.sport_selection_widget = SportSelectionWidget()
        self.sport_selection_widget.sport_selected.connect(self._on_sport_selected)
        self.main_layout.addWidget(self.sport_selection_widget)

        self.task_management_button = QPushButton("⚙️ 任务管理")
        self.task_management_button.setFixedSize(150, 50)
        self.task_management_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border-radius: 10px;
                padding: 8px 15px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.task_management_button.clicked.connect(self._on_task_management_selected)
        task_btn_layout = QHBoxLayout()
        task_btn_layout.addStretch()
        task_btn_layout.addWidget(self.task_management_button)
        task_btn_layout.addStretch()
        self.main_layout.addLayout(task_btn_layout)

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        self._create_pages()

        self.log_widget = LogWidget()
        self.main_layout.addWidget(self.log_widget)

        # 启动调度器 (可以在Firebase初始化前启动，因为它不依赖Firebase)
        scheduler_manager.start()
        logger.info("MainWindow: 定时任务调度器已启动。")

        # 连接 Firebase 准备就绪信号
        firebase_manager.firebase_ready.connect(self._on_firebase_ready)
        # 连接 Firebase 认证状态改变信号，更新用户状态组件
        firebase_manager.auth_state_changed.connect(self.user_status_widget.set_user_id)

        # 初始UI更新将由 _on_firebase_ready 触发，确保Firebase就绪
        # self._update_ui_based_on_login_status() # 移除此处的直接调用

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
        self.login_page = LoginPage()
        self.login_page.login_successful.connect(self._on_login_successful_from_page)
        self.stacked_widget.addWidget(self.login_page)

        self.default_home_page = QWidget()
        default_layout = QVBoxLayout(self.default_home_page)
        default_label = QLabel("请选择一个运动项目进行预约。")
        default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_label.setStyleSheet("font-size: 20px; color: #666; padding: 50px;")
        default_layout.addWidget(default_label)
        self.stacked_widget.addWidget(self.default_home_page)

        self.badminton_page = BadmintonBookingPage()
        self.stacked_widget.addWidget(self.badminton_page)

        self.pingpong_page = PingpongBookingPage()
        self.stacked_widget.addWidget(self.pingpong_page)

        self.basketball_page = BasketballBookingPage()
        self.stacked_widget.addWidget(self.basketball_page)

        self.fitness_page = FitnessBookingPage()
        self.stacked_widget.addWidget(self.fitness_page)

        self.task_management_page = TaskManagementPage()
        self.stacked_widget.addWidget(self.task_management_page)

    def _on_firebase_ready(self):
        """
        当 Firebase 初始化并认证完成后触发。
        在此处加载持久化任务并更新初始UI状态。
        """
        logger.info("MainWindow: Firebase 已准备就绪。正在加载持久化任务并更新UI。")
        scheduler_manager.load_persisted_tasks()  # 加载持久化任务
        self._update_ui_based_on_login_status()  # 更新UI状态

    def _handle_login_logout(self):
        """
        处理来自 UserStatusWidget 的登录/退出按钮点击事件。
        """
        if self.user_status_widget.已登录:
            self._logout_user()
        else:
            self.stacked_widget.setCurrentWidget(self.login_page)
            self.status_label.setText("请在登录页面完成登录。")
            self.user_status_widget.登录注销按钮.setEnabled(False)

    def _logout_user(self):
        """
        执行用户退出登录操作。
        """
        logger.info("MainWindow: 用户正在退出登录。")
        credentials_manager.clear_credentials()
        # 触发 Firebase 匿名登录或清除认证状态
        # 在 Canvas 环境中，通常是重新加载页面或通过 Firebase API 登出
        # 这里我们模拟清除本地凭证，并依赖 FirebaseManager 的 auth_state_changed 信号来更新UI
        # 实际的 Firebase Auth 登出操作应在 credentials_manager.clear_credentials() 之后
        # 例如：firebase_manager.auth.signOut() # 如果有真实的 Firebase Auth 对象

        self._update_ui_based_on_login_status()  # 更新UI状态
        self.status_label.setText("您已退出登录。")
        self.stacked_widget.setCurrentWidget(self.default_home_page)

    def _on_login_successful_from_page(self, credentials: dict):
        """
        处理来自 LoginPage 的登录成功信号。
        """
        logger.info("MainWindow: 从 LoginPage 接收到登录成功信号。")
        credentials_manager.save_credentials_to_file(credentials)  # 保存凭证

        # 登录成功后，FirebaseManager 应该会通过其内部机制更新认证状态并发出信号
        # _on_firebase_ready 和 auth_state_changed 会处理后续的UI更新和任务加载
        self.status_label.setText("登录成功！")
        self.stacked_widget.setCurrentWidget(self.default_home_page)  # 切换到首页
        # 重新启用登录/退出按钮将由 _update_ui_based_on_login_status 处理

        # 登录成功后，主动加载羽毛球预约页面的数据 (如果需要立即显示最新数据)
        # 注意：如果 _update_ui_based_on_login_status 已经触发了，这里可以考虑移除重复调用
        if firebase_manager.is_ready() and firebase_manager.get_user_id():
            self.badminton_page.load_current_venue_state()

    def _on_sport_selected(self, sport_name: str):
        """
        处理运动图标点击事件，切换到对应的子界面。
        """
        logger.info(f"MainWindow: 选中运动: {sport_name}")
        if sport_name == "羽毛球":
            self.stacked_widget.setCurrentWidget(self.badminton_page)
        elif sport_name == "乒乓球":
            self.stacked_widget.setCurrentWidget(self.pingpong_page)
        elif sport_name == "篮球":
            self.stacked_widget.setCurrentWidget(self.basketball_page)
        elif sport_name == "健身":
            self.stacked_widget.setCurrentWidget(self.fitness_page)
        else:
            self.stacked_widget.setCurrentWidget(self.default_home_page)

        self.status_label.setText(f"已进入 {sport_name} 预约界面。")

    def _on_task_management_selected(self):
        """
        处理任务管理按钮点击事件，切换到任务管理界面。
        """
        logger.info("MainWindow: 切换到任务管理界面。")
        self.stacked_widget.setCurrentWidget(self.task_management_page)
        self.status_label.setText("已进入定时任务管理界面。")
        # 确保任务管理页面在显示时刷新其列表，它内部会检查Firebase状态
        self.task_management_page.load_tasks()

    def _update_ui_based_on_login_status(self):
        """
        根据当前登录状态更新 UI 元素。
        在启动时和登录/退出后调用。
        """
        # 现在直接检查 FirebaseManager 的认证状态
        is_logged_in = firebase_manager.get_user_id() is not None
        logger.info(f"MainWindow: 更新UI基于登录状态。已登录: {is_logged_in}")

        self.user_status_widget.set_logged_in_state(is_logged_in)
        self.sport_selection_widget.set_buttons_enabled(is_logged_in)
        self.task_management_button.setEnabled(is_logged_in)

        # 确保登录/退出按钮在Firebase准备就绪后始终启用，以便用户可以点击
        self.user_status_widget.登录注销按钮.setEnabled(True)

        if is_logged_in:
            self.stacked_widget.setCurrentWidget(self.default_home_page)
            self.status_label.setText("已加载上次登录状态。")
            self.badminton_page.load_current_venue_state()
        else:
            self.stacked_widget.setCurrentWidget(self.login_page)
            self.status_label.setText("点击 '登录' 按钮开始。")


# --- run_gui Function ---
def run_gui():
    """
    Function to run the GUI application.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
