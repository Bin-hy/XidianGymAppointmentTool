from tools.request_b import get,post

# 登陆成功后获取用户信息
def GetUserInfo():
    """
    获取到用户信息
    :return:
    """
    return get("https://gyytygyy.xidian.edu.cn/User/GetUserInfo")