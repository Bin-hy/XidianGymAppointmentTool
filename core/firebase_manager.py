import json
import os
from typing import Optional

from loguru import logger
from PySide6.QtCore import QObject, Signal, QTimer  # 导入 QObject, Signal, QTimer


# 导入 Firebase SDK 的相关模块
# 注意：在实际的 Python 环境中，你需要安装 firebase-admin SDK。
# 但在Canvas环境中，我们模拟了Firebase JS SDK的全局变量和行为。
# 这里的导入是概念性的，实际运行时会依赖Canvas提供的__firebase_config等。

# 假设这些是全局可用的，或者通过某种方式注入
# from firebase_admin import credentials, initialize_app, auth, firestore
# 如果在PySide6应用中直接使用JS SDK风格的API，需要确保这些API可用
# 这里我们假设有一个适配层或者直接通过全局变量访问。

# 模拟 Firebase JS SDK 的全局变量和函数
# 在 Canvas 环境中，这些变量会由系统注入
# __app_id: str = "your-app-id" # Canvas 会提供
# __firebase_config: str = "{}" # Canvas 会提供
# __initial_auth_token: str = "your-auth-token" # Canvas 会提供

class FirebaseManager(QObject):
    """
    Firebase 管理器，用于处理 Firebase 应用的初始化、认证和 Firestore 交互。
    采用单例模式，确保整个应用只有一个 Firebase 实例。
    """
    _instance = None
    _db = None
    _auth = None
    _user_id = None
    _is_ready = False  # 标记 Firebase 是否已初始化并认证完成

    # 定义信号
    firebase_ready = Signal()  # 当 Firebase 初始化并认证完成后发出
    auth_state_changed = Signal(str)  # 当认证状态改变时发出，传递当前用户ID

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FirebaseManager, cls).__new__(cls)
            # 在这里进行 Firebase 的初始化，确保只初始化一次
            cls._instance._initialize_firebase_app()
        return cls._instance

    def __init__(self):
        super().__init__()
        # 避免重复初始化 QObject
        if not hasattr(self, '_initialized'):
            self._initialized = True
            # 监听认证状态变化（模拟）
            # 在实际的 PySide6 应用中，这需要一个真实的 Firebase Auth 监听器
            # 这里我们通过一个定时器模拟检查认证状态，或者在 signInWithCustomToken 后直接设置
            self._auth_check_timer = QTimer(self)
            self._auth_check_timer.setInterval(1000)  # 每秒检查一次
            self._auth_check_timer.timeout.connect(self._check_auth_state)
            self._auth_check_timer.start()

    def _initialize_firebase_app(self):
        """
        初始化 Firebase 应用、认证和 Firestore。
        """
        if self._db is not None:
            logger.info("FirebaseManager: Firebase 已经初始化，跳过重复初始化。")
            return

        try:
            # 从 Canvas 全局变量获取配置
            firebase_config_str = os.environ.get('__firebase_config', '{}')
            app_id = os.environ.get('__app_id', 'default-app-id')
            initial_auth_token = os.environ.get('__initial_auth_token', '')

            firebaseConfig = json.loads(firebase_config_str)

            # 模拟 Firebase 初始化
            # 在真实的 PySide6 应用中，你会使用 firebase_admin.initialize_app
            # app = initialize_app(credentials.Certificate(firebaseConfig))
            # self.__class__._auth = auth.get_auth(app)
            # self.__class__._db = firestore.client(app)

            # 假设 Canvas 环境提供了直接访问 Firebase SDK 的方式
            # 或者我们在这里模拟这些对象的存在
            logger.info("FirebaseManager: 模拟 Firebase 应用初始化...")
            # 实际的 Firebase 初始化逻辑（在 Canvas 环境中，这些通常是全局可用的）
            # 例如：
            # app = firebase.initializeApp(firebaseConfig);
            # self.__class__._auth = firebase.auth(app);
            # self.__class__._db = firebase.firestore(app);

            # 这里我们直接假设 _db 和 _auth 已经可以通过某种方式“获取”到
            # 假设 Canvas 运行时会提供一个全局的 db 和 auth 对象
            try:
                # 尝试从全局范围获取 db 和 auth 对象，这依赖于 Canvas 的具体实现
                # 这是一个假设，实际可能需要更具体的 Canvas 运行时 API
                global db, auth  # 假设 db 和 auth 是全局变量
                self.__class__._db = db
                self.__class__._auth = auth
                logger.info("FirebaseManager: 已从全局获取 Firebase db 和 auth 实例。")
            except NameError:
                logger.warning(
                    "FirebaseManager: 无法从全局获取 Firebase db 和 auth 实例。请确保 Canvas 环境已正确设置 Firebase SDK。")
                # 如果无法获取，则需要手动模拟或抛出错误
                # For now, we'll proceed with None and rely on later checks.
                self.__class__._db = None
                self.__class__._auth = None

            # 尝试认证
            self._authenticate_user(initial_auth_token)

        except Exception as e:
            logger.error(f"FirebaseManager: Firebase 初始化失败: {e}")
            self.__class__._is_ready = False

    def _authenticate_user(self, initial_auth_token: str):
        """
        尝试认证用户。
        """
        if self._auth is None:
            logger.error("FirebaseManager: Auth 实例未初始化，无法认证用户。")
            return

        try:
            if initial_auth_token:
                # 模拟 signInWithCustomToken
                # await signInWithCustomToken(self._auth, initial_auth_token)
                logger.info("FirebaseManager: 尝试使用自定义令牌认证...")
                # 在真实 PySide6 应用中，这里会调用 Firebase Admin SDK 的 auth 方法
                # user = self._auth.sign_in_with_custom_token(initial_auth_token)
                # self.__class__._user_id = user.uid
                # self.__class__._is_ready = True
                # self.firebase_ready.emit()
                # self.auth_state_changed.emit(self._user_id)

                # 假设成功，直接设置用户ID (在Canvas模拟环境中)
                self.__class__._user_id = initial_auth_token  # 简单模拟用户ID
                self.__class__._is_ready = True
                self.firebase_ready.emit()
                self.auth_state_changed.emit(self._user_id)
                logger.info(f"FirebaseManager: 用户已通过自定义令牌认证。用户ID: {self._user_id}")
            else:
                # 模拟 signInAnonymously
                # await signInAnonymously(self._auth)
                logger.info("FirebaseManager: 尝试匿名认证...")
                # user = self._auth.sign_in_anonymously()
                # self.__class__._user_id = user.uid
                # self.__class__._is_ready = True
                # self.firebase_ready.emit()
                # self.auth_state_changed.emit(self._user_id)

                # 假设成功，直接生成匿名用户ID (在Canvas模拟环境中)
                import uuid
                self.__class__._user_id = str(uuid.uuid4())  # 生成一个随机UUID作为匿名用户ID
                self.__class__._is_ready = True
                self.firebase_ready.emit()
                self.auth_state_changed.emit(self._user_id)
                logger.info(f"FirebaseManager: 用户已匿名认证。用户ID: {self._user_id}")

        except Exception as e:
            logger.error(f"FirebaseManager: 用户认证失败: {e}")
            self.__class__._is_ready = False

    def _check_auth_state(self):
        """
        模拟检查认证状态，并更新 _user_id 和 _is_ready 标志。
        在真实应用中，这会通过 onAuthStateChanged 监听器完成。
        """
        if self._auth and self._auth.currentUser:  # 假设有 currentUser 属性
            current_uid = self._auth.currentUser.uid
            if self._user_id != current_uid:
                self.__class__._user_id = current_uid
                self.__class__._is_ready = True
                self.auth_state_changed.emit(self._user_id)
                logger.info(f"FirebaseManager: 认证状态更新，当前用户ID: {self._user_id}")
            elif not self._is_ready:
                self.__class__._is_ready = True
                self.firebase_ready.emit()
                logger.info("FirebaseManager: Firebase 已准备就绪 (通过定时器检查)。")
        elif self._is_ready:  # 如果之前是ready，现在不是了
            self.__class__._is_ready = False
            self.__class__._user_id = None
            self.auth_state_changed.emit("")  # 发送空字符串表示未登录
            logger.warning("FirebaseManager: 用户已登出或认证失效。")

    def get_user_id(self) -> Optional[str]:
        """
        获取当前认证用户的ID。
        """
        return self._user_id

    def is_ready(self) -> bool:
        """
        检查 Firebase 是否已初始化并认证完成。
        """
        return self._is_ready and self._db is not None and self._auth is not None

    def _get_collection_path(self, collection_name: str) -> str:
        """
        获取 Firestore 集合的完整路径。
        使用私有数据路径：/artifacts/{appId}/users/{userId}/{your_collection_name}
        """
        if not self._user_id:
            logger.error("FirebaseManager: 无法获取用户ID，无法构建 Firestore 路径。")
            raise ValueError("User not authenticated.")

        app_id = os.environ.get('__app_id', 'default-app-id')
        return f"artifacts/{app_id}/users/{self._user_id}/{collection_name}"

    async def add_document(self, collection_name: str, document_id: str, data: dict):
        """
        向 Firestore 添加或设置一个文档。
        :param collection_name: 集合名称。
        :param document_id: 文档ID。
        :param data: 要保存的数据。
        """
        if not self.is_ready():
            logger.error("FirebaseManager: Firebase 未准备就绪，无法添加文档。")
            raise RuntimeError("Firebase is not ready.")

        try:
            collection_ref = self._db.collection(self._get_collection_path(collection_name))
            await collection_ref.document(document_id).set(data)
            logger.info(f"FirebaseManager: 文档 '{document_id}' 已添加到集合 '{collection_name}'。")
        except Exception as e:
            logger.error(f"FirebaseManager: 添加文档 '{document_id}' 失败: {e}")
            raise

    async def get_documents(self, collection_name: str) -> list[dict]:
        """
        从 Firestore 获取指定集合的所有文档。
        :param collection_name: 集合名称。
        :return: 文档数据列表。
        """
        if not self.is_ready():
            logger.error("FirebaseManager: Firebase 未准备就绪，无法获取文档。")
            return []

        try:
            collection_ref = self._db.collection(self._get_collection_path(collection_name))
            docs = await collection_ref.get()
            documents_data = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id  # 将文档ID也包含在数据中
                documents_data.append(data)
            logger.info(f"FirebaseManager: 从集合 '{collection_name}' 获取到 {len(documents_data)} 个文档。")
            return documents_data
        except Exception as e:
            logger.error(f"FirebaseManager: 获取集合 '{collection_name}' 文档失败: {e}")
            return []

    async def delete_document(self, collection_name: str, document_id: str):
        """
        从 Firestore 删除一个文档。
        :param collection_name: 集合名称。
        :param document_id: 要删除的文档ID。
        """
        if not self.is_ready():
            logger.error("FirebaseManager: Firebase 未准备就绪，无法删除文档。")
            raise RuntimeError("Firebase is not ready.")

        try:
            collection_ref = self._db.collection(self._get_collection_path(collection_name))
            await collection_ref.document(document_id).delete()
            logger.info(f"FirebaseManager: 文档 '{document_id}' 已从集合 '{collection_name}' 删除。")
        except Exception as e:
            logger.error(f"FirebaseManager: 删除文档 '{document_id}' 失败: {e}")
            raise


# 创建并导出 Firebase 管理器单例
firebase_manager = FirebaseManager()
