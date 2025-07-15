# gui/threads.py

import threading
import time
import json
from PySide6.QtCore import QThread, Signal
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
from typing import Dict, Any, Optional

# Import credentials manager
from config.credentials_config import credentials_manager
# Import API functions
from API.Badminiton.API import GetVenueStateNew, OrderField # Assuming these are in API.Badminiton.API
from API.User.API import GetUserInfo # Assuming this is in API.User.API

# --- SeleniumLoginThread (Moved from gui/login_page.py) ---
class SeleniumLoginThread(QThread):
    """
    Responsible for launching Selenium browser and handling the login process in a separate thread.
    """
    login_success = Signal(dict) # Signal: login successful, pass credentials
    login_failed = Signal(str)   # Signal: login failed, pass error message

    def __init__(self, login_url: str, verification_url_prefix: str, driver_path: str = None):
        super().__init__()
        self.login_url = login_url
        self.verification_url_prefix = verification_url_prefix
        self.driver_path = driver_path
        self.driver = None

    def run(self):
        try:
            logger.info("SeleniumLoginThread: Starting browser...")
            chrome_options = Options()
            # chrome_options.add_argument("--headless") # Uncomment for headless mode
            # chrome_options.add_argument("--incognito")

            service = None
            if self.driver_path:
                service = ChromeService(executable_path=self.driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.set_page_load_timeout(30)
            self.driver.get(self.login_url)
            logger.info(f"SeleniumLoginThread: Opened login entry page (Page A): {self.login_url}")

            start_time = time.time()
            max_wait_to_b = 30
            is_on_verification_page = False
            logger.info("SeleniumLoginThread: Waiting to redirect to verification page (Page B)...")

            while time.time() - start_time < max_wait_to_b:
                current_url = self.driver.current_url
                if current_url.startswith(self.verification_url_prefix):
                    is_on_verification_page = True
                    logger.info(f"SeleniumLoginThread: Redirected to verification page: {current_url}")
                    break
                time.sleep(0.5)

            if not is_on_verification_page:
                self.login_failed.emit(f"SeleniumLoginThread: Failed to redirect to verification page ({self.verification_url_prefix}) within {max_wait_to_b} seconds.")
                return

            start_time = time.time()
            max_wait_return_to_a = 180
            logged_in_and_returned = False
            logger.info("SeleniumLoginThread: Please complete login in the popped-up browser window...")

            while time.time() - start_time < max_wait_return_to_a:
                current_url = self.driver.current_url
                if not current_url.startswith(self.verification_url_prefix) and \
                        current_url.startswith(self.login_url.split('/')[0] + "//" + self.login_url.split('/')[2]):
                    logged_in_and_returned = True
                    logger.info(f"SeleniumLoginThread: Returned to main business domain (Page A): {current_url}")
                    break
                time.sleep(1)

            if logged_in_and_returned:
                logger.info("SeleniumLoginThread: User likely logged in and returned, attempting to get credentials...")
                self.driver.get(self.login_url)
                time.sleep(2)
                credentials = self._get_credentials_from_driver()
                self.login_success.emit(credentials)
            else:
                self.login_failed.emit(f"SeleniumLoginThread: User did not complete login and return to main business domain within the allotted time. Current URL: {self.driver.current_url}")

        except WebDriverException as e:
            logger.error(f"SeleniumLoginThread: WebDriver error: {e}")
            self.login_failed.emit(f"WebDriver error: Please ensure browser driver is correctly installed and in PATH, or specify the correct path. Error: {e}")
        except TimeoutException as e:
            logger.error(f"SeleniumLoginThread: Page load timeout: {e}")
            self.login_failed.emit(f"Page load timeout, please check network or URL. Error: {e}")
        except Exception as e:
            logger.error(f"SeleniumLoginThread: An unknown error occurred: {e}")
            self.login_failed.emit(f"An unknown error occurred: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("SeleniumLoginThread: Browser closed.")

    def _get_credentials_from_driver(self) -> dict:
        """
        Retrieves login credentials from the Selenium WebDriver instance.
        Primarily gets Cookies; can execute JavaScript for localStorage/sessionStorage if needed.
        """
        credentials = {
            "cookies": {},
            "local_storage": {},
            "session_storage": {}
        }

        cookies = self.driver.get_cookies()
        for cookie in cookies:
            credentials["cookies"][cookie['name']] = cookie['value']
        logger.info(f"SeleniumLoginThread: Retrieved {len(cookies)} cookies.")

        try:
            local_storage_script = "return window.localStorage;"
            local_storage_data = self.driver.execute_script(local_storage_script)
            if local_storage_data:
                credentials["local_storage"] = local_storage_data
            logger.info(f"SeleniumLoginThread: Retrieved Local Storage data.")
        except Exception as e:
            logger.warning(f"SeleniumLoginThread: Failed to retrieve Local Storage: {e}")

        try:
            session_storage_script = "return window.sessionStorage;"
            session_storage_data = self.driver.execute_script(session_storage_script)
            if session_storage_data:
                credentials["session_storage"] = session_storage_data
            logger.info(f"SeleniumLoginThread: Retrieved Session Storage data.")
        except Exception as e:
            logger.warning(f"SeleniumLoginThread: Failed to retrieve Session Storage: {e}")

        return credentials

# --- GetVenueStateNewThread (Moved from badminton_booking_page.py) ---
class GetVenueStateNewThread(QThread):
    """
    Calls GetVenueStateNew API in a separate thread.
    """
    data_fetched = Signal(dict, int) # dict response, dateadd
    error_occurred = Signal(str)

    def __init__(self, dateadd: int, time_period: int):
        super().__init__()
        self.dateadd = dateadd
        self.time_period = time_period

    def run(self):
        try:
            logger.info(f"GetVenueStateNewThread: Fetching venue info: dateadd={self.dateadd}, TimePeriod={self.time_period}")
            response = GetVenueStateNew(self.dateadd, self.time_period)
            if response and response.get("errorcode") == 0 and response.get("resultdata"):
                result_data_str = response["resultdata"]
                try:
                    parsed_result_data = json.loads(result_data_str)
                    self.data_fetched.emit({"status": "success", "data": parsed_result_data}, self.dateadd)
                except json.JSONDecodeError as e:
                    self.error_occurred.emit(f"GetVenueStateNewThread: Failed to parse venue info JSON: {e}")
            elif response and response.get("message"):
                self.error_occurred.emit(f"GetVenueStateNewThread: Failed to get venue info: {response['message']}")
            else:
                self.error_occurred.emit("GetVenueStateNewThread: Failed to get venue info, unknown error or empty response.")
        except Exception as e:
            logger.error(f"GetVenueStateNewThread: Error calling GetVenueStateNew API: {e}")
            self.error_occurred.emit(f"GetVenueStateNewThread: Failed to call venue info API: {e}")

# --- GetUserInfoThread (New, for fetching user info in background) ---
class GetUserInfoThread(QThread):
    """
    Fetches user information in a separate thread.
    """
    user_info_fetched = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            logger.info("GetUserInfoThread: Attempting to fetch user info...")
            user_data_list = GetUserInfo()
            if user_data_list and isinstance(user_data_list, list) and len(user_data_list) > 0:
                self.user_info_fetched.emit({"status": "success", "data": user_data_list[0]})
            else:
                self.error_occurred.emit("GetUserInfoThread: Failed to fetch user info or data is empty.")
        except Exception as e:
            logger.error(f"GetUserInfoThread: Error fetching user info: {e}")
            self.error_occurred.emit(f"GetUserInfoThread: Error fetching user info: {e}")

