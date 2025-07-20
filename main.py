import os
import sys  # 导入 sys 用于 QApplication
from PySide6.QtWidgets import QApplication  # 导入 QApplication 用于 app.exec()
from gui.main_window import MainWindow  # 导入 MainWindow 直接
from config.credentials_config import credentials_manager
from config.app_config import config_manager
from loguru import logger

# 注意：此版本已移除 SQLite 数据库的导入和初始化。
# 定时任务将不会被持久化。

if __name__ == '__main__':
    project_root = os.path.dirname(os.path.abspath(__file__))

    credentials_manager.set_project_root_dir(project_root)
    config_manager.set_project_root_dir(project_root)

    logger.info(f"项目根目录已设置为: {project_root}")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

