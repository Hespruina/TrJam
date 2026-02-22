# commands/help_command/help_sender.py
# 负责发送帮助信息

import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder
from utils.task_utils import create_monitored_task
from commands.help_command.help_data import generate_help_groups

logger = get_logger("HelpCommandSender")

async def process_help_request(context: BotContext, user_id: str, group_id: str, server_name: str, group_id_str: str, processing_message_id: str = None, sender_role: str = None) -> None:
    """在后台处理帮助请求"""
    # 检查群组是否配置
    is_configured = False
    if server_name and context.config.get("servers", {}).get(server_name, {}).get("groups", {}).get(group_id_str):
        is_configured = True
        
    logger.debug(f"处理help命令，用户ID: {user_id}，群ID: {group_id}，是否已配置: {is_configured}，用户角色: {sender_role}")
    
    try:
        # 使用fakemsg格式发送命令列表
        await send_help_as_fakemsg(context, user_id, group_id, is_configured, sender_role=sender_role)
        
        # 撤回处理中提示消息
        if processing_message_id:
            await recall_processing_message_by_id(context, processing_message_id)
        else:
            await try_recall_processing_message(context, user_id, group_id)
            
    except Exception as e:
        logger.error(f"处理帮助命令时发生异常: {e}")
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"\n❌ 处理帮助命令时发生异常: {str(e)}")
        await error_builder.send()
        
        # 撤回处理中提示消息
        if processing_message_id:
            await recall_processing_message_by_id(context, processing_message_id)
        else:
            await try_recall_processing_message(context, user_id, group_id)


async def try_recall_processing_message(context: BotContext, user_id: str, group_id: str) -> None:
    """尝试撤回处理中提示消息"""
    try:
        if hasattr(context, '_processing_messages'):
            message_key = f"help_{user_id}_{group_id}"
            if message_key in context._processing_messages:
                message_id = context._processing_messages[message_key]
                # 调用API撤回消息
                await recall_processing_message_by_id(context, message_id)
    except Exception as e:
        logger.warning(f"撤回处理中提示消息时发生异常: {e}")


async def recall_processing_message_by_id(context: BotContext, message_id: str) -> None:
    """根据消息ID撤回处理中提示消息"""
    try:
        # 从存储中移除已撤回的消息ID
        message_keys_to_remove = []
        if hasattr(context, '_processing_messages'):
            for key, value in context._processing_messages.items():
                if value == message_id:
                    message_keys_to_remove.append(key)
        
        for key in message_keys_to_remove:
            del context._processing_messages[key]
        
        # 调用API撤回消息
        from utils.api_utils import call_onebot_api
        result = await call_onebot_api(
            context=context,
            action="delete_msg",
            params={"message_id": message_id}
        )
        
        if not (result and result.get("success")):
            logger.warning(f"撤回处理中提示消息失败: {result}")
    except Exception as e:
        logger.warning(f"撤回处理中提示消息时发生异常: {e}")


async def send_help_as_fakemsg(context: BotContext, user_id: str, group_id: str, is_configured: bool, sender_role: str = None) -> None:
    """使用fakemsg格式发送帮助信息，每个命令作为单独的消息节点"""
    logger.info(f"开始处理fakemsg格式的帮助请求，用户ID: {user_id}，群ID: {group_id}")
    
    # 生成帮助组数据（权限检查已在generate_help_groups内部处理）
    help_groups, permission_blocked_count, blacklist_blocked_count = await generate_help_groups(context, user_id, group_id, is_configured, False, sender_role=sender_role)
    
    # 创建消息节点列表
    message_nodes = []
    
    # 添加标题节点和屏蔽统计信息
    title_text = '📚 ZHRrobot 功能帮助信息'
    # 添加屏蔽统计信息
    if permission_blocked_count > 0 or blacklist_blocked_count > 0:
        stats_text = '\n'
        if permission_blocked_count > 0:
            stats_text += f'🔒 因权限不足屏蔽 {permission_blocked_count} 个命令\n'
        if blacklist_blocked_count > 0:
            stats_text += f'⛔ 因群聊黑名单屏蔽 {blacklist_blocked_count} 个命令\n'
        title_text += stats_text
    
    title_node = {
        'type': 'node',
        'data': {
            'user_id': str(context.config.get('Root_user', '10000')),  # 使用Root用户ID或默认值
            'nickname': 'ZHRrobot 帮助系统',
            'content': [{'type': 'text', 'data': {'text': title_text}}]
        }
    }
    message_nodes.append(title_node)
    
    # 添加命令分类和命令
    for group in help_groups:
        group_name = group.get('group', '未分类')
        commands = group.get('list', [])
        
        # 添加分类节点
        category_node = {
            'type': 'node',
            'data': {
                'user_id': str(context.config.get('Root_user', '10000')),
                'nickname': 'ZHRrobot 帮助系统',
                'content': [{'type': 'text', 'data': {'text': f'\n{group_name}\n------------------------'}}]
            }
        }
        message_nodes.append(category_node)
        
        # 为每个命令创建一个节点
        for cmd_info in commands:
            title = cmd_info.get('title', '')
            eg = cmd_info.get('eg', '')
            desc = cmd_info.get('desc', '')
            disabled = cmd_info.get('disabled', False)
            
            # 构建命令消息内容，移除末尾的换行
            cmd_text = f"命令: {title}\n"
            cmd_text += f"格式: {eg}\n"
            cmd_text += f"描述: {desc}"
            if disabled:
                cmd_text += " 状态: ⚠️ 已禁用"
            
            cmd_node = {
                'type': 'node',
                'data': {
                    'user_id': str(context.config.get('Root_user', '10000')),
                    'nickname': 'ZHRrobot 帮助系统',
                    'content': [{'type': 'text', 'data': {'text': cmd_text}}]
                }
            }
            message_nodes.append(cmd_node)
    
    # 添加结束节点
    end_node = {
        'type': 'node',
        'data': {
            'user_id': str(context.config.get('Root_user', '10000')),
            'nickname': 'ZHRrobot 帮助系统',
            'content': [{'type': 'text', 'data': {'text': '📌 提示：在命令前加上/即可使用对应功能'}}]
        }
    }
    message_nodes.append(end_node)
    
    # 使用onebot API发送转发消息
    from utils.api_utils import call_onebot_api
    
    payload = {
        'group_id': group_id,
        'messages': message_nodes
    }
    
    try:
        logger.info(f"执行伪造消息API调用：send_group_forward_msg，群号：{group_id}")
        logger.debug(f"请求参数：{payload}")
        
        # 执行onebot API请求
        result = await call_onebot_api(
            context=context,
            action='send_group_forward_msg',
            params=payload
        )
        
        if result is None:
            logger.error("API请求失败，未获取到响应")
        elif not result.get('success'):
            error_msg = result.get('error', '未知错误')
            logger.error(f"API调用失败：{error_msg}")
        else:
            logger.info(f"成功发送帮助信息，共 {len(message_nodes)} 个消息节点")
            
    except Exception as e:
        logger.error(f"发送帮助信息时发生异常: {str(e)}")
        # 如果fakemsg发送失败，回退到简单文本格式
        from commands.help_command.help_formatter import get_help_info
        help_text = get_help_info(context, user_id, group_id, is_configured)
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"\n{help_text}")
        await builder.send()