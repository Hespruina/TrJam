# commands/bad_command.py
# 重构后的敏感词管理命令，从主文件中独立出来

import os
from datetime import datetime
from logger_config import get_logger
from core.bot_context import BotContext
# 从独立的管理器导入，解决循环导入
from core.sensitive_word_manager import sensitive_words, sensitive_trigger_log, MAX_LOG_ENTRIES, add_sensitive_word, remove_sensitive_word, clear_sensitive_trigger_log
# 导入权限检查
from commands.permission_manager import check_permission
from utils.message_sender import MessageBuilder, CommandResponse

logger = get_logger("BadCommand")

async def handle_bad_command(message: str, user_id: str, context: BotContext = None) -> CommandResponse:
    """处理Root用户的私聊 /bad 命令，用于管理全局敏感词和查看日志。"""
    # 创建响应构建器
    builder = MessageBuilder(context)
    builder.set_user_id(user_id)
    
    # 权限检查
    if context:
        # 由于这是全局敏感词管理，不绑定特定群组，所以传入一个特殊值"global"作为group_id
        # 实际会检查是否为Root用户
        user_level = check_permission(context, user_id, "global")
        if user_level < 2:
            logger.warning(f"无权限用户 {user_id} 尝试使用 /bad 命令")
            builder.add_text("⚠️ 需要Root权限")
            return CommandResponse.builder(builder)
    msg_parts = message.strip().split(maxsplit=2)
    if len(msg_parts) < 2:
        builder.add_text("❌ 参数错误。支持: /bad add <词>, /bad rm <词>, /bad log, /bad clear")
        return CommandResponse.builder(builder)

    command = msg_parts[0].lower()
    sub_command = msg_parts[1].lower()

    if command != '/bad':
        builder.add_text("❌ 无效命令。私聊仅支持 /bad。")
        return CommandResponse.builder(builder)

    try:
        if sub_command == 'add':
            if len(msg_parts) < 3:
                builder.add_text("❌ 参数错误。格式: /bad add <词>")
                return CommandResponse.builder(builder)
            target_word = msg_parts[2].strip()
            if not target_word:
                builder.add_text("❌ 请输入要操作的敏感词。")
                return CommandResponse.builder(builder)
            # 使用管理器函数
            if not add_sensitive_word(target_word):
                builder.add_text(f"⚠️ 敏感词 '{target_word}' 已存在。")
                return CommandResponse.builder(builder)
            logger.info(f"Root用户 {user_id} 成功添加敏感词: {target_word}")
            builder.add_text(f"✅ 已添加敏感词: {target_word}")
            return CommandResponse.builder(builder)

        elif sub_command == 'rm':
            if len(msg_parts) < 3:
                builder.add_text("❌ 参数错误。格式: /bad rm <词>")
                return CommandResponse.builder(builder)
            target_word = msg_parts[2].strip()
            if not target_word:
                builder.add_text("❌ 请输入要操作的敏感词。")
                return CommandResponse.builder(builder)
            # 使用管理器函数
            if not remove_sensitive_word(target_word):
                builder.add_text(f"⚠️ 未找到敏感词 '{target_word}'。")
                return CommandResponse.builder(builder)
            logger.info(f"Root用户 {user_id} 成功删除敏感词: {target_word}")
            builder.add_text(f"✅ 已删除敏感词: {target_word}")
            return CommandResponse.builder(builder)

        elif sub_command == 'log':
            if not sensitive_trigger_log:
                builder.add_text("✅ 敏感词触发日志为空。")
                return CommandResponse.builder(builder)
            log_messages = ["📋 **最近的敏感词触发记录**:"]
            for i, entry in enumerate(sensitive_trigger_log, 1):
                dt = datetime.fromtimestamp(entry['timestamp'])
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                log_messages.append(
                    f"{i}. [{time_str}] 群{entry['group_id']} | 用户{entry['user_id']} | "
                    f"敏感词: `{entry['word']}` | 原始消息: `{entry['message']}`"
                )
            builder.add_text("\n".join(log_messages))
            return CommandResponse.builder(builder)

        elif sub_command == 'clear':
            # 使用管理器函数
            clear_sensitive_trigger_log()
            logger.info(f"Root用户 {user_id} 已清空敏感词触发日志")
            builder.add_text("✅ 已清空敏感词触发日志。")
            return CommandResponse.builder(builder)

        else:
            builder.add_text("❌ 无效子命令。支持: add, rm, log, clear")
            return CommandResponse.builder(builder)

    except Exception as e:
        logger.error(f"处理 /bad 命令时发生异常: {e}")
        builder.add_text(f"🛑 操作失败: {str(e)}")
        return CommandResponse.builder(builder)