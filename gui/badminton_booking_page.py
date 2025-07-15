import json
import datetime
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QTimeEdit, QComboBox, QGridLayout, QScrollArea,
    QMessageBox, QSizePolicy, QLineEdit  # 导入 QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QDate, QTime
from PySide6.QtGui import QColor, QPalette

from loguru import logger

# 导入API函数
from API.Badminiton.API import GetVenueStateNew, OrderField
# 导入定时任务管理器
from core.schedule_task import scheduler_manager


# --- API 调用线程 ---
class GetVenueStateNewThread(QThread):
    """
    在独立线程中调用 GetVenueStateNew API。
    """
    data_fetched = Signal(dict, int)  # 增加一个参数，用于传递 dateadd
    error_occurred = Signal(str)

    def __init__(self, dateadd: int, time_period: int):
        super().__init__()
        self.dateadd = dateadd
        self.time_period = time_period

    def run(self):
        try:
            logger.info(f"正在获取场地信息：dateadd={self.dateadd}, TimePeriod={self.time_period}")
            response = GetVenueStateNew(self.dateadd, self.time_period)
            if response and response.get("errorcode") == 0 and response.get("resultdata"):
                # resultdata 是一个 JSON 字符串，需要再次解析
                result_data_str = response["resultdata"]
                try:
                    parsed_result_data = json.loads(result_data_str)
                    self.data_fetched.emit({"status": "success", "data": parsed_result_data}, self.dateadd)
                except json.JSONDecodeError as e:
                    self.error_occurred.emit(f"解析场地信息JSON失败: {e}")
            elif response and response.get("message"):
                self.error_occurred.emit(f"获取场地信息失败: {response['message']}")
            else:
                self.error_occurred.emit("获取场地信息失败，未知错误或响应为空。")
        except Exception as e:
            logger.error(f"调用 GetVenueStateNew API 发生错误: {e}")
            self.error_occurred.emit(f"调用场地信息API失败: {e}")


# --- OrderFieldThread 类被移除，由 core.schedule_task 接管 ---
# class OrderFieldThread(QThread):
#     ...

