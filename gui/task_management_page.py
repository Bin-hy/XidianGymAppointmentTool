import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QFrame, QStackedWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPalette

from loguru import logger
from core.schedule_task import scheduler_manager


class TaskManagementPage(QWidget):
    """
    定时任务管理界面，显示已添加的定时任务，并允许删除。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        self.task_widgets = {}  # 存储任务ID到任务显示部件的映射

        # 标题和刷新按钮
        self.header_layout = QHBoxLayout()
        self.title_label = QLabel("📅 定时预约任务管理")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()

        self.refresh_button = QPushButton("🔄 刷新任务")
        self.refresh_button.setFixedSize(120, 35)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2471a3;
            }
        """)
        self.refresh_button.clicked.connect(self.load_tasks)
        self.header_layout.addWidget(self.refresh_button)
        self.layout.addLayout(self.header_layout)

        # 任务列表区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)  # 无边框
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # 任务从顶部开始排列
        self.tasks_layout.setSpacing(10)  # 任务项之间的间距
        self.scroll_area.setWidget(self.tasks_container)
        self.layout.addWidget(self.scroll_area)

        # 无任务提示页面
        self.no_tasks_page = QWidget()
        no_tasks_layout = QVBoxLayout(self.no_tasks_page)
        no_tasks_label = QLabel("暂无定时预约任务。")
        no_tasks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_tasks_label.setStyleSheet("font-size: 16px; color: #7f8c8d; padding: 50px;")
        no_tasks_layout.addWidget(no_tasks_label)

        # QStackedWidget 用于切换任务列表和无任务提示
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.tasks_container)  # Index 0: 任务列表
        self.stacked_widget.addWidget(self.no_tasks_page)  # Index 1: 无任务提示
        self.layout.addWidget(self.stacked_widget)

        # 初始化时加载任务
        self.load_tasks()

    def load_tasks(self):
        """
        从调度器获取所有待执行的定时任务并显示。
        """
        logger.info("TaskManagementPage: 正在加载定时任务列表...")
        # 清空现有显示
        for task_id, widget in self.task_widgets.items():
            widget.deleteLater()
        self.task_widgets.clear()

        pending_jobs = scheduler_manager.get_pending_jobs_info()

        if not pending_jobs:
            logger.info("TaskManagementPage: 没有待执行的定时任务。切换到无任务提示页面。")
            self.stacked_widget.setCurrentIndex(1)  # 显示无任务提示页面
            return
        else:
            self.stacked_widget.setCurrentIndex(0)  # 显示任务列表页面

        for job_info in pending_jobs:
            task_id = job_info["id"]
            task_name = job_info["name"]
            next_run_time = job_info["next_run_time"]
            status = job_info["status"]

            task_widget = self._create_task_widget(task_id, task_name, next_run_time, status)
            self.tasks_layout.addWidget(task_widget)
            self.task_widgets[task_id] = task_widget

        logger.info(f"TaskManagementPage: 已加载 {len(pending_jobs)} 个定时任务。")

    def _create_task_widget(self, task_id: str, task_name: str, next_run_time: str, status: str) -> QWidget:
        """
        创建单个任务的显示部件。
        """
        task_frame = QFrame()
        task_frame.setFrameShape(QFrame.Shape.StyledPanel)
        task_frame.setFrameShadow(QFrame.Shadow.Raised)
        task_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        task_layout = QHBoxLayout(task_frame)
        task_layout.setContentsMargins(10, 5, 10, 5)
        task_layout.setSpacing(15)

        # 任务信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.addWidget(QLabel(f"<b>任务名称:</b> {task_name}"))
        info_layout.addWidget(QLabel(f"<b>执行时间:</b> {next_run_time}"))
        info_layout.addWidget(QLabel(f"<b>状态:</b> {status}"))
        info_layout.addWidget(QLabel(f"<small>ID: {task_id}</small>"))  # 显示完整ID

        task_layout.addLayout(info_layout)
        task_layout.addStretch(1)

        # 操作按钮
        delete_button = QPushButton("❌ 删除")
        delete_button.setFixedSize(80, 30)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        delete_button.clicked.connect(lambda: self._confirm_delete_task(task_id))
        task_layout.addWidget(delete_button)

        return task_frame

    def _confirm_delete_task(self, task_id: str):
        """
        弹出确认对话框，确认是否删除任务。
        """
        reply = QMessageBox.question(self, '确认删除',
                                     f"您确定要删除任务 '{task_id}' 吗？\n删除后任务将无法恢复。",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_task(task_id)

    def _delete_task(self, task_id: str):
        """
        执行删除任务的操作。
        """
        logger.info(f"TaskManagementPage: 正在删除任务: {task_id}")
        success = scheduler_manager.remove_job(task_id)
        if success:
            QMessageBox.information(self, "删除成功", f"任务 '{task_id}' 已成功删除。")
            self.load_tasks()  # 刷新任务列表
        else:
            QMessageBox.critical(self, "删除失败", f"删除任务 '{task_id}' 失败。请检查日志。")

