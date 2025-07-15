import sys
import time
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
from loguru import logger
import json
from typing import Dict, Any, Optional

# 导入凭证配置管理器
from config.credentials_config import credentials_manager

# --- Configuration Section (Moved from gui/main_windows.py) ---
# 替换为你的预约系统登录页URL (通常是主业务域的登录入口)
LOGIN_URL = "https://gyytygyy.xidian.edu.cn/Views/User/Main.html?VenueNo=02"
# 替换为跳转到的验证页面的URL前缀
VERIFICATION_URL_PREFIX = "https://ids.xidian.edu.cn/authserver/login?service=https%3A%2F%2Fxxcapp.xidian.edu.cn%2Fa_xidian%2Fapi%2Fcas-login%2Findex%3Fredirect%3Dhttps%253A%252F%252Fxxcapp.xidian.edu.cn%252F%252Fuc%252Fapi%252Foauth%252Findex%253Fappid%253D200240927110038794%2526redirect%253Dhttp%25253a%25252f%25252fgyytygyy.xidian.edu.cn%25252fUser%25252fQYLogin%2526state%253DSTATE%26from%3Dwap"

CHROME_DRIVER_PATH = None  # If chromedriver is not in PATH, specify its full path


# --- Selenium WebDriver Thread (Moved from gui/main_windows.py) ---
class SeleniumLoginThread(QThread):
    """
    负责在独立线程中启动Selenium浏览器并处理登录。
    """
    login_success = Signal(dict)  # 信号：登录成功，传递凭证
    login_failed = Signal(str)  # 信号：登录失败，传递错误信息

    def __init__(self, login_url: str, verification_url_prefix: str, driver_path: str = None):
        super().__init__()
        self.login_url = login_url
        self.verification_url_prefix = verification_url_prefix
        self.driver_path = driver_path
        self.driver = None

    def run(self):
        try:
            logger.info("正在启动浏览器...")
            chrome_options = Options()
            # 根据需要可以添加更多选项，例如：
            # chrome_options.add_argument("--headless") # 如果你希望无头模式（不显示浏览器窗口），不推荐用于用户扫码
            # chrome_options.add_argument("--incognito") # 隐身模式
            # chrome_options.add_experimental_option("detach", True) # 浏览器关闭时不退出驱动进程

            service = None
            if self.driver_path:
                service = ChromeService(executable_path=self.driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)  # Selenium会尝试从PATH查找

            self.driver.set_page_load_timeout(30)  # 设置页面加载超时时间
            self.driver.get(self.login_url)
            logger.info(f"已打开登录入口页面 (A页面): {self.login_url}")

            # --- 步骤1: 等待从 A 页面跳转到 B 验证页面 ---
            start_time = time.time()
            max_wait_to_b = 30  # 最多等待30秒跳转到B页面
            is_on_verification_page = False
            logger.info("等待跳转到验证页面 (B页面)...")

            while time.time() - start_time < max_wait_to_b:
                current_url = self.driver.current_url
                if current_url.startswith(self.verification_url_prefix):
                    is_on_verification_page = True
                    logger.info(f"已跳转到验证页面: {current_url}")
                    break
                time.sleep(0.5)  # 每0.5秒检查一次

            if not is_on_verification_page:
                self.login_failed.emit(
                    f"未能在 {max_wait_to_b} 秒内跳转到验证页面 ({self.verification_url_prefix})。请检查URL或手动操作。")
                return

            # --- 步骤2: 等待从 B 验证页面返回 A 域 (登录成功) ---
            start_time = time.time()
            max_wait_return_to_a = 180  # 最多等待180秒（3分钟）让用户完成登录并返回A页面
            logged_in_and_returned = False
            logger.info("请在弹出的浏览器窗口中完成登录操作...")

            while time.time() - start_time < max_wait_return_to_a:
                current_url = self.driver.current_url
                # 检查是否已经回到了 A 域，并且不再是验证页面
                # 通常，登录成功后会回到主业务域下的某个页面，可能就是 LOGIN_URL 或其子路径
                if not current_url.startswith(self.verification_url_prefix) and \
                        current_url.startswith(self.login_url.split('/')[0] + "//" + self.login_url.split('/')[2]):
                    logged_in_and_returned = True
                    logger.info(f"已从验证页面返回主业务域 (A页面): {current_url}")
                    break
                time.sleep(1)  # 每秒检查一次

            if logged_in_and_returned:
                logger.info("用户可能已登录并返回主业务域，尝试获取凭证...")
                # 确保在正确的域下获取凭证
                self.driver.get(self.login_url)  # 再次访问主业务URL，确保在正确的域下
                time.sleep(2)  # 给页面一点时间加载完毕
                credentials = self._get_credentials_from_driver()
                self.login_success.emit(credentials)
            else:
                self.login_failed.emit(f"用户未在规定时间内完成登录并返回主业务域。当前URL: {self.driver.current_url}")

        except WebDriverException as e:
            logger.error(f"WebDriver错误：{e}")
            self.login_failed.emit(
                f"WebDriver错误：请确保浏览器驱动已正确安装并可在PATH中找到，或指定正确的路径。错误信息：{e}")
        except TimeoutException as e:
            logger.error(f"页面加载超时：{e}")
            self.login_failed.emit(f"页面加载超时，请检查网络或URL是否正确。错误信息：{e}")
        except Exception as e:
            logger.error(f"发生未知错误：{e}")
            self.login_failed.emit(f"发生未知错误：{e}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("浏览器已关闭。")

    def _get_credentials_from_driver(self) -> dict:
        """
        从Selenium WebDriver实例中获取登录凭证。
        目前主要获取Cookie，如果需要Token，可以执行JavaScript获取localStorage或sessionStorage。
        """
        credentials = {
            "cookies": {},
            "local_storage": {},
            "session_storage": {}
        }

        # 获取Cookie
        cookies = self.driver.get_cookies()
        for cookie in cookies:
            credentials["cookies"][cookie['name']] = cookie['value']
        logger.info(f"获取到 {len(cookies)} 条Cookie。")

        # 尝试获取Local Storage (可能包含Token)
        try:
            local_storage_script = "return window.localStorage;"
            local_storage_data = self.driver.execute_script(local_storage_script)
            if local_storage_data:
                credentials["local_storage"] = local_storage_data
            logger.info(f"获取到 Local Storage 数据。")
        except Exception as e:
            logger.warning(f"无法获取 Local Storage：{e}")

        # 尝试获取Session Storage (可能包含Token)
        try:
            session_storage_script = "return window.sessionStorage;"
            session_storage_data = self.driver.execute_script(session_storage_script)
            if session_storage_data:
                credentials["session_storage"] = session_storage_data
            logger.info(f"获取到 Session Storage 数据。")
        except Exception as e:
            logger.warning(f"无法获取 Session Storage：{e}")

        return credentials


# --- Login Page Class ---
class LoginPage(QWidget):
    """
    独立的登录页面，处理Selenium登录流程。
    """
    login_successful = Signal(dict)  # 登录成功信号，传递凭证

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录")  # 登录页面自己的标题
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
        self.login_button.setEnabled(False)  # 禁用按钮防止重复点击

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

