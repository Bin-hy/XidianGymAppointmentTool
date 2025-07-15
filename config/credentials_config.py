from typing import Dict, Any, Optional
import json
import os

class CredentialsConfig:
    """
    凭证配置类，用于存储从登录流程中获取的Cookies和其他凭证信息。
    """
    _instance = None
    _cookies: Dict[str, str] = {}
    _local_storage: Dict[str, Any] = {}
    _session_storage: Dict[str, Any] = {}
    _jwt_user_token: Optional[str] = None
    _project_root_dir: Optional[str] = None # 新增：存储项目根目录

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CredentialsConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化和加载
        if not self._cookies and not self._local_storage and not self._session_storage:
            # 初始时不立即加载，等待set_project_root_dir后再加载
            pass

    def set_project_root_dir(self, path: str):
        """
        设置项目根目录，并在设置后尝试加载凭证。
        此方法应在应用程序启动时调用一次。
        """
        if self._project_root_dir is None or self._project_root_dir != path:
            self._project_root_dir = path
            # logger.info(f"项目根目录已设置为: {self._project_root_dir}")
            print(f"INFO: 项目根目录已设置为: {self._project_root_dir}") # 临时打印
            self.load_credentials_from_file() # 设置根目录后加载凭证

    def _get_credentials_file_path(self) -> Optional[str]:
        """
        获取凭证文件的完整路径 (在 config 文件夹下)。
        """
        if self._project_root_dir:
            config_dir = os.path.join(self._project_root_dir, "config")
            os.makedirs(config_dir, exist_ok=True) # 确保config目录存在
            return os.path.join(config_dir, "credentials.json")
        # logger.error("项目根目录未设置，无法获取凭证文件路径。")
        print("ERROR: 项目根目录未设置，无法获取凭证文件路径。") # 临时打印
        return None

    def load_credentials_from_file(self):
        """
        从指定文件加载凭证。
        """
        file_path = self._get_credentials_file_path()
        if not file_path or not os.path.exists(file_path):
            # logger.warning(f"凭证文件未找到或路径无效: {file_path}")
            print(f"WARNING: 凭证文件未找到或路径无效: {file_path}") # 临时打印
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                credentials_data = json.load(f)

            self._cookies = credentials_data.get("cookies", {})
            self._local_storage = credentials_data.get("local_storage", {})
            self._session_storage = credentials_data.get("session_storage", {})

            self._jwt_user_token = self._cookies.get("JWTUserToken")

            # logger.info(f"凭证已从 {file_path} 加载。")
            print(f"INFO: 凭证已从 {file_path} 加载。") # 临时打印
        except (json.JSONDecodeError, Exception) as e:
            # logger.error(f"加载凭证文件失败: {e}")
            print(f"ERROR: 加载凭证文件失败: {e}") # 临时打印

    def save_credentials_to_file(self, credentials: Dict[str, Any]):
        """
        将凭证保存到指定文件。
        """
        file_path = self._get_credentials_file_path()
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(credentials, f, ensure_ascii=False, indent=4)
            # logger.info(f"凭证已保存到: {file_path}")
            print(f"INFO: 凭证已保存到: {file_path}") # 临时打印
            # 立即更新内存中的凭证，确保其他模块能拿到最新数据
            self.update_cookies(credentials.get("cookies", {}))
            self._local_storage = credentials.get("local_storage", {})
            self._session_storage = credentials.get("session_storage", {})

        except Exception as e:
            # logger.error(f"保存凭证失败：{e}")
            print(f"ERROR: 保存凭证失败：{e}") # 临时打印


    def get_cookies(self) -> Dict[str, str]:
        return self._cookies

    def get_jwt_user_token(self) -> Optional[str]:
        return self._jwt_user_token

    def get_local_storage(self) -> Dict[str, Any]:
        return self._local_storage

    def get_session_storage(self) -> Dict[str, Any]:
        return self._session_storage

    def update_cookies(self, new_cookies: Dict[str, str]):
        self._cookies.update(new_cookies)
        self._jwt_user_token = self._cookies.get("JWTUserToken")
        # logger.info("CredentialsConfig: Cookies已更新。")
        print("INFO: CredentialsConfig: Cookies已更新。") # 临时打印

    def clear_credentials(self):
        self._cookies = {}
        self._local_storage = {}
        self._session_storage = {}
        self._jwt_user_token = None
        # logger.info("CredentialsConfig: 所有凭证已清空。")
        print("INFO: CredentialsConfig: 所有凭证已清空。") # 临时打印

# 在模块加载时就初始化单例
credentials_manager = CredentialsConfig()