import json
import datetime
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QTimeEdit, QComboBox, QGridLayout, QScrollArea,
    QMessageBox, QSizePolicy, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal, QDate, QTime
from PySide6.QtGui import QColor, QPalette

from loguru import logger

# 导入 API 函数 (OrderField 仍在此处使用)
from API.Badminiton.API import OrderField
# 导入定时任务管理器
from core.schedule_task import scheduler_manager
# 从新的 threads 模块导入 GetVenueStateNewThread
from gui.threads import GetVenueStateNewThread


# --- 羽毛球预约界面类 ---
class BadmintonBookingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        # 调整主布局的边距和间距，为内容留出更多空间
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.selected_fields = []  # 存储用户选中的所有场地数据
        self._current_rendered_dateadd = None  # 存储当前渲染数据对应的 dateadd
        self.field_buttons = {}  # 存储所有场地按钮的引用，key为 (FieldName, TimeSlot)

        # 第一行：预约日期选择和脚本执行日期时间选择
        self.top_controls_layout = QHBoxLayout()
        self.top_controls_layout.setSpacing(10)

        # 预约日期选择 (默认明天)
        self.date_label = QLabel("预约日期:")
        self.date_edit = QDateEdit(QDate.currentDate().addDays(1))  # 默认明天
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setMinimumDate(QDate.currentDate())  # 最小日期为今天
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.top_controls_layout.addWidget(self.date_label)
        self.top_controls_layout.addWidget(self.date_edit)

        # 脚本执行日期选择
        self.script_date_label = QLabel("脚本执行日期:")
        self.script_date_edit = QDateEdit(QDate.currentDate().addDays(1))  # 默认明天
        self.script_date_edit.setCalendarPopup(True)
        self.script_date_edit.setMinimumDate(QDate.currentDate())  # 最小日期为今天
        self.script_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.top_controls_layout.addWidget(self.script_date_label)
        self.top_controls_layout.addWidget(self.script_date_edit)

        # 脚本执行时间选择 (默认明天早上8点)
        self.script_time_label = QLabel("脚本执行时间:")
        self.script_time_edit = QTimeEdit(QTime(8, 0))  # 默认早上8点
        self.script_time_edit.setDisplayFormat("HH:mm")
        self.top_controls_layout.addWidget(self.script_time_label)
        self.top_controls_layout.addWidget(self.script_time_edit)

        # 时间段选择 (上午/下午/晚上)
        self.time_period_label = QLabel("时间段:")
        self.time_period_combo = QComboBox()
        self.time_period_combo.addItem("上午 (08:00-12:00)", 0)  # 假设0是上午
        self.time_period_combo.addItem("下午 (12:00-18:00)", 1)  # 假设1是下午
        self.time_period_combo.addItem("晚上 (18:00-22:00)", 2)  # 假设2是晚上
        self.time_period_combo.currentIndexChanged.connect(self._on_time_period_changed)
        self.top_controls_layout.addWidget(self.time_period_label)
        self.top_controls_layout.addWidget(self.time_period_combo)

        # 邮箱提醒输入框
        self.email_label = QLabel("邮箱提醒:")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("请输入接收提醒的邮箱地址 (可选)")
        self.email_input.setMinimumWidth(200)  # 确保输入框有足够的宽度
        self.top_controls_layout.addWidget(self.email_label)
        self.top_controls_layout.addWidget(self.email_input, 1)  # 给邮箱输入框一个伸缩因子，使其能扩展

        self.top_controls_layout.addStretch(1)  # 填充剩余空间
        self.layout.addLayout(self.top_controls_layout)

        # 第二行往下：场地信息显示区域
        self.fields_scroll_area = QScrollArea()
        self.fields_scroll_area.setWidgetResizable(True)
        # 设置 QScrollArea 的大小策略，使其垂直方向可扩展
        self.fields_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.fields_scroll_area.setFrameShape(QFrame.Shape.NoFrame) # 移除边框，减少占用空间

        self.fields_container = QWidget()
        self.fields_grid_layout = QGridLayout(self.fields_container)
        self.fields_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_grid_layout.setSpacing(5)  # 单元格之间的间距
        self.fields_scroll_area.setWidget(self.fields_container)
        self.layout.addWidget(self.fields_scroll_area)

        # 提交按钮
        self.submit_button = QPushButton("点击预约")
        self.submit_button.setFixedSize(200, 50)
        self.submit_button.setStyleSheet("""
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
        self.submit_button.clicked.connect(self._start_scheduling_task)
        self.submit_button.setEnabled(False)  # 初始禁用，选择场地后启用
        self.layout.addWidget(self.submit_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.get_venue_thread = None

        # 移除初始加载场地信息的调用，改为在登录成功后手动触发
        # self._fetch_initial_reference_venue_state()
        self._update_submit_button_state()  # 确保初始状态正确

        # 初始显示一个提示信息
        self._display_message("请先登录以查看和预约场地信息。", "info")


    def load_current_venue_state(self):
        """
        在登录成功后调用此方法，加载当前日期和时间段的场地信息。
        """
        logger.info("BadmintonBookingPage: 登录成功，正在加载当前场地信息...")
        self._fetch_venue_state() # 调用已有的获取场地状态方法

    def _on_date_changed(self, date: QDate):
        """预约日期选择框改变时触发，重新获取场地信息"""
        logger.info(f"预约日期选择改变为: {date.toString('yyyy-MM-dd')}")
        self._fetch_venue_state()

    def _on_time_period_changed(self, index: int):
        """时间段选择框改变时触发，重新获取场地信息"""
        time_period = self.time_period_combo.itemData(index)
        logger.info(f"时间段选择改变为: {self.time_period_combo.currentText()} (值: {time_period})")
        self._fetch_venue_state()

    def _calculate_date_add(self) -> int:
        """计算当前日期与选中预约日期之间的天数偏移量"""
        current_date = QDate.currentDate()
        selected_date = self.date_edit.date()
        return current_date.daysTo(selected_date)

    # 移除 _fetch_initial_reference_venue_state 方法，因为它不再需要
    # def _fetch_initial_reference_venue_state(self):
    #     """
    #     在初始化时获取昨天的场地信息作为参考。
    #     """
    #     logger.info("初始加载：正在获取昨天的场地信息作为参考...")
    #     self._clear_fields_display()
    #     self.submit_button.setEnabled(False)
    #     self.selected_fields = []
    #     self._clear_all_button_styles()

    #     initial_dateadd = -1  # -1 表示昨天
    #     initial_time_period = 0  # 默认上午

    #     if self.get_venue_thread and self.get_venue_thread.isRunning():
    #         self.get_venue_thread.quit()
    #         self.get_venue_thread.wait()

    #     self.get_venue_thread = GetVenueStateNewThread(initial_dateadd, initial_time_period)
    #     self.get_venue_thread.data_fetched.connect(self._on_venue_state_fetched)
    #     self.get_venue_thread.error_occurred.connect(self._on_venue_state_error)
    #     self.get_venue_thread.start()

    def _fetch_venue_state(self):
        """
        根据当前选择的预约日期和时间段获取场地状态。
        此方法由日期和时间段选择器触发。
        """
        logger.info("正在获取当前选择日期的场地信息...")
        self._clear_fields_display()
        self.submit_button.setEnabled(False)
        self.selected_fields = []
        self._clear_all_button_styles()

        dateadd = self._calculate_date_add()
        time_period = self.time_period_combo.currentData()

        if self.get_venue_thread and self.get_venue_thread.isRunning():
            self.get_venue_thread.quit()
            self.get_venue_thread.wait()

        self.get_venue_thread = GetVenueStateNewThread(dateadd, time_period)
        self.get_venue_thread.data_fetched.connect(self._on_venue_state_fetched)
        self.get_venue_thread.error_occurred.connect(self._on_venue_state_error)
        self.get_venue_thread.start()

    def _on_venue_state_fetched(self, response_data: dict, fetched_dateadd: int):
        """
        处理场地信息获取成功后的数据。
        新增 fetched_dateadd 参数，用于记录当前渲染数据对应的日期偏移量。
        """
        logger.info("场地信息获取成功。")
        self._current_rendered_dateadd = fetched_dateadd
        data = response_data.get("data")
        if not data:
            self._display_message("无可用场地信息。", "info")
            return

        self._render_fields(data)
        self._update_submit_button_state()

    def _on_venue_state_error(self, error_message: str):
        """
        处理场地信息获取失败。
        """
        logger.error(f"获取场地信息失败: {error_message}")
        self._display_message(f"获取场地信息失败: {error_message}", "error")
        self._update_submit_button_state()

    def _clear_fields_display(self):
        """
        清空场地显示区域。
        """
        while self.fields_grid_layout.count():
            item = self.fields_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.field_buttons.clear()

    def _clear_all_button_styles(self):
        """
        清除所有按钮的选中高亮样式，恢复到默认状态（绿色）。
        """
        for (field_name, time_slot), button in self.field_buttons.items():
            item_data = button.property("field_data")
            # is_available = button.property("is_available") # 不再根据可用性设置初始颜色

            if item_data:
                # 统一设置为绿色背景，深绿色边框，深色文字
                button.setStyleSheet(
                    "background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px; color: #333; font-size: 10pt;")
            else:
                # 无数据：默认灰色背景，浅灰色边框，深灰色文字
                button.setStyleSheet(
                    "background-color: #f0f0f0; border: 1px solid #ccc; color: #999; border-radius: 5px; font-size: 10pt;")
            button.setText(time_slot)  # 恢复原始文本

    def _render_fields(self, field_data_list: list):
        """
        渲染场地信息到界面。
        所有按钮都可点击，文本显示时间段。
        """
        self._clear_fields_display()

        if not field_data_list:
            no_data_label = QLabel("当前日期/时间段无可用场地。")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("font-size: 14pt; color: #777; padding: 50px;")
            self.fields_grid_layout.addWidget(no_data_label, 0, 0, 1, -1)  # 跨所有列
            # 确保即使没有数据，布局也能撑开
            self.fields_grid_layout.setRowStretch(0, 1)
            self.fields_grid_layout.setColumnStretch(0, 1)
            return

        field_names = sorted(list(set(item["FieldName"] for item in field_data_list)))
        time_slots = sorted(list(set(item["BeginTime"] + "-" + item["EndTime"] for item in field_data_list)))

        field_time_map = defaultdict(lambda: defaultdict(dict))
        for item in field_data_list:
            time_key = item["BeginTime"] + "-" + item["EndTime"]
            field_time_map[item["FieldName"]][time_key] = item

        # 添加时间段标题行
        self.fields_grid_layout.addWidget(QLabel(""), 0, 0)  # 左上角空位
        for col_idx, time_slot in enumerate(time_slots):
            time_label = QLabel(time_slot)
            time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            time_label.setStyleSheet("font-weight: bold; background-color: #e0e0e0; padding: 5px; border-radius: 5px;")
            # 移除 setMinimumWidth，让布局自动调整
            # time_label.setMinimumWidth(80)
            self.fields_grid_layout.addWidget(time_label, 0, col_idx + 1)

        # 添加场地名称列和场地按钮
        for row_idx, field_name in enumerate(field_names):
            field_label = QLabel(field_name)
            field_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            field_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e0e0e0; border-radius: 5px;")
            field_label.setWordWrap(True)  # 允许文本换行
            # 移除 setMinimumWidth，并调整 SizePolicy
            # field_label.setMinimumWidth(100)
            field_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred) # 允许水平扩展
            self.fields_grid_layout.addWidget(field_label, row_idx + 1, 0)

            for col_idx, time_slot in enumerate(time_slots):
                item_data = field_time_map[field_name].get(time_slot)

                button = QPushButton()
                # 移除 setFixedSize，让按钮根据内容和布局策略自动调整大小
                # 移除 setMinimumHeight，让布局自动调整
                # button.setMinimumHeight(40)
                # 允许按钮在水平和垂直方向上扩展
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                button.setText(time_slot)
                # 移除 setWordWrap(True)，因为 QPushButton 不支持，通过 QSizePolicy 和布局来处理
                # button.setWordWrap(True)

                if item_data:
                    is_available = item_data.get("TimeStatus") == "0" and item_data.get("FieldState") == "1"

                    button.setProperty("field_data", item_data)
                    button.setProperty("is_available", is_available)  # 仍然保留此属性用于逻辑判断

                    # 统一设置为绿色背景，深绿色边框，深色文字 (未选中状态)
                    button.setStyleSheet(
                        "background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px; color: #333; font-size: 10pt;")

                else:
                    # 无数据：默认灰色背景，浅灰色边框，深灰色文字
                    button.setStyleSheet(
                        "background-color: #f0f0f0; border: 1px solid #ccc; color: #999; border-radius: 5px; font-size: 10pt;")
                    button.setProperty("field_data", None)
                    button.setProperty("is_available", False)

                button.clicked.connect(lambda checked, btn=button: self._on_field_button_toggle_selection(btn))
                self.fields_grid_layout.addWidget(button, row_idx + 1, col_idx + 1)
                self.field_buttons[(field_name, time_slot)] = button

        # 确保网格布局能够撑开，给行和列添加伸缩因子
        # 第0列（球场名称）给予更高的伸缩因子，让其有更多空间
        self.fields_grid_layout.setColumnStretch(0, 2)
        for i in range(1, self.fields_grid_layout.columnCount()):
            self.fields_grid_layout.setColumnStretch(i, 3)  # 其他列（时间段）均匀分配

        for i in range(self.fields_grid_layout.rowCount()):
            self.fields_grid_layout.setRowStretch(i, 1)  # 行均匀分配

        self._restore_selected_button_styles()

    def _on_field_button_toggle_selection(self, button: QPushButton):
        """
        处理场地按钮点击事件，实现多选和取消选中。
        """
        field_data = button.property("field_data")
        is_available = button.property("is_available")  # 仍然使用此属性进行逻辑判断

        if field_data is None:
            self._display_message(f"该时段 ({button.text()}) 无此场地数据。", "info")
            return

        # 检查是否已选中
        if field_data in self.selected_fields:
            # 如果已选中，则取消选中
            self.selected_fields.remove(field_data)
            # 恢复到默认状态的绿色样式
            button.setStyleSheet(
                "background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px; color: #333; font-size: 10pt;")
            button.setText(field_data.get("BeginTime") + "-" + field_data.get("EndTime"))
            logger.info(
                f"取消选中场地: {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')}")
        else:
            # 如果未选中，则选中
            self.selected_fields.append(field_data)
            # 设置选中状态的蓝色样式，字体颜色设置为黑色
            button.setStyleSheet(
                "background-color: #cceeff; border: 2px solid #007bff; border-radius: 5px; color: #000; font-size: 10pt;")  # 蓝色背景，黑色文字
            # 确保选中后的文本显示在单行，避免高度问题
            button.setText(field_data.get("BeginTime") + "-" + field_data.get("EndTime"))
            logger.info(
                f"已选中场地: {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')}")

            # 提示信息保持不变
            # if self._current_rendered_dateadd == -1:
            #     if not is_available:
            #         self._display_message(f"此为参考数据：场地 {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')} 在昨天是已满或不可用的。", "info")
            #     else:
            #         self._display_message(f"此为参考数据：场地 {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')} 在昨天是可预订的。", "info")
            # elif not is_available:
            #     self._display_message(f"场地 {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')} 已被预订或不可用。", "info")

        self._update_submit_button_state()

    def _restore_selected_button_styles(self):
        """
        根据 self.selected_fields 恢复已选中按钮的样式。
        在重新渲染场地时调用。
        """
        for selected_field_data in self.selected_fields:
            field_name = selected_field_data.get("FieldName")
            time_slot = selected_field_data.get("BeginTime") + "-" + selected_field_data.get("EndTime")
            button_key = (field_name, time_slot)

            if button_key in self.field_buttons:
                button = self.field_buttons[button_key]
                # 恢复选中状态的蓝色样式，字体颜色设置为黑色
                button.setStyleSheet(
                    "background-color: #cceeff; border: 2px solid #007bff; border-radius: 5px; color: #000; font-size: 10pt;")
                button.setText(time_slot)  # 确保恢复时也只显示时间段

    def _update_submit_button_state(self):
        """
        更新提交按钮的启用状态。
        只要有任何场地被选中，就启用提交按钮。
        """
        self.submit_button.setEnabled(bool(self.selected_fields))

    def _start_scheduling_task(self):
        """
        启动定时预约任务。
        """
        if not self.selected_fields:
            self._display_message("请至少选择一个场地进行预约。", "warning")
            return

        script_date_qdate = self.script_date_edit.date()
        script_time_qtime = self.script_time_edit.time()
        email_address = self.email_input.text().strip()

        script_date = datetime.date(script_date_qdate.year(), script_date_qdate.month(), script_date_qdate.day())
        script_time = datetime.time(script_time_qtime.hour(), script_time_qtime.minute(), script_time_qtime.second())

        scheduler_manager.add_booking_task(self.selected_fields, script_date, script_time, email_address=email_address)

        self._display_message(
            f"定时预约任务已添加！\n将在 {script_date.strftime('%Y-%m-%d')} {script_time.strftime('%H:%M')} 尝试预约所选场地。\n提醒邮箱: {email_address if email_address else '未设置'}",
            "info")
        # 任务启动后，可以清空已选，或者禁用选择器，具体看需求
        # self.selected_fields = []
        # self._clear_all_button_styles()
        # self._update_submit_button_state()

    def _display_message(self, message: str, msg_type: str = "info"):
        """
        显示消息框。
        """
        if msg_type == "info":
            QMessageBox.information(self, "提示", message)
        elif msg_type == "warning":
            QMessageBox.warning(self, "警告", message)
        elif msg_type == "error":
            QMessageBox.critical(self, "错误", message)
        else:
            QMessageBox.information(self, "消息", message)
