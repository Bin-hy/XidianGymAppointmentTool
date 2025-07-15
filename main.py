import os

from config.app_config import config_manager
from gui.main_windows import run_gui
from config.credentials_config import credentials_manager # 导入凭证管理器


if __name__ == '__main__':
    # 获取当前main.py文件所在的目录，即项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_manager.set_project_root_dir(project_root)
    # 设置凭证管理器的项目根目录
    credentials_manager.set_project_root_dir(project_root)

    run_gui()
