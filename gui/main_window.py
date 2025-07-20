import sys
import os
import datetime
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, \
    QMainWindow, QPushButton  # 导入 QPushButton
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QPainterPath, QIcon

from loguru import logger

# 导入配置和凭证管理器
from config.credentials_config import credentials_manager
from config.app_config import config_manager
# 导入定时任务管理器
from core.schedule_task import scheduler_manager
# 导入 JWT token 工具
from tools.token_util import get_plaintext_token  # 新增导入

# 导入重构后的 GUI 组件
from gui.styles import STYLE_SHEET  # 导入新的样式表
from gui.widgets import LogWidget, UserStatusWidget, SportSelectionWidget  # 导入新的组件

# 导入各个预约子界面和登录页面
from gui.login_page import LoginPage
from gui.booking_page.badminton_booking_page import BadmintonBookingPage
from gui.booking_page.pingpong_booking_page import PingpongBookingPage
from gui.booking_page.basketball_booking_page import BasketballBookingPage
from gui.booking_page.fitness_booking_page import FitnessBookingPage
# 导入任务管理页面
from gui.task_management_page import TaskManagementPage  # 导入任务管理页面


# --- Main Window Class ---
class MainWindow(QMainWindow):  # 使用 QMainWindow 以便更好地应用样式和结构
    def __init__(self):
        super().__init__()
        self.setWindowTitle("广州研究院场馆预约工具")
        self.setGeometry(100, 100, 900, 750)  # 调整窗口大小，为更好的布局留出空间

        # 创建中央部件，并设置主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)  # 增加主布局的内边距
        self.main_layout.setSpacing(10)

        # 应用全局样式表
        self.setStyleSheet(STYLE_SHEET)

        # 顶部区域：用户状态组件
        self.user_status_widget = UserStatusWidget()
        self.user_status_widget.login_logout_clicked.connect(self._handle_login_logout)
        self.main_layout.addWidget(self.user_status_widget)

        # 状态标签 (用于显示一般性的应用状态消息)
        self.status_label = QLabel("欢迎使用场馆预约工具！")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #555; margin-top: 5px; margin-bottom: 5px;")
        self.main_layout.addWidget(self.status_label)

        # 运动选择组件
        self.sport_selection_widget = SportSelectionWidget()
        self.sport_selection_widget.sport_selected.connect(self._on_sport_selected)
        self.main_layout.addWidget(self.sport_selection_widget)

        # 新增：任务管理按钮
        self.task_management_button = QPushButton("⚙️ 任务管理")
        self.task_management_button.setFixedSize(150, 50)  # 设置按钮固定大小
        self.task_management_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d; /* 灰色 */
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
        # 将任务管理按钮添加到主布局中，可以考虑一个独立的QHBoxLayout来居中
        task_btn_layout = QHBoxLayout()
        task_btn_layout.addStretch()
        task_btn_layout.addWidget(self.task_management_button)
        task_btn_layout.addStretch()
        self.main_layout.addLayout(task_btn_layout)

        # QStackedWidget 用于不同页面的切换
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # 创建并添加页面到 QStackedWidget
        self._create_pages()

        # 底部区域：日志显示组件
        self.log_widget = LogWidget()
        self.main_layout.addWidget(self.log_widget)

        # 启动调度器
        scheduler_manager.start()
        logger.info("MainWindow: 定时任务调度器已启动。")

        # 根据登录状态更新 UI
        # 这一步只负责启用/禁用运动按钮和切换主页/登录页
        # UserStatusWidget 的内部状态和用户信息加载由其自身管理
        self._update_ui_based_on_login_status()

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
        # 登录页面 (作为 QStackedWidget 的一页)
        self.login_page = LoginPage()
        self.login_page.login_successful.connect(self._on_login_successful_from_page)
        self.stacked_widget.addWidget(self.login_page)

        # 默认主页
        self.default_home_page = QWidget()
        default_layout = QVBoxLayout(self.default_home_page)
        default_label = QLabel("请选择一个运动项目进行预约。")
        default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_label.setStyleSheet("font-size: 20px; color: #666; padding: 50px;")
        default_layout.addWidget(default_label)
        self.stacked_widget.addWidget(self.default_home_page)

        # 预约页面
        self.badminton_page = BadmintonBookingPage()
        self.stacked_widget.addWidget(self.badminton_page)

        self.pingpong_page = PingpongBookingPage()
        self.stacked_widget.addWidget(self.pingpong_page)

        self.basketball_page = BasketballBookingPage()
        self.stacked_widget.addWidget(self.basketball_page)

        self.fitness_page = FitnessBookingPage()
        self.stacked_widget.addWidget(self.fitness_page)

        # 新增：任务管理页面
        self.task_management_page = TaskManagementPage()
        self.stacked_widget.addWidget(self.task_management_page)

        # 根据登录状态设置初始显示的页面
        # 这一步将在 _update_ui_based_on_login_status 中处理
        pass

    def _handle_login_logout(self):
        """
        处理来自 UserStatusWidget 的登录/退出按钮点击事件。
        """
        if self.user_status_widget.is_logged_in:
            self._logout_user()
        else:
            self.stacked_widget.setCurrentWidget(self.login_page)
            self.status_label.setText("请在登录页面完成登录。")
            # 登录过程中暂时禁用登录/退出按钮
            self.user_status_widget.login_logout_button.setEnabled(False)

    def _logout_user(self):
        """
        执行用户退出登录操作。
        """
        logger.info("MainWindow: 用户正在退出登录。")
        credentials_manager.clear_credentials()
        # 退出时，显式设置 UserStatusWidget 为未登录状态
        self.user_status_widget.set_logged_in_state(False)
        self.sport_selection_widget.set_buttons_enabled(False)  # 禁用运动按钮
        self.task_management_button.setEnabled(False)  # 禁用任务管理按钮
        self.status_label.setText("您已退出登录。")
        self.stacked_widget.setCurrentWidget(self.login_page)  # 退出后切换回登录页
        self.user_status_widget.login_logout_button.setEnabled(True)  # 重新启用登录按钮

    def _on_login_successful_from_page(self, credentials: dict):
        """
        处理来自 LoginPage 的登录成功信号。
        """
        logger.info("MainWindow: 从 LoginPage 接收到登录成功信号。")
        # 登录成功后，显式设置 UserStatusWidget 为登录状态并触发信息获取
        self.user_status_widget.set_logged_in_state(True)
        self.user_status_widget._fetch_and_display_user_info()  # 确保获取并显示最新用户信息

        self.sport_selection_widget.set_buttons_enabled(True)  # 启用运动按钮
        self.task_management_button.setEnabled(True)  # 启用任务管理按钮
        self.status_label.setText("登录成功！")
        self.stacked_widget.setCurrentWidget(self.default_home_page)  # 切换到首页
        self.user_status_widget.login_logout_button.setEnabled(True)  # 重新启用退出登录按钮

    def _on_sport_selected(self, sport_name: str):
        """
        处理运动图标点击事件，切换到对应的子界面。
        """
        logger.info(f"MainWindow: 选中运动: {sport_name}")
        # 将运动名称映射到对应的页面并切换
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
        # 确保任务管理页面在显示时刷新其列表
        self.task_management_page.load_tasks()  # 调用 load_tasks 方法

    def _update_ui_based_on_login_status(self):
        """
        根据当前登录状态更新 UI 元素。
        在启动时和登录/退出后调用。
        """
        # 尝试获取凭证和 JWT 解析内容
        # get_plaintext_token 会检查过期并删除文件，如果凭证无效或过期，则返回 None
        # 注意：这里需要确保 credentials_manager._project_root_dir 已经被正确设置
        raw_token, parsed_cookies, parsed_jwt_payload = get_plaintext_token(credentials_manager._project_root_dir)

        # 如果 raw_token 为 None，表示没有凭证或凭证已过期并被删除
        is_logged_in_and_valid = bool(raw_token)

        if not is_logged_in_and_valid:
            # 未登录或凭证过期/无效
            self.user_status_widget.set_logged_in_state(False)
            self.stacked_widget.setCurrentWidget(self.login_page)  # 未登录时默认显示登录页
            self.status_label.setText("凭证无效或已过期，请点击 '开始登录' 按钮重新登录。")  # 更新提示信息
            # 确保登录按钮可用，运动按钮和任务管理按钮禁用
            self.user_status_widget.login_logout_button.setEnabled(True)  # 确保登录按钮可用
            self.sport_selection_widget.set_buttons_enabled(False)
            self.task_management_button.setEnabled(False)  # 禁用任务管理按钮
        else:
            # 已登录且凭证有效
            # UserStatusWidget 应该已经通过其自身初始化逻辑显示了正确的信息
            self.user_status_widget.set_logged_in_state(True)  # 确保 UserStatusWidget 状态正确
            # 重新触发用户信息获取，以防在 MainWindow 初始化时 UserStatusWidget 尚未完全加载完信息
            self.user_status_widget._fetch_and_display_user_info()

            self.stacked_widget.setCurrentWidget(self.default_home_page)
            self.status_label.setText("已加载上次登录状态。")
            self.sport_selection_widget.set_buttons_enabled(True)
            self.task_management_button.setEnabled(True)  # 启用任务管理按钮
            self.user_status_widget.login_logout_button.setEnabled(True)  # 确保注销按钮可用


# --- run_gui 函数 ---
def run_gui():
    """
    运行 GUI 应用程序的函数。
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

