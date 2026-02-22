# commands/command_dispatcher/command_executor.py
# 负责命令执行

import asyncio
import re
import os
import json
from logger_config import get_logger
from core.bot_context import BotContext
from utils.user_utils import get_user_nickname
from utils.message_sender import process_command_response, CommandResponse, MessageBuilder

logger = get_logger("CommandExecutor")

async def execute_command(context: BotContext, message: str, user_id: str, group_id: str, nickname: str, **kwargs) -> int:
    """命令执行器，根据命令名调用对应的处理器。
    
    Returns:
        int: 0 表示消息处理流程正常完成，1 表示消息处理过程中出现错误
    """
    logger.debug(f"开始处理命令，消息: {message}，用户: {user_id}，群: {group_id}，昵称: {nickname}")

    # 输入验证：检查消息长度和格式
    if len(message) > 1000:
        logger.warning(f"命令长度超过限制，用户: {user_id}，消息长度: {len(message)}")
        return 0
    


    from commands.bancommand_command import is_command_banned
    msg_parts = message.strip().split()
    if not msg_parts:
        # 移除未知指令提示，不返回任何内容
        return 0

    raw_command = msg_parts[0]
    command = raw_command.lstrip('/')

    # 处理中文命令映射
    from commands.command_dispatcher.command_registry import COMMAND_HANDLERS, CHINESE_COMMAND_MAPPING
    actual_command = command
    if command in CHINESE_COMMAND_MAPPING:
        actual_command = CHINESE_COMMAND_MAPPING[command]
        logger.debug(f"将中文命令 '{command}' 映射到英文命令 '{actual_command}'")

    # 输入验证：检查命令名是否合法
    if not re.match(r'^[a-zA-Z0-9_]+$', actual_command):
        logger.warning(f"非法命令名: {command}，用户: {user_id}")
        return 0

    args = msg_parts[1:]
    
    # 输入验证：过滤危险参数
    safe_args = []
    for arg in args:
        # 移除可能的危险字符
        safe_arg = re.sub(r'[<>&|;`$\\]', '', arg)
        safe_args.append(safe_arg)
    args = safe_args

    # 查找群组配置（只从主程序配置中查找）
    group_id_str = str(group_id)
    server_name = None
    group_config = None
    
    # 只从主程序的配置中查找服务器配置
    servers_config = context.config.get("servers", {})
    for s_name, server in servers_config.items():
        if group_id_str in server.get("groups", {}):
            server_name = s_name
            group_config = server["groups"][group_id_str]
            break

    # 从kwargs中获取用户角色信息
    sender_role = kwargs.get('sender_role')

    # 所有命令都作为全局可用处理
    # 获取命令配置
    cmd_config = context.config["commands"].get(actual_command, {
        "permission": "User",
        "description": "",
        "usage": ""
    })
    
    # 检查权限
    from commands.command_dispatcher.command_authorizer import check_permission
    perm_mapping = {"User": 0, "Admin": 1, "Root": 2}
    required_level = perm_mapping.get(cmd_config["permission"].capitalize(), 0)
    user_level = await check_permission(context, user_id, group_id, sender_role or "member")
    
    if user_level < required_level:
        # 移除权限不足提示，不返回任何内容
        return 0
    
    handler = COMMAND_HANDLERS.get(actual_command)
    if handler:
        try:
            handler_kwargs = {
                'context': context,
                'args': args,
                'user_id': user_id,
                'group_id': group_id,
                'user_level': user_level,  # 添加user_level参数
                'command': actual_command,  # 添加command参数
                'nickname': nickname,
                'raw_message': kwargs.get('raw_message', []),
                'websocket': kwargs.get('websocket') or context.websocket,
                'message_id': kwargs.get('message_id'),  # 添加message_id参数
                'sender_role': sender_role  # 添加sender_role参数
            }
            
            # 如果有群组配置，添加额外参数
            if group_config:
                handler_kwargs['api_base'] = group_config.get("api_base")
                handler_kwargs['server_name'] = server_name
            
            # 传递命令配置
            handler_kwargs['cmd_config'] = cmd_config
            
            # 调用命令处理函数，现在命令处理函数应该返回int值
            result = await handler(**handler_kwargs)
            
            # 如果命令返回None，表示它自己处理了消息发送，这是旧的处理方式
            if result is None:
                return 0
            # 如果结果不是int类型，且不是None，则需要处理这个结果
            elif not isinstance(result, int):
                await process_command_response(context, result, group_id, user_id)
                return 0
            # 如果结果是int类型，则直接返回这个结果
            else:
                return result
        except Exception as e:
            logger.error(f"处理命令 /{actual_command} 时发生异常", exc_info=True)
            # 移除异常提示，不返回任何内容
            return 1
    
    # 尝试调用插件命令
    if hasattr(context, 'plugin_manager'):
        try:
            # 遍历所有已加载的插件
            for plugin_info in context.plugin_manager.list_plugins():
                if plugin_info.status == 'enabled':
                    # 检查插件是否注册了该命令
                    command_handlers = plugin_info.instance.context.list_commands()
                    if actual_command in command_handlers:
                        cmd_info = command_handlers[actual_command]
                        handler = cmd_info.get('handler')
                        if handler:
                            logger.info(f"执行插件 {plugin_info.id} 的命令: {actual_command}")
                            # 调用插件命令处理函数
                            handler_kwargs = {
                                'context': plugin_info.instance.context,
                                'user_id': user_id,
                                'group_id': group_id,
                                'nickname': nickname,
                                'sender_role': sender_role,
                                'args': args,
                                **kwargs
                            }
                            await handler(**handler_kwargs)
                            return 0
        except Exception as e:
            logger.error(f"处理插件命令 /{actual_command} 时发生异常", exc_info=True)
            return 1
    
    # 移除未知命令提示，不返回任何内容
    return 0

