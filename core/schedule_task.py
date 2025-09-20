# core/schedule_task.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import datetime
import time
import json
from loguru import logger

# 导入API函数
from API.Badminiton.API import OrderField, OrderFieldFree
# 导入邮件发送脚本
from tools.email_sender import send_email


# 注意：此版本暂时移除了数据库持久化功能。
# 如果应用程序关闭，所有已添加但尚未执行的定时任务将会丢失。

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
            # 初始化 BackgroundScheduler
            # BackgroundScheduler 适合在 GUI 应用中运行，因为它不会阻塞主线程。
            cls._scheduler = BackgroundScheduler()
            logger.info("SchedulerManager: BackgroundScheduler 已初始化。")
        return cls._instance

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
            # wait=False 避免阻塞，让调度器尽快关闭
            self._scheduler.shutdown(wait=False)
            logger.info("SchedulerManager: BackgroundScheduler 已关闭。")

    def add_booking_task(self, selected_fields_data: list, booking_date: datetime.date, script_date: datetime.date, script_time: datetime.time,
                         email_address: str = ""):
        """
        添加一个定时预约任务。
        此版本不进行数据库持久化。
        """
        # 组合日期和时间，得到任务执行的精确时间
        run_datetime = datetime.datetime.combine(script_date, script_time)
        logger.warning(f"booking_date:{booking_date} script_date: {script_date} script_time: {script_time}")
        # 生成一个唯一的任务ID (仅用于 APScheduler 内部识别)
        job_id = f"booking_job_{run_datetime.timestamp()}_{hash(json.dumps(selected_fields_data, sort_keys=True))}"

        # 确保任务执行时间在未来
        if run_datetime <= datetime.datetime.now():
            logger.warning(
                f"SchedulerManager: 任务执行时间 {run_datetime.strftime('%Y-%m-%d %H:%M:%S')} 已过期或为当前时间，将尝试立即执行。")
            # 如果时间已过，直接执行预约逻辑
            self._execute_booking_job(selected_fields_data, booking_date, email_address, job_id=job_id)  # 传递 job_id
            return

        # 添加任务到调度器
        self._scheduler.add_job(
            self._execute_booking_job,
            trigger=DateTrigger(run_date=run_datetime),  # 使用 DateTrigger 在指定日期时间执行
            args=[selected_fields_data, booking_date, email_address, job_id],  # 传递 job_id
            id=job_id,
            name=f"场馆预约任务 ({booking_date.strftime('%Y-%m-%d')} {script_time.strftime('%H:%M')})",
            replace_existing=True  # 如果有相同ID的任务，则替换
        )
        logger.info(
            f"SchedulerManager: 定时预约任务已添加，将在 {run_datetime.strftime('%Y-%m-%d %H:%M:%S')} 执行。任务ID: {job_id}")
        logger.debug(f"SchedulerManager: 预约详情: {json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}")

    def _execute_booking_job(self, selected_fields_data: list, booking_date: datetime.date, email_address: str = "",
                             job_id: str = None):
        """
        实际执行预约的函数，由APScheduler在指定时间调用。
        此函数将在调度器的后台线程中运行。
        此版本不进行数据库删除操作。
        """
        logger.info(
            f"SchedulerManager: >>> _execute_booking_job 函数开始执行，任务ID: {job_id if job_id else 'N/A'}，当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} <<<")
        print(
            f"DEBUG: 定时任务 _execute_booking_job 正在执行！当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(0.5)
        current_date = datetime.date.today()
        dateadd = (booking_date - current_date).days
        logger.warning(f"booking_date:{booking_date},current_date:{current_date},dateadd:{dateadd}")
        venue_no = "02"  # 羽毛球场馆编号，假设固定

        if dateadd < 0:
            logger.warning(f"SchedulerManager: 尝试预约过去的日期 (dateadd={dateadd})，这可能不是预期行为。")

        start_time = time.time()
        end_time = start_time + 10  # 10-second window for retries
        attempt = 0
        booking_successful = False
        final_email_subject = ""
        final_email_content = ""

        # Loop for 10 seconds or until success/definitive failure
        while time.time() < end_time and not booking_successful:
            attempt += 1
            logger.info(
                f"SchedulerManager: Attempt {attempt} to execute booking task for target date: {booking_date.strftime('%Y-%m-%d')}.")

            try:
                logger.info(
                    f"SchedulerManager: Calling OrderField API, params: checkdata={selected_fields_data}, dateadd={dateadd}, VenueNo={venue_no}")
                # response = OrderField(selected_fields_data, dateadd, venue_no)
                response = OrderFieldFree(selected_fields_data, dateadd, venue_no)
                logger.info(f"SchedulerManager: OrderField API Response: {response}")

                message = response.get("message", "Unknown result")
                response_type = response.get("type")

                if response_type == 1 and response.get("errorcode") == 0:
                    logger.success(f"SchedulerManager: Booking successful! Order ID: {response.get('resultdata')}")
                    final_email_subject = "场馆预约成功提醒"
                    final_email_content = f"您的场馆已成功预约！\n\n预约详情:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}\n\n订单号: {response.get('resultdata')}"
                    booking_successful = True  # Set flag to exit loop
                elif response_type == 3 and response.get("errorcode") == 0:
                    logger.warning(f"SchedulerManager: Booking failed (conflict/too slow): {message}. Retrying...")
                    # This is a temporary failure, continue retrying within the window
                    final_email_subject = "场馆预约失败提醒 (尝试中)"  # Keep this for final email if all attempts fail
                    final_email_content = f"您的场馆预约失败：{message}\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}\n\n将继续尝试..."
                else:
                    logger.error(
                        f"SchedulerManager: Booking failed: {message} (Error code: {response.get('errorcode')}). Stopping retries.")
                    final_email_subject = "场馆预约失败提醒"
                    final_email_content = f"您的场馆预约失败：{message} (错误码: {response.get('errorcode')})\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}"
                    break  # Definitive failure, stop trying

            except Exception as e:
                logger.error(f"SchedulerManager: Error during booking attempt {attempt}: {e}. Retrying...")
                final_email_subject = "场馆预约任务执行错误 (尝试中)"
                final_email_content = f"执行场馆预约任务时发生错误：{e}\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}\n\n将继续尝试..."

            # Add a small delay between attempts to avoid overwhelming the API
            if not booking_successful and time.time() < end_time:
                time.sleep(3.75)  # Wait for 0.5 seconds before next attempt

        # After the loop, send the final email based on the outcome
        if email_address:
            if booking_successful:
                logger.info(f"SchedulerManager: Booking successful. Sending final success email to {email_address}.")
                send_email(email_address, final_email_subject, final_email_content)
            else:
                logger.warning(
                    f"SchedulerManager: Booking failed after all attempts or definitive error. Sending final failure email to {email_address}.")
                # If no definitive failure, but time ran out, provide a generic failure message.
                if not final_email_subject or "尝试中" in final_email_subject:  # If subject was temporary or not set
                    final_email_subject = "场馆预约失败提醒"
                    final_email_content = f"您的场馆预约在规定时间内未能成功。\n\n尝试预约的场地:\n{json.dumps(selected_fields_data, indent=2, ensure_ascii=False)}"
                send_email(email_address, final_email_subject, final_email_content)
        elif not email_address and not booking_successful:
            logger.warning("SchedulerManager: No email address provided and booking failed after all attempts.")

        # 任务执行完毕后，此版本不从数据库中删除任务，因为没有持久化。
        # 如果需要，可以从 APScheduler 中移除已完成的任务。
        if job_id:
            try:
                self._scheduler.remove_job(job_id)
                logger.info(f"SchedulerManager: 已从 APScheduler 移除已执行任务 '{job_id}'。")
            except Exception as e:
                logger.warning(f"SchedulerManager: 移除 APScheduler 任务 '{job_id}' 失败: {e}")

    def get_pending_jobs_info(self) -> list[dict]:
        """
        获取当前 APScheduler 中所有待执行的定时任务信息。
        此版本不从数据库获取，只返回 APScheduler 内存中的任务。
        """
        jobs_info = []
        for job in self._scheduler.get_jobs():
            # APScheduler 的 job.next_run_time 是 datetime 对象
            next_run_time_str = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "N/A"
            jobs_info.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run_time_str,
                "status": "待执行"  # APScheduler 中的任务都是待执行的
            })
        logger.info(f"SchedulerManager: 从 APScheduler 获取到 {len(jobs_info)} 个待执行任务。")
        return jobs_info

    def remove_job(self, job_id: str) -> bool:
        """
        根据任务ID从调度器中删除任务。
        此版本不涉及数据库删除。
        :param job_id: 要删除的任务的ID。
        :return: 如果任务成功删除则返回True，否则返回False。
        """
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"SchedulerManager: 任务 '{job_id}' 已成功从 APScheduler 删除。")
            return True
        except Exception as e:
            logger.error(f"SchedulerManager: 从 APScheduler 删除任务 '{job_id}' 失败: {e}")
            return False

    def load_persisted_tasks(self):
        """
        此版本不从任何持久化存储加载任务，因为已移除数据库功能。
        """
        logger.info("SchedulerManager: 已禁用任务持久化加载功能。")


# 创建并导出调度器管理器单例
scheduler_manager = SchedulerManager()
