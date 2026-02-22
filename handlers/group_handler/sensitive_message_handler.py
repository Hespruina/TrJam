# handlers/group_handler/sensitive_message_handler.py
# 处理敏感消息

import json
import time
from datetime import datetime
from logger_config import get_logger
from core.bot_context import BotContext
from core.sensitive_word_manager import log_sensitive_trigger
from utils.message_sender import MessageBuilder
from utils.api_utils import call_onebot_api

logger = get_logger("SensitiveMessageHandler")

async def handle_sensitive_message(context: BotContext, event: dict, group_id, user_id, original_message, sensitive_word, sensitive_reason):
    """处理包含敏感词的消息。"""
    logger.info(f"检测到敏感词，群: {group_id}，用户: {user_id}，敏感词: {sensitive_word}，原因: {sensitive_reason}")
    # 使用管理器记录日志
    log_sensitive_trigger(original_message, sensitive_word, group_id, user_id)
    logger.debug(f"已记录敏感词触发日志")

    # 检查是否启用了敏感词自动撤回功能
    group_config = context.get_group_config(str(group_id))
    sensitive_word_recall_enabled = group_config.get("sensitive_word_recall_enabled", False) if group_config else False
    
    if not sensitive_word_recall_enabled:
        logger.debug(f"敏感词自动撤回功能未启用，群: {group_id}")
        return

    # 获取群组配置
    is_configured_group = group_config is not None

    if is_configured_group:
        try:
            message_id = event.get('message_id')
            if message_id:
                recall_result = await call_onebot_api(
                    context, 'delete_msg', {'message_id': message_id}
                )
                # 检查API调用是否成功以及业务处理是否成功
                if recall_result and recall_result.get('success') and recall_result.get('data', {}).get('status') == 'ok':
                    logger.info(f"已成功撤回敏感消息，群: {group_id}，用户: {user_id}")
                    # 构建消息并发送
                    builder = MessageBuilder(context)
                    builder.set_group_id(str(group_id))
                    builder.set_user_id(user_id)
                    builder.add_at()
                    builder.add_text(f" 含有{sensitive_reason}内容，已撤回")
                    await builder.send()

                    # 推送报告到指定群（已撤回）
                    await send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, True)
                else:
                    # 提供更详细的失败原因
                    failure_reason = "未知原因"
                    if recall_result:
                        if not recall_result.get('success'):
                            failure_reason = recall_result.get('error', 'API调用失败')
                        else:
                            failure_reason = f"业务状态非成功: {recall_result.get('data', {}).get('status', '未知')}"
                    logger.error(f"撤回敏感消息失败，群: {group_id}，用户: {user_id}，原因: {failure_reason}")
                    # 推送报告到指定群（未撤回）
                    await send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, False)
            else:
                logger.error(f"无法获取消息ID，无法撤回敏感消息，群: {group_id}，用户: {user_id}")
                # 推送报告到指定群（未撤回）
                await send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, False)
        except Exception as e:
            logger.error(f"处理敏感消息时发生异常: {e}")
            # 推送报告到指定群（处理异常，视为未撤回）
            await send_sensitive_report(context, group_id, user_id, original_message, sensitive_word, False)
    else:
        logger.info(f"未配置群聊中检测到敏感词，不执行撤回也不发送回复，群: {group_id}，用户: {user_id}")

async def send_sensitive_report(context, group_id, user_id, raw_message, sensitive_word, recalled=False):
    """
    发送敏感词报告到配置的目标
    
    Args:
        context: BotContext对象
        group_id: 群组ID
        user_id: 用户ID
        raw_message: 原始消息内容
        sensitive_word: 检测到的敏感词
        recalled: 是否已撤回（默认False）
    """
    logger.info(f"准备发送敏感词报告，群ID: {group_id}, 用户ID: {user_id}")
    
    # 使用统一的报告处理器
    from utils.sensitive_word_reporter import SensitiveWordReporter
    try:
        success = await SensitiveWordReporter.send_report(
            context, group_id, user_id, raw_message, sensitive_word, recalled
        )
        if success:
            logger.info("敏感词报告发送成功")
        else:
            logger.warning("敏感词报告发送失败")
    except Exception as e:
        logger.error(f"发送敏感词报告时发生异常: {e}")
