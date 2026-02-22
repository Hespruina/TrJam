# commands/whoami_command.py
# 处理 /whoami 命令，查询用户权限级别

from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender.message_builder import MessageBuilder

logger = get_logger("WhoAmICommand")

async def handle_whoami_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> int:
    """处理 /whoami 命令，查询用户权限级别
    
    Returns:
        int: 0 表示消息处理流程正常完成，1 表示消息处理过程中出现错误
    """
    from commands.permission_manager import check_permission
    
    try:
        # 获取用户角色信息
        sender_role = kwargs.get('sender_role')
        
        # 检查用户权限级别
        permission_level = check_permission(context, user_id, group_id, sender_role)
        
        # 使用MessageBuilder构建消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        
        # 添加@用户
        builder.add_at()
        
        # 根据权限级别和角色返回对应信息
        if permission_level == 2:
            if str(user_id) == str(context.get_config_value("Root_user")):
                builder.add_text("👑 您是开发者（Root权限）")
            else:
                builder.add_text("👑 您是超级管理员")
        elif permission_level == 1:
            if sender_role == "owner":
                builder.add_text("🔑 您是群主")
            elif sender_role == "admin":
                builder.add_text("🔑 您是群管理员")
            else:
                # 从配置文件中获得的管理员权限
                builder.add_text("🔑 您是管理员")
        else:
            # 检查是否为群主或群管理员（通过WebSocket消息中的sender.role字段）
            if sender_role == "owner":
                builder.add_text("🔑 您是群主")
            elif sender_role == "admin":
                builder.add_text("🔑 您是群管理员")
            else:
                builder.add_text("👤 您是普通用户")
        
        # 发送消息
        await builder.send()
        
        # 返回0表示消息处理成功
        return 0
    except Exception as e:
        logger.error(f"处理whoami命令时发生异常: {e}")
        
        # 发送错误消息
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"处理whoami命令时发生错误")
        await error_builder.send()
        
        # 返回1表示消息处理过程中出现错误
        return 1