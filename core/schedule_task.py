import json
import datetime
import time
from loguru import logger
from PySide6.QtCore import QThread, Signal  # 导入 QThread 和 Signal 用于异步操作

# 导入API函数
from API.Badminiton.API import OrderField
# 导入邮件发送脚本
from tools.email_sender import send_email
# 导入 Firebase 管理器
from core.firebase_manager import firebase_manager  # 假设路径正确

# 定义 Firestore 集合名称
TASKS_COLLECTION = "scheduled_booking_tasks"


# 辅助线程用于异步 Firestore 操作
class FirestoreAsyncTaskThread(QThread):
    """
    一个简单的 QThread，用于在后台运行异步 Firestore 操作。
    """
    finished = Signal()
    error = Signal(str)
    # 如果需要从异步函数返回结果，可以添加一个信号
    result_ready = Signal(object)

    def __init__(self, coroutine_func, *args, **kwargs):
        super().__init__()
        self.coroutine_func = coroutine_func
        self.args = args
        self.kwargs = kwargs
        self._result = None  # 用于存储异步操作的结果
        self._error_message = None  # 用于存储错误信息

    def run(self):
        try:
            import asyncio
            # 为当前线程创建一个新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 运行异步协程并等待其完成
            self._result = loop.run_until_complete(self.coroutine_func(*self.args, **self.kwargs))
            loop.close()  # 关闭事件循环

            self.result_ready.emit(self._result)  # 发送结果
            self.finished.emit()
        except Exception as e:
            self._error_message = str(e)
            logger.error(f"FirestoreAsyncTaskThread: 运行异步任务时出错: {self._error_message}")
            self.error.emit(self._error_message)

    @property
    def result(self):
        return self._result

    @property
    def error_message(self):
        return self._error_message


