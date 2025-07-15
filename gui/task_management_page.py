import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QStackedWidget  # 导入 QStackedWidget
)
from PySide6.QtCore import Qt, QTimer, Signal
from loguru import logger

# 导入定时任务管理器单例
from core.schedule_task import scheduler_manager


class TaskManagementPage(QWidget):
    """
    定时任务管理界面，用于显示和管理已添加的定时预约任务。
    """
    # 定义一个信号，用于在任务被删除时通知其他组件（可选，但有助于解耦）
    task_deleted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.load_tasks()  # 初始化时加载任务列表
        # 可以设置一个定时器，每隔一段时间自动刷新任务列表
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000)  # 每5秒刷新一次
        self.refresh_timer.timeout.connect(self.load_tasks)
        self.refresh_timer.start()

    def initUI(self):
        """初始化 UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # 顶部控制区域
        self.top_control_layout = QHBoxLayout()
        self.top_control_layout.setSpacing(10)

        self.title_label = QLabel("📅 定时任务管理")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #007bff;")
        self.top_control_layout.addWidget(self.title_label)
        self.top_control_layout.addStretch(1)  # 填充空间

        self.refresh_button = QPushButton("🔄 刷新任务")
        self.refresh_button.clicked.connect(self.load_tasks)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745; /* 绿色 */
                color: white;
                border-radius: 8px;
                padding: 8px 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        self.top_control_layout.addWidget(self.refresh_button)

        self.layout.addLayout(self.top_control_layout)

        # 使用 QStackedWidget 来管理表格和无任务提示
        self.content_stacked_widget = QStackedWidget()
        self.layout.addWidget(self.content_stacked_widget)

        # 页面 0: 任务列表表格
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(5)  # 任务ID, 任务名称, 下次执行时间, 状态, 操作
        self.task_table.setHorizontalHeaderLabels(["任务ID", "任务名称", "下次执行时间", "状态", "操作"])

        # 调整列宽以适应内容
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 任务ID自适应内容
        self.task_table.horizontalHeader().setSectionResizeMode(2,
                                                                QHeaderView.ResizeMode.ResizeToContents)  # 下次执行时间自适应内容
        self.task_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # 操作列固定
        self.task_table.setColumnWidth(4, 100)  # 操作列宽度

        # 禁止编辑单元格
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # 整行选择
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # 隐藏行号
        self.task_table.verticalHeader().setVisible(False)
        # 设置表格的最小高度，即使没有数据也保持一定大小
        self.task_table.setMinimumHeight(200)

        self.task_table.setStyleSheet("""
            QTableWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 5px;
                border: 1px solid #dee2e6;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #cfe2ff; /* 选中行背景色 */
                color: #212529;
            }
        """)
        self.content_stacked_widget.addWidget(self.task_table)  # 添加表格到堆叠布局

        # 页面 1: 无任务提示
        self.no_tasks_widget = QWidget()
        no_tasks_layout = QVBoxLayout(self.no_tasks_widget)
        self.no_tasks_label = QLabel("当前没有待执行的定时任务。")
        self.no_tasks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_tasks_label.setStyleSheet("font-size: 16px; color: #777; padding: 50px;")
        no_tasks_layout.addWidget(self.no_tasks_label)
        no_tasks_layout.addStretch(1)  # 确保标签居中并不会过度撑开
        self.no_tasks_widget.setMinimumHeight(200)  # 与表格保持一致的最小高度
        self.content_stacked_widget.addWidget(self.no_tasks_widget)  # 添加无任务提示页面

    def load_tasks(self):
        """从调度器加载并显示所有待执行的定时任务。"""
        logger.info("TaskManagementPage: 正在加载定时任务列表...")
        self.task_table.setRowCount(0)  # 清空现有行

        tasks = scheduler_manager.get_pending_jobs_info()

        if not tasks:
            logger.info("TaskManagementPage: 没有待执行的定时任务。切换到无任务提示页面。")
            self.content_stacked_widget.setCurrentIndex(1)  # 显示无任务提示页面
            return

        logger.info(f"TaskManagementPage: 已加载 {len(tasks)} 个定时任务。切换到任务表格页面。")
        self.content_stacked_widget.setCurrentIndex(0)  # 显示任务表格页面
        self.task_table.setRowCount(len(tasks))

        for row, task in enumerate(tasks):
            self.task_table.setItem(row, 0, QTableWidgetItem(task.get("id", "")))
            self.task_table.setItem(row, 1, QTableWidgetItem(task.get("name", "")))
            self.task_table.setItem(row, 2, QTableWidgetItem(task.get("next_run_time", "")))
            self.task_table.setItem(row, 3, QTableWidgetItem(task.get("status", "")))

            # 添加删除按钮
            delete_button = QPushButton("删除")
            delete_button.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545; /* 红色 */
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
                QPushButton:pressed {
                    background-color: #bd2130;
                }
            """)
            # 使用 lambda 表达式传递任务 ID
            delete_button.clicked.connect(lambda checked, task_id=task.get("id"): self.delete_task(task_id))

            self.task_table.setCellWidget(row, 4, delete_button)

    def delete_task(self, task_id: str):
        """
        删除指定的定时任务。
        :param task_id: 要删除的任务的ID。
        """
        reply = QMessageBox.question(self, "确认删除", f"确定要删除任务 '{task_id}' 吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if scheduler_manager.remove_job(task_id):
                QMessageBox.information(self, "删除成功", f"任务 '{task_id}' 已成功删除。")
                logger.info(f"TaskManagementPage: 用户已删除任务 '{task_id}'。")
                self.load_tasks()  # 刷新列表
                self.task_deleted.emit()  # 发出任务删除信号
            else:
                QMessageBox.critical(self, "删除失败", f"删除任务 '{task_id}' 失败，请检查日志。")
                logger.error(f"TaskManagementPage: 删除任务 '{task_id}' 失败。")

    def showEvent(self, event):
        """当页面显示时触发，确保任务列表是最新的。"""
        super().showEvent(event)
        self.load_tasks()
        self.refresh_timer.start()  # 页面显示时启动刷新定时器

    def hideEvent(self, event):
        """当页面隐藏时触发，停止刷新定时器。"""
        super().hideEvent(event)
        self.refresh_timer.stop()
