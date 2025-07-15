import hashlib
import time
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
from typing import Dict, Any, Optional
from tools.logger import logger

# 导入凭证配置管理器
from config.credentials_config import credentials_manager

# 配置区：根据你的项目结构，这些可能来自 config.config
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json;charset=UTF-8'
    # 根据你的API实际需求添加更多头信息
}

# 创建Session对象并配置重试策略
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

session.mount('http://', HTTPAdapter(max_retries=retry_strategy))
session.mount('https://', HTTPAdapter(max_retries=retry_strategy))

# 在模块加载时，初始化 session 的 headers
# Note: Cookies will be set dynamically before each request or when explicitly needed.
session.headers.update(HEADERS)


def _update_session_with_credentials():
    """
    从CredentialsConfig获取最新凭证并更新requests.Session。
    这个函数会在每次请求前被调用，确保使用最新的凭证。
    """
    # 清除旧的Cookie，避免重复或过期Cookie的干扰
    session.cookies.clear()

    # 获取并设置Cookies
    current_cookies = credentials_manager.get_cookies()
    if current_cookies:
        requests.utils.add_dict_to_cookiejar(session.cookies, current_cookies)
        logger.debug("Session cookies已从CredentialsConfig更新。")
    else:
        logger.warning("CredentialsConfig中没有可用的Cookie。")

    # 如果JWTUserToken需要作为Authorization Header发送，可以在这里添加
    # 你的凭证显示JWTUserToken已经在Cookie中，所以通常不需要额外添加到Header
    # 但如果未来API要求Header，可以这样添加：
    # jwt_token = credentials_manager.get_jwt_user_token()
    # if jwt_token and "Authorization" not in session.headers:
    #     session.headers.update({'Authorization': f'Bearer {jwt_token}'})
    #     logger.debug("Session Authorization Header (JWT) 已更新。")


def appSign(params: Dict[str, Any]) -> Dict[str, Any]:
    '''为请求 添加 认证信息 (如果API需要特殊签名)
    :param params: 请求参数
    :return: 添加签名后的参数
    '''
    try:
        params["_"] = time.time()# 当前时间戳
        pass # 你的签名逻辑
        return params
    except Exception as e:
        logger.error(f"appSign 签名失败: {e}")
        raise

def get_request(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    发送 GET 请求，自动携带Session中的Cookie和Headers。
    :param url: 请求URL
    :param params: GET请求的查询参数
    :return: 响应JSON数据
    """
    if params is None:
        params = {}
    try:
        # 在每次请求前更新session的凭证
        _update_session_with_credentials()

        signed_params = appSign(params)
        logger.debug(f'发送GET请求: {url}, 参数: {signed_params}')
        response = session.get(url, params=signed_params)
        response.raise_for_status()
        data = response.json()
        logger.debug(f'GET请求成功: {data}')
        return data
    except requests.exceptions.HTTPError as e:
        logger.error(f'GET请求HTTP错误: {e}\n响应内容: {e.response.text}')
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f'GET请求失败: {e}')
        raise
    except ValueError as e:
        logger.error(f'解析GET响应JSON失败: {e}')
        raise

def post_request(url: str, json_data: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    发送 POST 请求，自动携带Session中的Cookie和Headers。
    根据Content-Type，选择发送json或data。
    :param url: 请求URL
    :param json_data: POST请求的JSON体数据
    :param data: POST请求的表单数据
    :return: 响应JSON数据
    """
    try:
        # 在每次请求前更新session的凭证
        _update_session_with_credentials()

        logger.debug(f'发送POST请求: {url}, JSON数据: {json_data}, 表单数据: {data}')

        if json_data is not None:
            response = session.post(url, json=json_data)
        elif data is not None:
            response = session.post(url, data=data)
        else:
            response = session.post(url)

        response.raise_for_status()
        data = response.json()
        logger.debug(f'POST请求成功: {data}')
        return data
    except requests.exceptions.HTTPError as e:
        logger.error(f'POST请求HTTP错误: {e}\n响应内容: {e.response.text}')
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f'POST请求失败: {e}')
        raise
    except ValueError as e:
        logger.error(f'解析POST响应JSON失败: {e}')
        raise

# 将原代码中的get函数名改为get_request，并提供 post_request
get = get_request
post = post_request