class SchedulerManager:
    """
    定时任务管理器，使用 BackgroundScheduler 在后台线程中调度任务。
    采用单例模式，确保整个应用只有一个调度器实例。
    """
    _instance = None
    _scheduler = None

    def __new__(cls, *args, **kwargs):
        """
        实现单例模式。
        """
        if cls._instance is None:
            cls._instance = super(SchedulerManager, cls).__new__(cls)
            cls._instance._initialize_scheduler()
        return cls._instance

    def _initialize_scheduler(self):
        """初始化 BackgroundScheduler。"""
        if self.__class__._scheduler is None:
            from apscheduler.schedulers.background import BackgroundScheduler  # 延迟导入
            self.__class__._scheduler = BackgroundScheduler()
            logger.info("SchedulerManager: BackgroundScheduler 已初始化。")

    def start(self):
        """
        启动调度器。
        """
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("SchedulerManager: BackgroundScheduler 已启动。")
        else:
            logger.info("SchedulerManager: BackgroundScheduler 已经运行中。")

    def shutdown(self):
        """
        关闭调度器。
        """
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("SchedulerManager: BackgroundScheduler 已关闭。")

    def add_booking_task(self, selected_fields_data: list, booking_date: datetime.date, script_time: datetime.time,
                         email_address: str = ""):
        """
        添加一个定时预约任务。
        如果任务时间在过去或现在，则尝试立即执行。
        同时将任务持久化到 Firestore。
        """
        run_datetime = datetime.datetime.combine(booking_date, script_time)
        job_id = f"booking_job_{run_datetime.timestamp()}_{hash(json.dumps(selected_fields_data, sort_keys=True))}"

        task_data = {
            "id": job_id,
            "name": f"场馆预约任务 ({booking_date.strftime('%Y-%m-%d')} {script_time.strftime('%H:%M')})",
            "run_datetime": run_datetime.isoformat(),  # 以 ISO 格式字符串存储，便于持久化
            "selected_fields_data": json.dumps(selected_fields_data, ensure_ascii=False),  # 作为 JSON 字符串存储
            "email_address": email_address,
            "status": "pending"  # 初始状态
        }

        # 首先将任务持久化到 Firestore (异步执行)
        if firebase_manager.is_ready():
            firestore_add_thread = FirestoreAsyncTaskThread(
                firebase_manager.add_document, TASKS_COLLECTION, job_id, task_data
            )
            firestore_add_thread.start()  # 启动线程，不等待结果
            logger.info(f"SchedulerManager: 已请求将任务 '{job_id}' 持久化到 Firestore。")
        else:
            logger.warning("Firebase 未准备就绪。任务将不会持久化到 Firestore。")

        # 如果任务时间在过去或现在，则立即执行
        if run_datetime <= datetime.datetime.now():
            logger.warning(
                f"SchedulerManager: 任务执行时间 {run_datetime.strftime('%Y-%m-%d %H:%M:%S')} 已过期或为当前时间。尝试立即执行。")
            # 在单独的 QThread 中执行，避免阻塞主线程
            execute_thread = QThread()
            # 使用 lambda 包装，将参数传递给 _execute_booking_job
            execute_thread.run = lambda: self._execute_booking_job(selected_fields_data, booking_date, email_address,
                                                                   job_id=job_id)
            execute_thread.start()
            return

        # 将任务添加到 APScheduler 以供将来执行
        self._scheduler.add_job(
            self._execute_booking_job,
            trigger='date',  # 使用 'date' 触发器类型
            run_date=run_datetime,  # 直接传递 run_date
            args=[selected_fields_data, booking_date, email_address, job_id],  # 将 job_id 传递给执行函数
            id=job_id,
            name=task_data["name"],
            replace_existing=True
        )
        logger.info(
            f"SchedulerManager: 已添加定时预约任务，将在 {run_datetime.strftime('%Y-%m-%d %H:%M:%S')} 执行。任务ID: {job_id}")
        logger.debug(f"SchedulerManager: 预约详情: {json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}")

    def _execute_booking_job(self, selected_fields_data: list, booking_date: datetime.date, email_address: str = "",
                             job_id: str = None):
        """
        实际执行预约的函数，由APScheduler或直接调用。
        此函数将在后台线程中运行。
        执行后更新 Firestore 中的任务状态。
        """
        logger.info(
            f"SchedulerManager: >>> _execute_booking_job 函数开始执行，任务ID: {job_id}，当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} <<<")

        current_date = datetime.date.today()
        dateadd = (booking_date - current_date).days
        venue_no = "02"  # 羽毛球场馆编号，假设固定

        start_time = time.time()
        end_time = start_time + 10  # 10秒的重试窗口
        attempt = 0
        booking_successful = False
        final_email_subject = ""
        final_email_content = ""

        # 在10秒内循环重试，直到成功或明确失败
        while time.time() < end_time and not booking_successful:
            attempt += 1
            logger.info(
                f"SchedulerManager: 尝试 {attempt} 执行预约任务，目标日期: {booking_date.strftime('%Y-%m-%d')}。")

            try:
                response = OrderField(selected_fields_data, dateadd, venue_no)
                message = response.get("message", "未知结果")
                response_type = response.get("type")

                if response_type == 1 and response.get("errorcode") == 0:
                    logger.success(f"SchedulerManager: 预约成功！订单ID: {response.get('resultdata')}")
                    final_email_subject = "场馆预约成功提醒"
                    final_email_content = f"您的场馆已成功预约！\n\n预约详情:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}\n\n订单号: {response.get('resultdata')}"
                    booking_successful = True
                elif response_type == 3 and response.get("errorcode") == 0:
                    logger.warning(f"SchedulerManager: 预约失败 (冲突/太慢): {message}。正在重试...")
                    final_email_subject = "场馆预约失败提醒 (尝试中)"
                    final_email_content = f"您的场馆预约失败：{message}\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}\n\n将继续尝试..."
                else:
                    logger.error(
                        f"SchedulerManager: 预约失败: {message} (错误码: {response.get('errorcode')})。停止重试。")
                    final_email_subject = "场馆预约失败提醒"
                    final_email_content = f"您的场馆预约失败：{message} (错误码: {response.get('errorcode')})\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}"
                    break

            except Exception as e:
                logger.error(f"SchedulerManager: 预约尝试 {attempt} 期间发生错误: {e}。正在重试...")
                final_email_subject = "场馆预约任务执行错误 (尝试中)"
                final_email_content = f"执行场馆预约任务时发生错误：{e}\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}\n\n将继续尝试..."

            if not booking_successful and time.time() < end_time:
                time.sleep(1)

        if email_address:
            if booking_successful:
                logger.info(f"SchedulerManager: 预约成功。正在向 {email_address} 发送最终成功邮件。")
                send_email(email_address, final_email_subject, final_email_content)
            else:
                logger.warning(
                    f"SchedulerManager: 所有尝试后预约失败或明确错误。正在向 {email_address} 发送最终失败邮件。")
                if not final_email_subject or "尝试中" in final_email_subject:
                    final_email_subject = "场馆预约失败提醒"
                    final_email_content = f"您的场馆预约在规定时间内未能成功。\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}"
                send_email(email_address, final_email_subject, final_email_content)
        elif not email_address and not booking_successful:
            logger.warning("SchedulerManager: 未提供邮箱地址，且所有尝试后预约失败。")

        # 任务执行完毕后，从 Firestore 中删除该任务
        if job_id and firebase_manager.is_ready():
            firestore_delete_thread = FirestoreAsyncTaskThread(
                firebase_manager.delete_document, TASKS_COLLECTION, job_id
            )
            firestore_delete_thread.start()
            logger.info(f"SchedulerManager: 已请求从 Firestore 删除已执行任务 '{job_id}'。")

    def get_pending_jobs_info(self) -> list[dict]:
        """
        从 Firestore 获取当前所有待执行的定时任务信息。
        """
        if not firebase_manager.is_ready():
            logger.warning("Firebase 未准备就绪。无法从 Firestore 获取待执行任务。")
            return []

        # 在单独的 QThread 中运行异步 Firestore get_documents 调用并等待结果
        get_tasks_thread = FirestoreAsyncTaskThread(firebase_manager.get_documents, TASKS_COLLECTION)
        get_tasks_thread.start()
        get_tasks_thread.wait()  # 阻塞当前线程直到 Firestore 操作完成

        if get_tasks_thread.error_message:
            logger.error(f"SchedulerManager: 从 Firestore 获取待执行任务失败: {get_tasks_thread.error_message}")
            return []

        persisted_tasks = get_tasks_thread.result
        if not isinstance(persisted_tasks, list):
            logger.error("SchedulerManager: 从 Firestore 获取的任务数据格式不正确。")
            return []

        # 过滤出仍在待执行状态（即未来时间）的任务
        pending_jobs_info = []
        now = datetime.datetime.now()
        for task_data in persisted_tasks:
            try:
                job_id = task_data.get("id")
                run_datetime_str = task_data.get("run_datetime")

                if not job_id or not run_datetime_str:
                    logger.warning(f"SchedulerManager: 跳过格式不正确的持久化任务 (缺少ID或执行时间): {task_data}")
                    continue

                run_datetime = datetime.datetime.fromisoformat(run_datetime_str)

                if run_datetime > now:  # 仅添加真正待执行的任务
                    pending_jobs_info.append({
                        "id": job_id,
                        "name": task_data.get("name", f"Unnamed Task ({job_id})"),
                        "next_run_time": run_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                        "status": "待执行"
                    })
                else:
                    # 如果任务时间已过期，但仍在 Firestore 中，则记录警告并考虑删除
                    logger.warning(f"SchedulerManager: Firestore 中存在已过期任务 '{job_id}'。它应该在执行时被删除。")
                    # 可以在这里添加一个清理机制，例如再次尝试删除
                    if firebase_manager.is_ready():
                        delete_expired_thread = FirestoreAsyncTaskThread(
                            firebase_manager.delete_document, TASKS_COLLECTION, job_id
                        )
                        delete_expired_thread.start()
                        logger.info(f"SchedulerManager: 已请求从 Firestore 删除过期任务 '{job_id}'。")

            except (ValueError, KeyError) as e:
                logger.error(f"SchedulerManager: 解析持久化任务数据时出错，任务ID: {task_data.get('id')}: {e}")
                # 如果解析失败，考虑删除该格式错误的任务
                if task_data.get('id') and firebase_manager.is_ready():
                    delete_malformed_thread = FirestoreAsyncTaskThread(
                        firebase_manager.delete_document, TASKS_COLLECTION, task_data['id']
                    )
                    delete_malformed_thread.start()
                    logger.warning(f"SchedulerManager: 已请求从 Firestore 删除格式错误的任务 '{task_data['id']}'。")
                continue

        logger.info(f"SchedulerManager: 从 Firestore 获取到 {len(pending_jobs_info)} 个待执行任务。")
        return pending_jobs_info

    def remove_job(self, job_id: str) -> bool:
        """
        根据任务ID从调度器和 Firestore 中删除任务。
        :param job_id: 要删除的任务的ID。
        :return: 如果任务成功删除则返回True，否则返回False。
        """
        aps_removed = False
        try:
            self._scheduler.remove_job(job_id)
            aps_removed = True
            logger.info(f"SchedulerManager: 任务 '{job_id}' 已成功从 APScheduler 删除。")
        except Exception as e:
            logger.error(f"SchedulerManager: 从 APScheduler 删除任务 '{job_id}' 失败: {e}")

        firestore_removed = False
        if firebase_manager.is_ready():
            try:
                # 在单独的 QThread 中运行异步 Firestore delete_document 调用
                firestore_delete_thread = FirestoreAsyncTaskThread(
                    firebase_manager.delete_document, TASKS_COLLECTION, job_id
                )
                firestore_delete_thread.start()
                firestore_removed = True  # 假设成功（火-忘）
                logger.info(f"SchedulerManager: 已请求从 Firestore 删除任务 '{job_id}'。")
            except Exception as e:
                logger.error(f"SchedulerManager: 请求从 Firestore 删除任务 '{job_id}' 失败: {e}")
        else:
            logger.warning("Firebase 未准备就绪。无法从 Firestore 删除任务。")

        return aps_removed and firestore_removed  # 如果 APScheduler 成功删除且 Firestore 操作被请求，则返回 True

    def load_persisted_tasks(self):
        """
        从 Firestore 加载任务并重新添加到 APScheduler。
        立即执行计划时间已过的任务。
        此方法应在 Firebase 准备就绪后调用。
        """
        if not firebase_manager.is_ready():
            logger.warning("SchedulerManager: Firebase 未准备就绪。无法加载持久化任务。")
            return

        logger.info("SchedulerManager: 正在尝试从 Firestore 加载持久化任务。")

        # 在单独的 QThread 中运行异步 get_documents 调用
        load_thread = FirestoreAsyncTaskThread(firebase_manager.get_documents, TASKS_COLLECTION)

        def on_load_finished():
            if load_thread.error_message:  # 检查是否有错误
                logger.error(f"SchedulerManager: 从 Firestore 加载持久化任务失败: {load_thread.error_message}")
                return

            persisted_tasks = load_thread.result
            if not isinstance(persisted_tasks, list):
                logger.error("SchedulerManager: 从 Firestore 获取的任务数据格式不正确。")
                return

            now = datetime.datetime.now()
            for task_data in persisted_tasks:
                try:
                    job_id = task_data.get("id")
                    run_datetime_str = task_data.get("run_datetime")
                    selected_fields_data_str = task_data.get("selected_fields_data")
                    email_address = task_data.get("email_address", "")
                    name = task_data.get("name", f"Unnamed Task ({job_id})")

                    if not all([job_id, run_datetime_str, selected_fields_data_str]):
                        logger.warning(f"SchedulerManager: 跳过格式不正确的持久化任务: {task_data}")
                        continue

                    run_datetime = datetime.datetime.fromisoformat(run_datetime_str)
                    selected_fields_data = json.loads(selected_fields_data_str)

                    if run_datetime > now:
                        # 如果在未来，则重新添加到 APScheduler
                        self._scheduler.add_job(
                            self._execute_booking_job,
                            trigger='date',  # 使用 'date' 触发器类型
                            run_date=run_datetime,  # 直接传递 run_date
                            args=[selected_fields_data, run_datetime.date(), email_address, job_id],
                            id=job_id,
                            name=name,
                            replace_existing=True
                        )
                        logger.info(f"SchedulerManager: 已将待执行任务 '{job_id}' 重新添加到 APScheduler。")
                    else:
                        # 如果已过期，则立即执行
                        logger.info(f"SchedulerManager: 持久化任务 '{job_id}' 已过期。立即执行。")
                        # 在单独的 QThread 中执行，避免阻塞主线程
                        execute_thread = QThread()
                        execute_thread.run = lambda: self._execute_booking_job(selected_fields_data,
                                                                               run_datetime.date(), email_address,
                                                                               job_id=job_id)
                        execute_thread.start()
                        # _execute_booking_job 会在执行完成后从 Firestore 中删除该任务。

                except (ValueError, json.JSONDecodeError, KeyError) as e:
                    logger.error(f"SchedulerManager: 处理持久化任务 {task_data.get('id')} 时出错: {e}")
                    # 如果解析失败，考虑删除该格式错误的任务
                    if task_data.get('id') and firebase_manager.is_ready():
                        delete_malformed_thread = FirestoreAsyncTaskThread(
                            firebase_manager.delete_document, TASKS_COLLECTION, task_data['id']
                        )
                        delete_malformed_thread.start()
                        logger.warning(f"SchedulerManager: 已请求从 Firestore 删除格式错误的任务 '{task_data['id']}'。")
                continue
            logger.info("SchedulerManager: 已完成加载持久化任务。")

        # 连接信号槽，当 FirestoreAsyncTaskThread 完成时调用 on_load_finished
        load_thread.finished.connect(on_load_finished)
        load_thread.start()


# 创建并导出调度器管理器单例
scheduler_manager = SchedulerManager()
