# commands/trust_command.py
# 信任群组管理命令

from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from core.trust_manager import trust_manager

async def handle_trust_command(context: BotContext, args: list, user_id: str, group_id: str, nickname: str, **kwargs) -> str:
    """信任群组管理命令处理函数"""
    
    # 只允许Root用户使用此命令
    root_user_id = str(context.get_config_value("Root_user", ""))
    if user_id != root_user_id:
        return "None"
    
    if len(args) < 2:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 参数不足\n用法: /trust add/rm <群号>")
        await builder.send()
        return "None"
    
    action = args[0].lower()
    target_group = args[1]
    
    # 支持使用"this"关键字代表当前群组
    if target_group.lower() == "this":
        target_group = str(group_id)
    
    if action == "add":
        # 添加信任群组
        if trust_manager.add_trusted_group(target_group):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f" ✅ 已将群组 {target_group} 添加到信任列表")
            await builder.send()
            return "None"
        else:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f" ⚠️ 群组 {target_group} 已在信任列表中")
            await builder.send()
            return "None"
    
    elif action == "rm":
        # 移除信任群组
        if trust_manager.remove_trusted_group(target_group):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f" ✅ 已将群组 {target_group} 从信任列表移除")
            await builder.send()
            return "None"
        else:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f" ⚠️ 群组 {target_group} 不在信任列表中")
            await builder.send()
            return "None"
    
    else:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(" ❌ 无效的操作\n用法: /trust add/rm <群号>")
        await builder.send()
        return "None"