# --- 羽毛球预约界面类 ---
class BadmintonBookingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        self.selected_fields = []  # 存储用户选中的所有场地数据
        self._current_rendered_dateadd = None  # 存储当前渲染数据对应的dateadd
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

        # 时间段选择 (上午/下午/晚上) - 无需禁用
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
        self.top_controls_layout.addWidget(self.email_label)
        self.top_controls_layout.addWidget(self.email_input)

        self.top_controls_layout.addStretch(1)  # 填充剩余空间
        self.layout.addLayout(self.top_controls_layout)

        # 第二行往下：场地信息显示区域
        self.fields_scroll_area = QScrollArea()
        self.fields_scroll_area.setWidgetResizable(True)
        self.fields_container = QWidget()
        self.fields_grid_layout = QGridLayout(self.fields_container)
        self.fields_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_grid_layout.setSpacing(5)
        self.fields_scroll_area.setWidget(self.fields_container)
        self.layout.addWidget(self.fields_scroll_area)

        # 提交按钮
        self.submit_button = QPushButton("点击预约")  # 文本改为“点击预约”
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
        self.submit_button.clicked.connect(self._start_scheduling_task)  # 连接到新的调度任务方法
        self.submit_button.setEnabled(False)  # 初始禁用，选择场地后启用
        self.layout.addWidget(self.submit_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.get_venue_thread = None
        # self.scheduling_thread = None # 不再直接管理调度线程，由 core.schedule_task 接管

        # 初始加载场地信息 (获取昨天的信息作为参考)
        self._fetch_initial_reference_venue_state()
        self._update_submit_button_state()  # 确保初始状态正确

    def _on_date_changed(self, date: QDate):
        """预约日期选择框改变时触发，重新获取场地信息"""
        logger.info(f"预约日期选择改变为: {date.toString('yyyy-MM-dd')}")
        self._fetch_venue_state()  # 调用常规的获取场地信息方法

    def _on_time_period_changed(self, index: int):
        """时间段选择框改变时触发，重新获取场地信息"""
        time_period = self.time_period_combo.itemData(index)
        logger.info(f"时间段选择改变为: {self.time_period_combo.currentText()} (值: {time_period})")
        self._fetch_venue_state()  # 调用常规的获取场地信息方法

    def _calculate_date_add(self) -> int:
        """计算当前日期与选中预约日期之间的天数偏移量"""
        current_date = QDate.currentDate()
        selected_date = self.date_edit.date()
        return current_date.daysTo(selected_date)

    def _fetch_initial_reference_venue_state(self):
        """
        在初始化时获取昨天的场地信息作为参考。
        """
        logger.info("初始加载：正在获取昨天的场地信息作为参考...")
        self._clear_fields_display()
        self.submit_button.setEnabled(False)  # 暂时禁用提交按钮
        self.selected_fields = []  # 清空已选场地
        self._clear_all_button_styles()  # 清除所有按钮的选中样式

        # 使用 dateadd = -1 表示昨天，TimePeriod 默认上午 (0)
        initial_dateadd = -1
        initial_time_period = 0

        if self.get_venue_thread and self.get_venue_thread.isRunning():
            self.get_venue_thread.quit()
            self.get_venue_thread.wait()

        # 将 dateadd 传递给 data_fetched 信号
        self.get_venue_thread = GetVenueStateNewThread(initial_dateadd, initial_time_period)
        self.get_venue_thread.data_fetched.connect(self._on_venue_state_fetched)
        self.get_venue_thread.error_occurred.connect(self._on_venue_state_error)
        self.get_venue_thread.start()

    def _fetch_venue_state(self):
        """
        根据当前选择的预约日期和时间段获取场地状态。
        此方法由日期和时间段选择器触发。
        """
        logger.info("正在获取当前选择日期的场地信息...")
        self._clear_fields_display()
        self.submit_button.setEnabled(False)  # 重新获取数据时禁用提交按钮
        self.selected_fields = []  # 清空已选场地
        self._clear_all_button_styles()  # 清除所有按钮的选中样式

        dateadd = self._calculate_date_add()
        time_period = self.time_period_combo.currentData()

        if self.get_venue_thread and self.get_venue_thread.isRunning():
            self.get_venue_thread.quit()
            self.get_venue_thread.wait()

        # 将 dateadd 传递给 data_fetched 信号
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
        self._current_rendered_dateadd = fetched_dateadd  # 存储当前渲染数据的dateadd
        data = response_data.get("data")
        if not data:
            self._display_message("无可用场地信息。", "info")
            return

        # 检查是否有可预订的场地（仅用于日志，不影响渲染和点击行为）
        has_available_fields = any(
            item.get("TimeStatus") == "0" and item.get("FieldState") == "1"
            for item in data
        )
        if not has_available_fields and self._current_rendered_dateadd >= 0:  # 只有对于今天或未来的日期才警告
            logger.warning("当前获取的场地信息中，没有找到可预订的场次。")
            # 可以在这里选择性地弹窗提示用户，或者只在日志中记录

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
        # 移除 QGridLayout 中的所有控件
        while self.fields_grid_layout.count():
            item = self.fields_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.field_buttons.clear()  # 清空按钮引用字典

    def _clear_all_button_styles(self):
        """
        清除所有按钮的选中高亮样式，恢复到默认状态。
        """
        # 遍历 field_buttons 字典中的所有按钮，恢复其原始样式
        for (field_name, time_slot), button in self.field_buttons.items():
            item_data = button.property("field_data")
            is_available = button.property("is_available") if item_data else False
            button.setStyleSheet("background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px;")
            if item_data:
                button.setStyleSheet("background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px;")
            else:
                button.setStyleSheet(
                    "background-color: #f0f0f0; border: 1px solid #ccc; color: #999; border-radius: 5px;")
            button.setText(time_slot)  # 恢复文本为时间段

    def _render_fields(self, field_data_list: list):
        """
        渲染场地信息到界面。
        所有按钮都可点击，文本显示时间段。
        """
        self._clear_fields_display()  # 先清空，包括 self.field_buttons

        if not field_data_list:
            self.fields_grid_layout.addWidget(QLabel("当前日期/时间段无可用场地。"), 0, 0)
            return

        # 1. 提取所有唯一的场地名称和时间段
        field_names = sorted(list(set(item["FieldName"] for item in field_data_list)))
        time_slots = sorted(list(set(item["BeginTime"] + "-" + item["EndTime"] for item in field_data_list)))

        # 2. 创建一个字典，方便按场地名称和时间段查找数据
        field_time_map = defaultdict(lambda: defaultdict(dict))
        for item in field_data_list:
            time_key = item["BeginTime"] + "-" + item["EndTime"]
            field_time_map[item["FieldName"]][time_key] = item

        # 3. 绘制表头 (时间段)
        self.fields_grid_layout.addWidget(QLabel(""), 0, 0)  # 左上角空白
        for col_idx, time_slot in enumerate(time_slots):
            time_label = QLabel(time_slot)
            time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            time_label.setStyleSheet("font-weight: bold; background-color: #e0e0e0; padding: 5px;")
            self.fields_grid_layout.addWidget(time_label, 0, col_idx + 1)

        # 4. 绘制场地行和时间格
        for row_idx, field_name in enumerate(field_names):
            # 场地名称标签
            field_label = QLabel(field_name)
            field_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            field_label.setStyleSheet("font-weight: bold; padding: 5px;")
            self.fields_grid_layout.addWidget(field_label, row_idx + 1, 0)

            for col_idx, time_slot in enumerate(time_slots):
                item_data = field_time_map[field_name].get(time_slot)

                button = QPushButton()
                button.setFixedSize(100, 40)  # 固定按钮大小
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                button.setText(time_slot)  # 按钮文本始终显示时间段

                if item_data:
                    is_available = item_data.get("TimeStatus") == "0" and item_data.get("FieldState") == "1"

                    button.setProperty("field_data", item_data)  # 存储数据
                    button.setProperty("is_available", is_available)  # 存储可用性状态

                    # 默认样式：可预订的绿色，已满的红色
                    button.setStyleSheet("background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px;")
                    # if is_available:
                    #     button.setStyleSheet(
                    #         "background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px;")
                    # else:
                    #     button.setStyleSheet(
                    #         "background-color: #ffe6e6; border: 1px solid #cc6666; color: #666; border-radius: 5px;")

                else:
                    # 如果某个时间段该场地没有数据，表示不可用或不存在
                    button.setStyleSheet(
                        "background-color: #f0f0f0; border: 1px solid #ccc; color: #999; border-radius: 5px;")
                    button.setProperty("field_data", None)  # 无数据
                    button.setProperty("is_available", False)  # 不可用

                # 所有按钮都连接到统一的点击处理函数
                button.clicked.connect(lambda checked, btn=button: self._on_field_button_toggle_selection(btn))
                self.fields_grid_layout.addWidget(button, row_idx + 1, col_idx + 1)
                self.field_buttons[(field_name, time_slot)] = button  # 存储按钮引用

        # 渲染完成后，根据 selected_fields 恢复选中状态
        self._restore_selected_button_styles()

    def _on_field_button_toggle_selection(self, button: QPushButton):
        """
        统一处理场地按钮点击事件，实现多选和取消选中。
        """
        field_data = button.property("field_data")
        is_available = button.property("is_available")  # 实际可用性，用于提示

        if field_data is None:  # 如果是“无数据”的按钮
            self._display_message(f"该时段 ({button.text()}) 无此场地数据。", "info")
            return

        # 检查是否已选中
        if field_data in self.selected_fields:
            # 取消选中
            self.selected_fields.remove(field_data)
            # 恢复按钮原始样式和文本
            # if is_available:
            #     button.setStyleSheet("background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px;")
            # else:
            #     button.setStyleSheet(
            #         "background-color: #ffe6e6; border: 1px solid #cc6666; color: #666; border-radius: 5px;")
            button.setStyleSheet("background-color: #e6ffe6; border: 1px solid #66cc66; border-radius: 5px;")
            button.setText(field_data.get("BeginTime") + "-" + field_data.get("EndTime"))
            logger.info(
                f"取消选中场地: {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')}")
        else:
            # 选中
            self.selected_fields.append(field_data)
            # 高亮选中按钮
            button.setStyleSheet("background-color: #cceeff; border: 2px solid #007bff; border-radius: 5px;")
            button.setText(f"{field_data.get('BeginTime')}-{field_data.get('EndTime')}\n(已选中)")
            logger.info(
                f"已选中场地: {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')}")

            # 根据当前渲染的日期类型和实际可用性给出提示
            # if self._current_rendered_dateadd == -1:  # 如果是昨天的参考数据
            #     if not is_available:
            #         self._display_message(
            #             f"此为参考数据：场地 {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')} 在昨天是已满或不可用的。",
            #             "info")
            #     else:
            #         self._display_message(
            #             f"此为参考数据：场地 {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')} 在昨天是可预订的。",
            #             "info")
            # elif not is_available:  # 如果是今天或未来的数据且不可用
            #     self._display_message(
            #         f"场地 {field_data.get('FieldName')} {field_data.get('BeginTime')}-{field_data.get('EndTime')} 已被预订或不可用。",
            #         "info")

        self._update_submit_button_state()  # 更新提交按钮状态

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
                button.setStyleSheet("background-color: #cceeff; border: 2px solid #007bff; border-radius: 5px;")
                button.setText(f"{time_slot}\n(已选中)")

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

        # 获取脚本执行的完整日期时间
        script_date_qdate = self.script_date_edit.date()
        script_time_qtime = self.script_time_edit.time()
        email_address = self.email_input.text().strip()  # 获取邮箱地址

        # 转换为 datetime.date 和 datetime.time 对象
        script_date = datetime.date(script_date_qdate.year(), script_date_qdate.month(), script_date_qdate.day())
        script_time = datetime.time(script_time_qtime.hour(), script_time_qtime.minute(), script_time_qtime.second())

        # 调用定时任务管理器添加任务，并传递邮箱地址
        scheduler_manager.add_booking_task(self.selected_fields, script_date, script_time, email_address=email_address)

        # 提示用户任务已启动
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

