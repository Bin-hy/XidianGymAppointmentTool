# config/credentials_config.py

from typing import Dict, Any, Optional
import json
import os
from loguru import logger  # 导入 logger


class CredentialsConfig:
    """
    凭证配置类，用于存储从登录流程中获取的Cookies和其他凭证信息。
    """
    _instance = None
    _cookies: Dict[str, str] = {}
    _local_storage: Dict[str, Any] = {}
    _session_storage: Dict[str, Any] = {}
    _jwt_user_token: Optional[str] = None
    _project_root_dir: Optional[str] = None  # 存储项目根目录

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(CredentialsConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化和加载
        pass

    def set_project_root_dir(self, path: str):
        """
        设置项目根目录，并在设置后尝试加载凭证。
        此方法应在应用程序启动时调用一次。
        """
        if self._project_root_dir is None or self._project_root_dir != path:
            self._project_root_dir = path
            logger.info(f"CredentialsConfig: 项目根目录已设置为: {self._project_root_dir}")
            self.load_credentials_from_file()  # 设置根目录后加载凭证

    def _get_credentials_file_path(self) -> Optional[str]:
        """
        获取凭证文件的完整路径 (在 config 文件夹下)。
        """
        if self._project_root_dir:
            config_dir = os.path.join(self._project_root_dir, "config")
            os.makedirs(config_dir, exist_ok=True)  # 确保config目录存在
            return os.path.join(config_dir, "credentials.json")
        logger.error("CredentialsConfig: 项目根目录未设置，无法获取凭证文件路径。")
        return None

    def load_credentials_from_file(self):
        """
        从指定文件加载凭证。
        """
        file_path = self._get_credentials_file_path()
        if not file_path:
            logger.warning("CredentialsConfig: 凭证文件路径无效，跳过加载。")
            return

        if not os.path.exists(file_path):
            logger.warning(f"CredentialsConfig: 凭证文件未找到: {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                credentials_data = json.load(f)

            self._cookies = credentials_data.get("cookies", {})
            self._local_storage = credentials_data.get("local_storage", {})
            self._session_storage = credentials_data.get("session_storage", {})

            # 确保 JWTUserToken 从 cookies 中获取
            self._jwt_user_token = self._cookies.get("JWTUserToken")

            logger.info(f"CredentialsConfig: 凭证已从 {file_path} 加载。")
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"CredentialsConfig: 加载凭证文件失败: {e}")

    def save_credentials_to_file(self, credentials: Dict[str, Any]):
        """
        将凭证保存到指定文件。
        """
        file_path = self._get_credentials_file_path()
        if not file_path:
            logger.error("CredentialsConfig: 凭证文件路径无效，无法保存凭证。")
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(credentials, f, ensure_ascii=False, indent=4)
            logger.info(f"CredentialsConfig: 凭证已保存到: {file_path}")
            # 立即更新内存中的凭证，确保其他模块能拿到最新数据
            self.update_cookies(credentials.get("cookies", {}))
            self._local_storage = credentials.get("local_storage", {})
            self._session_storage = credentials.get("session_storage", {})

        except Exception as e:
            logger.error(f"CredentialsConfig: 保存凭证失败：{e}")

    def delete_credentials_file(self):
        """
        从磁盘上删除 credentials.json 凭证文件。
        """
        file_path = self._get_credentials_file_path()
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"CredentialsConfig: 凭证文件已删除: {file_path}")
            except Exception as e:
                logger.error(f"CredentialsConfig: 删除凭证文件失败: {e}")
        else:
            logger.warning("CredentialsConfig: 凭证文件不存在，无需删除。")

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
        logger.info("CredentialsConfig: Cookies已更新。")

    def clear_credentials(self):
        """
        清空内存中的所有凭证。
        """
        self._cookies = {}
        self._local_storage = {}
        self._session_storage = {}
        self._jwt_user_token = None
        logger.info("CredentialsConfig: 所有内存中的凭证已清空。")


# 在模块加载时就初始化单例
credentials_manager = CredentialsConfig()
