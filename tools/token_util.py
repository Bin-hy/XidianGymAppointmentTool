# token_util.py

import os
import json
import base64  # 导入 base64 模块用于解码 JWT
import time  # 导入 time 模块用于获取当前时间戳
import datetime  # 新增导入：导入 datetime 模块
from loguru import logger
from http.cookies import SimpleCookie  # 导入 SimpleCookie 用于解析 cookies 字符串

# 导入凭证管理器，用于清除凭证和删除文件
from config.credentials_config import credentials_manager


def get_plaintext_token(project_root_dir: str) -> tuple[str | None, dict | None, dict | None]:
    """
    尝试从 credentials.json 文件中获取明文 token (即 cookies 字符串) 及其解析后的内容。
    同时，如果存在 JWTUserToken，则解析其内容，并检查是否过期。

    参数:
        project_root_dir (str): 应用程序的项目根目录路径。

    返回:
        tuple[str | None, dict | None, dict | None]:
            第一个元素是明文的 cookies 字符串，如果未找到或已过期则为 None。
            第二个元素是解析后的 cookies 字典，如果未找到或解析失败或已过期则为 None。
            第三个元素是解析后的 JWT Payload 字典，如果未找到或解析失败或已过期则为 None。
    """
    # 凭证文件的相对路径
    credentials_relative_path = os.path.join("config", "credentials.json")
    credentials_file_path = os.path.join(project_root_dir, credentials_relative_path)

    logger.info(f"TokenUtil: 正在尝试从文件加载凭证: {credentials_file_path}")

    if not os.path.exists(credentials_file_path):
        logger.warning(f"TokenUtil: 凭证文件不存在: {credentials_file_path}")
        return None, None, None

    try:
        with open(credentials_file_path, 'r', encoding='utf-8') as f:
            credentials_data = json.load(f)
        logger.debug("TokenUtil: 凭证文件已加载。")

        raw_cookies_str = credentials_data.get("cookies")
        parsed_cookies_dict = None
        jwt_payload_dict = None  # 用于存储解析后的 JWT Payload

        if raw_cookies_str:
            logger.success("TokenUtil: 明文 token (cookies) 已成功获取。")
            try:
                # 使用 SimpleCookie 解析 cookies 字符串
                cookie = SimpleCookie()
                cookie.load(raw_cookies_str)

                # 将 SimpleCookie 对象转换为普通字典
                parsed_cookies_dict = {k: v.value for k, v in cookie.items()}
                logger.debug(f"TokenUtil: Cookies 字符串已成功解析为字典: {parsed_cookies_dict}")

                # 尝试从解析后的 cookies 中获取 JWTUserToken
                jwt_token = parsed_cookies_dict.get("JWTUserToken")
                if jwt_token:
                    logger.info("TokenUtil: 发现 JWTUserToken，尝试解析其内容。")
                    try:
                        # JWT 通常是 header.payload.signature
                        # payload 是第二部分，Base64Url 编码
                        parts = jwt_token.split('.')
                        if len(parts) == 3:
                            # Base64Url 解码，需要处理可能的填充
                            payload_encoded = parts[1]
                            missing_padding = len(payload_encoded) % 4
                            if missing_padding:
                                payload_encoded += '=' * (4 - missing_padding)

                            decoded_payload = base64.urlsafe_b64decode(payload_encoded).decode('utf-8')
                            jwt_payload_dict = json.loads(decoded_payload)
                            logger.success(f"TokenUtil: JWT Payload 已成功解析: {jwt_payload_dict}")

                            # --- JWT 过期时间检查 ---
                            exp_timestamp = jwt_payload_dict.get("exp")
                            if exp_timestamp is not None:
                                current_timestamp = time.time()
                                if current_timestamp > exp_timestamp:
                                    logger.warning(
                                        f"TokenUtil: JWT token 已过期！(过期时间: {datetime.datetime.fromtimestamp(exp_timestamp)}, 当前时间: {datetime.datetime.fromtimestamp(current_timestamp)})")
                                    # 如果过期，清除凭证并删除文件
                                    credentials_manager.clear_credentials()
                                    credentials_manager.delete_credentials_file()  # 调用新添加的方法
                                    logger.info("TokenUtil: 已删除过期的 credentials.json 文件。")
                                    return None, None, None  # 返回 None 表示 token 已失效
                                else:
                                    logger.info(
                                        f"TokenUtil: JWT token 有效。(过期时间: {datetime.datetime.fromtimestamp(exp_timestamp)}, 当前时间: {datetime.datetime.fromtimestamp(current_timestamp)})")
                            else:
                                logger.warning("TokenUtil: JWT Payload 中未找到 'exp' 字段。无法检查过期时间。")

                        else:
                            logger.warning("TokenUtil: JWTUserToken 格式不正确 (不包含三个部分)。")
                    except Exception as e:
                        logger.error(f"TokenUtil: 解析 JWTUserToken 失败: {e}")
                        jwt_payload_dict = None  # 解析失败则设为 None
                else:
                    logger.warning("TokenUtil: 解析后的 cookies 中未找到 'JWTUserToken' 键。")

            except Exception as e:
                logger.error(f"TokenUtil: 解析 cookies 字符串失败: {e}")
                parsed_cookies_dict = None  # 解析失败则设为 None

            return raw_cookies_str, parsed_cookies_dict, jwt_payload_dict
        else:
            logger.warning("TokenUtil: 凭证文件中未找到 'cookies' 键。")
            return None, None, None

    except json.JSONDecodeError as e:
        logger.error(f"TokenUtil: 解析凭证文件失败 (JSON 格式错误): {e}")
        return None, None, None
    except Exception as e:
        logger.error(f"TokenUtil: 读取凭证文件时发生未知错误: {e}")
        return None, None, None
