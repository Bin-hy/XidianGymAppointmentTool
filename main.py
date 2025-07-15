import os
import sys  # Import sys for QApplication
from PySide6.QtWidgets import QApplication  # Import QApplication for app.exec()
from gui.main_window import MainWindow  # Import MainWindow directly
from config.credentials_config import credentials_manager
from config.app_config import config_manager
from loguru import logger

if __name__ == '__main__':
    project_root = os.path.dirname(os.path.abspath(__file__))

    credentials_manager.set_project_root_dir(project_root)
    config_manager.set_project_root_dir(project_root)

    logger.info(f"Project root set to: {project_root}")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

