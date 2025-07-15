import webbrowser
import os

from PySide6.QtNetwork import QNetworkRequest, QNetworkReply, QNetworkAccessManager
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTextEdit,
    QFrame, QStackedWidget, QMessageBox, QGroupBox, QFormLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QTextCursor, QPixmap, QPainter, QBrush, QColor, QPainterPath, QIcon

from loguru import logger
from config.credentials_config import credentials_manager  # 用于用户状态组件
from gui.threads import GetUserInfoThread
from tools.gui_logger import LogViewer, setup_gui_logger  # 导入日志查看器和设置函数
from API.User.API import GetUserInfo  # 导入用户信息获取函数


# --- 日志组件 (集成日志查看器) ---
class LogWidget(QWidget):
    """日志显示组件，集成 LogViewer 并提供状态指示器和清空按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        # 配置 Loguru 将日志输出到这个 LogViewer
        setup_gui_logger(self.log_viewer)

    def initUI(self):
        """初始化 UI"""
        主布局 = QVBoxLayout(self)
        主布局.setContentsMargins(0, 0, 0, 0)

        日志分组框 = QGroupBox("📋 应用日志")
        日志布局 = QVBoxLayout(日志分组框)
        日志布局.setContentsMargins(15, 15, 15, 15)
        日志布局.setSpacing(10)

        日志工具栏 = QHBoxLayout()

        self.状态指示器 = QLabel("🟢 准备就绪")
        self.状态指示器.setObjectName("statusIndicator")  # 用于 QSS 样式

        日志工具栏.addWidget(self.状态指示器)
        日志工具栏.addStretch()

        清空按钮 = QPushButton("🗑️ 清空日志")
        清空按钮.setMaximumWidth(150)
        清空按钮.clicked.connect(self.clear_log)
        日志工具栏.addWidget(清空按钮)

        日志布局.addLayout(日志工具栏)

        self.log_viewer = LogViewer()  # 使用专用的日志查看器
        self.log_viewer.setObjectName("LogViewer")  # 用于 QSS 样式
        self.log_viewer.setMinimumHeight(150)
        self.log_viewer.setPlaceholderText("日志消息将在此处显示...")
        日志布局.addWidget(self.log_viewer)

        主布局.addWidget(日志分组框)

    def clear_log(self):
        """清空日志"""
        self.log_viewer.clear()
        self.状态指示器.setText("🟢 准备就绪")

    def set_status(self, status_text: str):
        """设置状态指示器文本"""
        self.状态指示器.setText(status_text)


# --- 用户状态组件 (替换主窗口顶部行) ---
class UserStatusWidget(QWidget):
    """
    显示用户状态（登录/注销）、用户名和头像，并包含登录/注销按钮。
    """
    login_logout_clicked = Signal()  # 信号：登录/注销按钮被点击

    def __init__(self, parent=None):
        super().__init__(parent)
        self.已登录 = False
        self.网络管理器 = QNetworkAccessManager(self)  # 用于头像下载
        self.获取用户信息线程 = None  # 初始化线程引用
        self.initUI()
        self._加载初始用户状态()  # 初始化时加载状态

    def initUI(self):
        """初始化 UI"""
        布局 = QHBoxLayout(self)
        布局.setContentsMargins(0, 0, 0, 0)
        布局.setSpacing(20)

        # 用户头像
        self.用户头像标签 = QLabel()
        self.用户头像标签.setFixedSize(60, 60)  # 头像在组件内略小
        self.用户头像标签.setScaledContents(True)  # 允许图片缩放
        self.用户头像标签.setStyleSheet("""
            QLabel {
                border-radius: 30px; /* 固定尺寸的一半，用于圆形 */
                background-color: #f0f0f0; /* 默认背景色 */
                border: 1px solid #ccc; /* 边框 */
            }
        """)
        self.用户头像标签.setAlignment(Qt.AlignmentFlag.AlignCenter)
        布局.addWidget(self.用户头像标签)

        # 用户名
        self.用户名标签 = QLabel("用户名: 未登录")
        self.用户名标签.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.用户名标签.setStyleSheet("font-size: 14px; font-weight: bold;")
        布局.addWidget(self.用户名标签)
        布局.addStretch(1)

        # 登录/注销按钮
        self.登录注销按钮 = QPushButton("登录")
        self.登录注销按钮.setObjectName("loginButton")  # 用于 QSS 样式
        self.登录注销按钮.setFixedSize(100, 35)  # 按钮略小
        self.登录注销按钮.clicked.connect(self.login_logout_clicked.emit)
        布局.addWidget(self.登录注销按钮)

    def _加载初始用户状态(self):
        """根据凭证加载初始用户状态。"""
        # 初始状态不再尝试获取用户信息，等待 Firebase 认证信号
        if credentials_manager.get_cookies():
            self.set_logged_in_state(True)
            # self._获取并显示用户信息() # 移除此处的直接调用
        else:
            self.set_logged_in_state(False)

    def set_logged_in_state(self, is_logged_in: bool):
        """根据登录状态更新 UI。"""
        self.已登录 = is_logged_in
        if is_logged_in:
            self.登录注销按钮.setText("注销")
            # 用户名和头像在 _获取并显示用户信息 或 set_user_id 中更新
            self.用户名标签.setText("用户名: 加载中...")  # 初始设置为加载中
        else:
            self.登录注销按钮.setText("登录")
            self.用户名标签.setText("用户名: 未登录")
            self.用户头像标签.clear()  # 清空头像

    def set_user_id(self, user_id: str):
        """
        设置并显示用户ID，并根据ID是否存在决定是否获取用户详细信息。
        这个方法将连接到 firebase_manager.auth_state_changed 信号。
        """
        logger.debug(f"用户状态组件: set_user_id 被调用，user_id: {user_id}")
        if user_id:
            logger.info(f"用户状态组件: 接收到用户ID: {user_id}。正在获取用户详细信息。")
            self.set_logged_in_state(True)  # 标记为已登录
            self._获取并显示用户信息()  # 获取并显示详细用户信息
        else:
            logger.info("用户状态组件: 接收到空用户ID。标记为未登录。")
            self.set_logged_in_state(False)  # 标记为未登录

    def _获取并显示用户信息(self):
        """获取用户信息并更新 UI。"""
        logger.info("用户状态组件: 正在尝试获取用户信息...")
        # 避免重复启动线程
        if self.获取用户信息线程 and self.获取用户信息线程.isRunning():
            logger.warning("用户状态组件: 获取用户信息线程已在运行中，跳过重复启动。")
            return

        # 使用线程获取用户信息，避免阻塞 UI
        self.获取用户信息线程 = GetUserInfoThread()
        self.获取用户信息线程.user_info_fetched.connect(self._用户信息获取成功)
        self.获取用户信息线程.error_occurred.connect(self._用户信息获取失败)
        self.获取用户信息线程.start()
        logger.debug("用户状态组件: 获取用户信息线程已启动。")

    def _用户信息获取成功(self, response_data: dict):
        """处理用户信息获取成功后的数据。"""
        logger.info("用户状态组件: 用户信息获取成功信号接收。")
        用户信息 = response_data.get("data")
        if 用户信息:
            用户名 = 用户信息.get("UserName", "未知用户")
            用户头像URL = 用户信息.get("Photo")

            self.用户名标签.setText(f"用户名: {用户名}")
            logger.info(f"用户状态组件: 已获取用户名: {用户名}")

            if 用户头像URL:
                self._加载并显示头像(用户头像URL)
            else:
                self.用户头像标签.setText("无头像")
                logger.warning("用户状态组件: 未获取到用户头像 URL。")
        else:
            self.用户名标签.setText("用户名: 获取失败 (数据为空)")
            self.用户头像标签.setText("头像获取失败")
            logger.warning("用户状态组件: 获取用户信息成功，但返回数据为空或格式不正确。")

        # 确保线程引用被清除，防止内存泄漏
        if self.获取用户信息线程:
            self.获取用户信息线程.quit()
            self.获取用户信息线程.wait()
            self.获取用户信息线程 = None

    def _用户信息获取失败(self, error_message: str):
        """处理用户信息获取失败。"""
        logger.error(f"用户状态组件: 用户信息获取失败信号接收：{error_message}")
        self.用户名标签.setText("用户名: 获取失败")
        self.用户头像标签.setText("头像获取失败")
        logger.error(f"用户状态组件: 获取用户信息时发生错误: {error_message}")

        # 确保线程引用被清除，防止内存泄漏
        if self.获取用户信息线程:
            self.获取用户信息线程.quit()
            self.获取用户信息线程.wait()
            self.获取用户信息线程 = None

    def _加载并显示头像(self, url: str):
        """异步加载并显示头像图片。"""
        logger.info(f"用户状态组件: 正在加载头像: {url}")
        请求 = QNetworkRequest(QUrl(url))
        回复 = self.网络管理器.get(请求)
        回复.finished.connect(lambda: self._头像下载完成(回复))

    def _头像下载完成(self, reply: QNetworkReply):
        """头像图片下载完成后的槽函数。"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            图片数据 = reply.readAll()
            像素图 = QPixmap()
            if 像素图.loadFromData(图片数据):
                圆形像素图 = QPixmap(像素图.size())
                圆形像素图.fill(Qt.GlobalColor.transparent)

                画家 = QPainter(圆形像素图)
                画家.setRenderHint(QPainter.RenderHint.Antialiasing)
                画家.setBrush(QBrush(像素图))
                画家.setPen(Qt.NoPen)

                路径 = QPainterPath()
                路径.addEllipse(圆形像素图.rect())
                画家.setClipPath(路径)

                画家.drawRect(圆形像素图.rect())
                画家.end()

                缩放像素图 = 圆形像素图.scaled(self.用户头像标签.size(),
                                               Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
                self.用户头像标签.setPixmap(缩放像素图)
                logger.info("用户状态组件: 头像加载成功。")
            else:
                self.用户头像标签.setText("头像加载失败")
                logger.error("用户状态组件: 无法从下载数据加载图片。")
        else:
            self.用户头像标签.setText("头像下载失败")
            logger.error(f"用户状态组件: 头像下载失败: {reply.errorString()}")
        reply.deleteLater()


# --- 运动选择组件 ---
class SportSelectionWidget(QWidget):
    """
    显示具有椭圆边框、蓝色边框、左侧徽标和右侧文本的运动导航项。
    """
    sport_selected = Signal(str)  # 信号：发射选定运动的名称

    def __init__(self, parent=None):
        super().__init__(parent)
        self.运动按钮 = {}  # 存储导航项按钮的引用
        self.initUI()
        self.set_buttons_enabled(False)  # 初始禁用

    def initUI(self):
        """初始化 UI"""
        布局 = QHBoxLayout(self)
        布局.setContentsMargins(10, 10, 10, 10)  # 调整边距
        布局.setSpacing(20)  # 导航项之间的间距
        布局.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 设置组件的最小高度，以确保有足够的空间
        self.setMinimumHeight(120)  # 增加整体组件的最小高度

        # 获取项目根目录以加载图片资源
        项目根目录 = os.path.dirname(os.path.abspath(__file__))
        # 回溯查找项目根目录 (假设 assets 文件夹在 project_root/assets)
        while not os.path.exists(os.path.join(项目根目录, 'assets')) and 项目根目录 != os.path.dirname(
                项目根目录):
            项目根目录 = os.path.dirname(项目根目录)
        资源路径 = os.path.join(项目根目录, 'assets')
        logger.info(f"运动选择组件: 资源路径解析为: {资源路径}")

        运动列表 = {
            "羽毛球": "羽毛球.png",
            "乒乓球": "乒乓球.png",
            "篮球": "篮球.png",
            "健身": "健身.png"
        }

        for 运动中文名, 图标文件 in 运动列表.items():
            图标路径 = os.path.join(资源路径, 图标文件)
            logger.info(f"运动选择组件: 正在尝试从 {图标路径} 加载图标")

            图标 = QIcon()  # 默认空图标
            if os.path.exists(图标路径):
                图标 = QIcon(图标路径)
                logger.info(f"运动选择组件: 成功加载 {运动中文名} 的图标。")
            else:
                logger.warning(f"运动选择组件: 未找到 {运动中文名} 的图标文件: {图标路径}")
                # 如果未找到图标，QLabel 将显示 '?'

            # 创建 QPushButton 作为每个导航项的基础
            按钮 = QPushButton("")  # 文本为空，因为文本将在 QLabel 中
            # 使用中文名作为对象名，确保与 QSS 使用时的一致性
            按钮.setObjectName(f"navButton_{运动中文名.replace(' ', '')}")

            # 调整尺寸以适应新设计，容纳图标和文本
            # 保持固定宽度 200，高度 100，以确保椭圆形
            按钮.setFixedSize(200, 100)
            按钮.setStyleSheet(f"""
                QPushButton#{按钮.objectName()} {{
                    background-color: #ffffff;
                    border: 2px solid #007bff; /* 蓝色边框 */
                    border-radius: 50px; /* 椭圆边框 (100px 高度的一半) */
                    padding: 0px; /* 布局处理内部填充 */
                    text-align: left; /* 如果需要，文本对齐，但布局将控制 */
                }}
                QPushButton#{按钮.objectName()}:hover {{
                    background-color: #e0f7fa; /* 悬停时浅蓝色 */
                    border-color: #0056b3;
                }}
                QPushButton#{按钮.objectName()}:pressed {{
                    background-color: #cceeff; /* 按下时深蓝色 */
                    border-color: #004085;
                }}
                QPushButton#{按钮.objectName()}:disabled {{
                    background-color: #f0f0f0;
                    border-color: #cccccc;
                }}
            """)
            按钮.clicked.connect(lambda checked, s=运动中文名: self.sport_selected.emit(s))
            self.运动按钮[运动中文名] = 按钮

            # 为按钮创建内部布局
            按钮内部布局 = QHBoxLayout(按钮)
            # 调整内部填充，垂直方向设置为 0，使按钮固定高度生效
            按钮内部布局.setContentsMargins(15, 0, 15, 0)
            按钮内部布局.setSpacing(10)  # 图标和文本之间的间距
            按钮内部布局.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # 垂直居中对齐

            # 左侧图标
            图标标签 = QLabel()
            # 从图标获取像素图，并缩放以适应 QLabel 的固定大小
            像素图 = 图标.pixmap(QSize(60, 60))  # 图标大小根据新的按钮高度调整
            if not 像素图.isNull():
                图标标签.setPixmap(像素图)
                图标标签.setScaledContents(True)  # 确保图片在 QLabel 中缩放
            else:
                图标标签.setText("?")  # 如果找不到图标，显示占位符
                图标标签.setStyleSheet("font-size: 30px; color: #999; font-weight: bold;")
            图标标签.setFixedSize(60, 60)  # 图标标签的固定大小
            按钮内部布局.addWidget(图标标签)

            # 右侧文本
            文本标签 = QLabel(运动中文名)
            文本标签.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")  # 增加字体大小
            文本标签.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            文本标签.setWordWrap(True)  # 允许文本换行，如果过长
            按钮内部布局.addWidget(文本标签)
            按钮内部布局.addStretch(1)  # 将文本推到左侧（如果需要）

            布局.addWidget(按钮)  # 将样式化的 QPushButton 添加到主布局

    def set_buttons_enabled(self, enable: bool):
        """启用或禁用运动导航项。"""
        for button in self.运动按钮.values():
            button.setEnabled(enable)
