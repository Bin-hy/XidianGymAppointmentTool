from config.app_config import config_manager
from tools.email_sender import send_email
from tools.logger import logger
from tools.request_b import get
from API.Badminiton.API import *
from API.User.API import *
from API.Order.API import *
import os
from config.credentials_config import credentials_manager

if __name__ == '__main__':
    # 获取当前main.py文件所在的目录，即项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    # 设置凭证管理器的项目根目录
    credentials_manager.set_project_root_dir(project_root)
    # t = GetUserInfo()
    t = GetFieldOrder()
    # t = GetWeek()
    # canAppoint = GetVenueStateNew(1,0)
    # t = CheckUserStatus()
    # t = OrderField()
    # t = GetVenueStateNew();
    print(t)

    # 当直接运行此文件时，我们需要手动初始化 config_manager
    # 因为 main.py 的初始化过程不会被执行。




