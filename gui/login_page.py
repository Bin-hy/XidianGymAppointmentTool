import sys
import time
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt, Signal
# 移除 selenium 相关的导入，因为 SeleniumLoginThread 已经移动
from loguru import logger
from typing import Dict, Any, Optional

# 导入凭证配置管理器
from config.credentials_config import credentials_manager
# 从新的 threads 模块导入 SeleniumLoginThread
from gui.threads import SeleniumLoginThread

# --- 配置部分 ---
# 替换为你的预约系统登录页 URL (通常是主业务域的登录入口)
LOGIN_URL = "https://gyytygyy.xidian.edu.cn/Views/User/Main.html?VenueNo=02"
# 替换为跳转到的验证页面的 URL 前缀
VERIFICATION_URL_PREFIX = "https://ids.xidian.edu.cn/authserver/login?service=https%3A%2F%2Fxxcapp.xidian.edu.cn%2Fa_xidian%2Fapi%2Fcas-login%2Findex%3Fredirect%3Dhttps%253A%252F%252Fxxcapp.xidian.edu.cn%252F%252Fuc%252Fapi%252Foauth%252Findex%253Fappid%253D200240927110038794%2526redirect%253Dhttp%25253a%25252f%25252fgyytygyy.xidian.edu.cn%25252fUser%25252fQYLogin%2526state%253DSTATE%26from%3Dwap"

CHROME_DRIVER_PATH = None # 如果 chromedriver 不在 PATH 中，请指定其完整路径


# --- 登录页面类 ---
class LoginPage(QWidget):
    """
    独立的登录页面，处理 Selenium 登录流程。
    """
    login_successful = Signal(dict) # 信号：登录成功，传递凭证

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录") # 登录页面自己的标题
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("点击 '开始登录' 按钮，在弹出的浏览器中完成登录。")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; color: #333; margin-bottom: 20px;")
        self.layout.addWidget(self.status_label)

        self.login_button = QPushButton("开始登录")
        self.login_button.setFixedSize(150, 50)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 10px;
                font-size: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.login_button.clicked.connect(self._start_login_process)
        self.layout.addWidget(self.login_button)

        self.login_thread = None

    def _start_login_process(self):
        """
        启动登录流程。
        """
        if self.login_thread and self.login_thread.isRunning():
            QMessageBox.warning(self, "警告", "登录进程正在运行中，请勿重复点击。")
            return

        self.status_label.setText("正在启动浏览器，请稍候...")
        self.login_button.setEnabled(False) # 禁用按钮防止重复点击

        self.login_thread = SeleniumLoginThread(LOGIN_URL, VERIFICATION_URL_PREFIX, CHROME_DRIVER_PATH)
        self.login_thread.login_success.connect(self._on_login_success)
        self.login_thread.login_failed.connect(self._on_login_failed)
        self.login_thread.start()
        logger.info("登录线程已启动。")

    def _on_login_success(self, credentials: dict):
        """
        处理登录成功信号。
        """
        logger.info("登录成功信号接收。")
        self.status_label.setText("登录成功！")
        QMessageBox.information(self, "登录成功", "您已成功登录！")
        self.login_button.setEnabled(True)

        # 保存凭证
        credentials_manager.save_credentials_to_file(credentials)

        # 发射登录成功信号，通知父级（MainWindow）
        self.login_successful.emit(credentials)

    def _on_login_failed(self, error_message: str):
        """
        处理登录失败信号。
        """
        logger.error(f"登录失败信号接收：{error_message}")
        self.status_label.setText(f"登录失败：{error_message}")
        QMessageBox.critical(self, "登录失败", f"登录过程中发生错误：\n{error_message}")
        self.login_button.setEnabled(True)

