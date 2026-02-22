# handlers/private_handler.py
# 处理私聊消息

from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.message_utils import parse_message
from utils.message_sender import CommandResponse, MessageBuilder

logger = get_logger("PrivateHandler")

async def handle_private_message(context: BotContext, event: dict):
    """处理私聊消息事件。"""
    # 检查是否应该处理该消息（基于当前活跃账号）
    if not context.should_handle_message(event):
        return

    user_id = str(event.get('user_id', ''))
    raw_message = event.get('message', '')
    original_message = parse_message(raw_message).strip()
    
    # 只有Root用户可以执行私聊命令
    if user_id != str(context.get_config_value("Root_user", "")):
        logger.warning(f"非Root用户 {user_id} 尝试发送私聊指令，已忽略")
        return

    logger.info(f"收到Root用户的私聊命令: {original_message} 来自用户: {user_id}")

    try:
        if original_message.startswith('/bad'):
            from commands.bad_command import handle_bad_command
            result = await handle_bad_command(original_message, user_id, context)
        else:
            result = "❌ 私聊仅支持 /bad 命令。"

        if result is not None:
            # 处理CommandResponse对象
            if isinstance(result, CommandResponse):
                if result.type == "builder" and isinstance(result.data, MessageBuilder):
                    # 确保MessageBuilder有正确的用户ID和context
                    result.data.set_user_id(user_id)
                    result.data.set_badword_bypass(True, "Root用户命令响应", user_id)
                    await result.data.send()
                    logger.info(f"已发送私聊命令回复到用户: {user_id}")
                elif result.type == "text":
                    # 使用MessageBuilder发送文本响应
                    builder = MessageBuilder(context)
                    builder.set_user_id(user_id)
                    builder.add_text(result.data)
                    builder.set_badword_bypass(True, "Root用户命令响应", user_id)
                    await builder.send()
                    logger.info(f"已发送私聊命令回复: {result.data} 到用户: {user_id}")
                else:
                    # 其他类型的响应，直接发送默认文本
                    builder = MessageBuilder(context)
                    builder.set_user_id(user_id)
                    builder.add_text("✅ 操作已完成")
                    builder.set_badword_bypass(True, "Root用户命令响应", user_id)
                    await builder.send()
                    logger.info(f"已发送私聊命令回复到用户: {user_id}")
            else:
                # 非CommandResponse对象，直接发送
                builder = MessageBuilder(context)
                builder.set_user_id(user_id)
                builder.add_text(result)
                builder.set_badword_bypass(True, "Root用户命令响应", user_id)
                await builder.send()
                logger.info(f"已发送私聊命令回复: {result} 到用户: {user_id}")
    except Exception as e:
        logger.error(f"处理私聊命令 {original_message} 时发生异常: {e}", exc_info=True)
        error_msg = f"🛑 处理私聊命令时发生错误: {str(e)}"
        if context.websocket and not context.websocket.closed:
            builder = MessageBuilder(context)
            builder.set_user_id(user_id)
            builder.add_text(error_msg)
            builder.set_badword_bypass(True, "错误消息通知", user_id)
            await builder.send()
            logger.info(f"已发送私聊错误消息到用户: {user_id}")