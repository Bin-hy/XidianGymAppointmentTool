import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from loguru import logger
import threading  # 用于确保线程安全

# 定义数据库文件路径
# 假设数据库文件位于项目根目录下的 'data' 文件夹中
DATABASE_NAME = "appointment_tasks.db"
_db_path = None  # 私有变量，用于存储完整的数据库路径
_db_path_lock = threading.Lock()  # 用于保护 _db_path 的设置


def set_database_path(project_root_dir: str):
    """
    设置数据库文件的完整路径。此函数应在应用程序启动时调用一次。
    """
    global _db_path
    with _db_path_lock:
        if _db_path is None:
            data_dir = os.path.join(project_root_dir, "data")
            os.makedirs(data_dir, exist_ok=True)  # 确保数据目录存在
            _db_path = os.path.join(data_dir, DATABASE_NAME)
            logger.info(f"SQLiteManager: 数据库路径已设置为: {_db_path}")


class SQLiteManager:
    """
    SQLite 数据库管理器，用于持久化和管理定时预约任务。
    采用单例模式，确保整个应用只有一个数据库管理器实例。
    """
    _instance = None
    _initialized = False  # 标记是否已初始化数据库

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SQLiteManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._create_table_if_not_exists()

    def _get_db_connection(self):
        """
        获取一个到 SQLite 数据库的连接。
        确保在每次操作时都获取新连接并正确关闭，以保证线程安全。
        """
        with _db_path_lock:
            if _db_path is None:
                logger.error("SQLiteManager: 数据库路径未设置。请先调用 set_database_path()。")
                raise RuntimeError("Database path not set.")
            return sqlite3.connect(_db_path)

    def _create_table_if_not_exists(self):
        """
        如果 'tasks' 表不存在，则创建它。
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    run_datetime TEXT NOT NULL,
                    selected_fields_data TEXT NOT NULL,
                    email_address TEXT
                )
            """)
            conn.commit()
            logger.info("SQLiteManager: 'tasks' 表已检查或创建成功。")
        except sqlite3.Error as e:
            logger.error(f"SQLiteManager: 创建表失败: {e}")
        finally:
            if conn:
                conn.close()

    def add_task(self, task_data: Dict[str, Any]):
        """
        向数据库添加一个新任务。
        如果任务已存在，则更新它。
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # 将 selected_fields_data 转换为 JSON 字符串存储
            selected_fields_data_json = json.dumps(task_data["selected_fields_data"], ensure_ascii=False)

            cursor.execute("""
                INSERT OR REPLACE INTO tasks (id, name, run_datetime, selected_fields_data, email_address)
                VALUES (?, ?, ?, ?, ?)
            """, (
                task_data["id"],
                task_data["name"],
                task_data["run_datetime"],
                selected_fields_data_json,
                task_data.get("email_address", "")
            ))
            conn.commit()
            logger.info(f"SQLiteManager: 任务 '{task_data['id']}' 已添加/更新到数据库。")
        except sqlite3.Error as e:
            logger.error(f"SQLiteManager: 添加/更新任务 '{task_data['id']}' 失败: {e}")
        finally:
            if conn:
                conn.close()

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        从数据库获取所有任务。
        """
        conn = None
        tasks = []
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, run_datetime, selected_fields_data, email_address FROM tasks")
            rows = cursor.fetchall()

            for row in rows:
                task = {
                    "id": row[0],
                    "name": row[1],
                    "run_datetime": row[2],
                    "selected_fields_data": json.loads(row[3]),  # 从 JSON 字符串解析回 Python 对象
                    "email_address": row[4]
                }
                tasks.append(task)
            logger.info(f"SQLiteManager: 从数据库获取到 {len(tasks)} 个任务。")
        except sqlite3.Error as e:
            logger.error(f"SQLiteManager: 获取所有任务失败: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"SQLiteManager: 解析 selected_fields_data 失败: {e}")
        finally:
            if conn:
                conn.close()
        return tasks

    def delete_task(self, task_id: str):
        """
        从数据库删除指定ID的任务。
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            logger.info(f"SQLiteManager: 任务 '{task_id}' 已从数据库删除。")
        except sqlite3.Error as e:
            logger.error(f"SQLiteManager: 删除任务 '{task_id}' 失败: {e}")
        finally:
            if conn:
                conn.close()


# 创建并导出 SQLite 管理器单例
sqlite_manager = SQLiteManager()
