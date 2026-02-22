# commands/report_command.py
# 处理 /report 命令

import json
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder

logger = get_logger("ReportCommand")

async def handle_report_command(context: BotContext, args: list, user_id: str, group_id: str, nickname: str, **kwargs) -> str:
    """处理 /report 命令。"""
    if not args:
        return "❌ 请输入反馈内容"

    report_content = ' '.join(args)
    report_group_id = context.get_config_value("report_group")
    if not report_group_id:
        return "❌ 管理员未配置接收反馈的群聊，请联系管理员设置"

    feedback_msg = f"{nickname}（{user_id}）发送反馈\n{report_content}"
    try:
        if context.websocket and not context.websocket.closed:
            # 使用统一的消息发送接口
            builder = MessageBuilder(context)
            builder.set_group_id(report_group_id)
            builder.add_text(feedback_msg)
            await builder.send()
            logger.info(f"已将反馈转发到群 {report_group_id}")
            return "✅ 反馈已提交，感谢你的建议！"
        else:
            logger.error("WebSocket连接无效，无法发送反馈")
            return "⚠️ 机器人连接异常，无法提交反馈"
    except Exception as e:
        logger.error(f"发送反馈时发生异常: {e}")
        return f"🛑 提交反馈时发生错误: {e}"