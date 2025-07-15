# config/app_config.py

import os
from typing import Any, Optional
from loguru import logger
from dotenv import load_dotenv  # 导入 load_dotenv


class ConfigManager:
    """
    配置管理器，用于从环境变量加载应用程序设置。
    采用单例模式，确保整个应用只有一个配置实例。
    """
    _instance = None
    _project_root_dir: Optional[str] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        pass

    def set_project_root_dir(self, path: str):
        """
        设置项目根目录，并在设置后尝试加载 .env 文件。
        此方法应在应用程序启动时调用一次。
        """
        if self._project_root_dir is None or self._project_root_dir != path:
            self._project_root_dir = path
            dotenv_path = os.path.join(path, '.env')  # .env 文件通常位于项目根目录

            if os.path.exists(dotenv_path):
                load_dotenv(dotenv_path)  # 从 .env 文件加载环境变量
                logger.info(f"ConfigManager: 已从 {dotenv_path} 加载环境变量。")
            else:
                logger.warning(f"ConfigManager: .env 文件未找到: {dotenv_path}。将尝试从系统环境变量获取配置。")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取环境变量的值。
        直接从 os.environ 中获取，不支持点号访问嵌套配置。
        例如，对于 EMAIL_SMTP_SERVER，直接使用 "EMAIL_SMTP_SERVER" 作为 key。
        """
        value = os.environ.get(key)
        if value is None:
            logger.warning(f"ConfigManager: 环境变量 '{key}' 未设置，将使用默认值: {default}")
            return default
        return value


# 创建并导出配置管理器单例
config_manager = ConfigManager()

# 动态计算项目根目录，假设 .env 文件在项目根目录
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# 假设项目根目录在 tools 文件夹的上一级
project_root_for_test = os.path.dirname(current_file_dir)
config_manager.set_project_root_dir(project_root_for_test)