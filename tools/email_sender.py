# tools/email_sender.py

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from loguru import logger
import os  # 导入 os 模块用于路径操作

# 导入配置管理器
from config.app_config import config_manager
# 导入环境变量键名实体
from config.env_keys import (
    EMAIL_SMTP_SERVER,
    EMAIL_SMTP_PORT,
    EMAIL_USE_TLS,
    EMAIL_SENDER_EMAIL,
    EMAIL_SENDER_PASSWORD
)


def send_email(receiver_email: str, subject: str, content: str) -> bool:
    """
    发送电子邮件。

    :param receiver_email: 收件人邮箱地址。
    :param subject: 邮件主题。
    :param content: 邮件正文。
    :return: 邮件是否成功发送。
    """
    # 从配置管理器获取邮件配置 (现在从环境变量读取，使用常量键名)
    smtp_server = config_manager.get(EMAIL_SMTP_SERVER)
    smtp_port = int(config_manager.get(EMAIL_SMTP_PORT, 587))  # 端口通常是整数
    use_tls = config_manager.get(EMAIL_USE_TLS, "True").lower() == "true"  # 环境变量读取为字符串，需要转换
    sender_email = config_manager.get(EMAIL_SENDER_EMAIL)
    sender_password = config_manager.get(EMAIL_SENDER_PASSWORD)

    if not smtp_server or not smtp_port or not sender_email or not sender_password:
        logger.error(
            "邮件发送配置不完整，请检查 .env 文件中的邮件配置项 (EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, EMAIL_SENDER_EMAIL, EMAIL_SENDER_PASSWORD)。")
        return False

    try:
        # 创建邮件内容
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = Header(f"体育馆预约结果", 'utf-8')
        message['To'] = Header(f"用户 <{receiver_email}>", 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')

        # 根据端口选择不同的 SMTP 类
        if smtp_port == 465 or smtp_port == 994:  # 465 和 994 是常见的隐式 SSL 端口
            logger.info(f"正在尝试使用 SMTP_SSL 连接到 {smtp_server}:{smtp_port}...")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            # 在使用 SMTP_SSL 时，不需要手动调用 starttls()，因为它在连接建立时就处理了 SSL/TLS
        else:  # 比如 25 或 587 端口，可能需要 starttls
            logger.info(f"正在尝试使用 SMTP 连接到 {smtp_server}:{smtp_port}...")
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                logger.info("开启 TLS 加密 (starttls)...")
                server.starttls()  # 开启TLS加密

        # 连接并发送
        with server:
            server.login(sender_email, sender_password)  # 登录邮箱
            server.sendmail(sender_email, receiver_email, message.as_string())  # 发送邮件

        logger.info(f"邮件已成功发送到: {receiver_email}，主题: {subject}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"邮件发送失败: 认证失败。请检查 .env 文件中发件人邮箱和授权码/密码是否正确，并确认SMTP服务已开启。错误: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(
            f"邮件发送失败: 无法连接到SMTP服务器。请检查 .env 文件中服务器地址和端口是否正确，网络是否畅通。错误: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"邮件发送失败: SMTP错误。错误: {e}")
        return False
    except Exception as e:
        logger.error(f"邮件发送失败: 发生未知错误。错误: {e}")
        return False


# 示例用法 (仅供测试，实际应用中请勿直接调用)
if __name__ == '__main__':

    test_receiver = "se_hyxiong@163.com"  # 替换为您的测试收件人邮箱
    test_subject = "场馆预约提醒测试"
    test_content = "这是一封来自场馆预约工具的测试邮件。如果收到，则邮件功能正常。"

    logger.info("正在尝试发送测试邮件...")
    if send_email(test_receiver, test_subject, test_content):
        logger.info("测试邮件发送成功。")
    else:
        logger.error("测试邮件发送失败。")

