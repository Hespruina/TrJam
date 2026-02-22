# commands/chat_command.py
# 处理/chat命令，用于管理MaiBot的黑白名单

import requests
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder

logger = get_logger("ChatCommand")

async def chat_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> int:
    """处理/chat命令
    
    用法：
    /chat enable - 将当前群加入白名单
    /chat disable - 将当前群移除白名单
    
    Args:
        context: BotContext对象
        args: 命令参数列表
        user_id: 发送命令的用户ID
        group_id: 命令发送的群组ID
    
    Returns:
        int: 0表示成功，1表示失败
    """
    if not args:
        return await handle_status(context, group_id, user_id)
    
    subcommand = args[0].lower()
    
    if subcommand == "enable":
        return await handle_enable(context, group_id, user_id)
    elif subcommand == "disable":
        return await handle_disable(context, group_id, user_id)
    else:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text("未知的子命令，请使用：enable/disable")
        await builder.send()
        return 1

def get_api_base_url(context: BotContext) -> str:
    """获取HTTP API基础地址
    
    Args:
        context: BotContext对象
    
    Returns:
        str: HTTP API基础地址
    """
    return context.config.get("maibot_adapter", {}).get("api_base_url", "http://localhost:3012/api")

def get_group_list_from_api(context: BotContext) -> dict:
    """从API获取群聊列表
    
    Args:
        context: BotContext对象
    
    Returns:
        dict: API返回的数据
    """
    base_url = get_api_base_url(context)
    url = f"{base_url}?do=get_group_list"
    
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error("连接失败: 请确保 adapter 已启动且 HTTP API 服务器正在运行")
        return {"success": False, "error": "连接失败"}
    except Exception as e:
        logger.error(f"请求出错: {e}")
        return {"success": False, "error": str(e)}

def update_group_list_via_api(context: BotContext, group_id: str, action: str) -> dict:
    """通过API更新群聊列表
    
    Args:
        context: BotContext对象
        group_id: 群组ID
        action: 操作类型，"add" 或 "rm"
    
    Returns:
        dict: API返回的数据
    """
    base_url = get_api_base_url(context)
    url = f"{base_url}?do=update_group_list&id={group_id}&action={action}"
    
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error("连接失败: 请确保 adapter 已启动且 HTTP API 服务器正在运行")
        return {"success": False, "error": "连接失败"}
    except Exception as e:
        logger.error(f"请求出错: {e}")
        return {"success": False, "error": str(e)}

async def handle_status(context: BotContext, group_id: str, user_id: str) -> int:
    """处理/chat命令（无参数），显示当前状态
    
    Args:
        context: BotContext对象
        group_id: 群组ID
        user_id: 发送命令的用户ID
    
    Returns:
        int: 0表示成功，1表示失败
    """
    result = get_group_list_from_api(context)
    
    if not result.get("success"):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(f"获取状态失败: {result.get('error', '未知错误')}")
        await builder.send()
        return 1
    
    data = result.get("data", {})
    group_list_type = data.get("group_list_type", "whitelist")
    group_list = data.get("group_list", [])
    
    if group_list_type == "whitelist":
        status = "已启用" if group_id in group_list else "已禁用"
    else:
        status = "已禁用" if group_id in group_list else "已启用"
    
    builder = MessageBuilder(context)
    builder.set_group_id(group_id)
    builder.add_at(user_id)
    builder.add_text(f"当前群 {group_id} 的AI聊天状态：{status}")
    await builder.send()
    return 0

async def handle_enable(context: BotContext, group_id: str, user_id: str) -> int:
    """处理/chat enable命令
    
    Args:
        context: BotContext对象
        group_id: 群组ID
        user_id: 发送命令的用户ID
    
    Returns:
        int: 0表示成功，1表示失败
    """
    result = get_group_list_from_api(context)
    
    if not result.get("success"):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(f"获取群聊列表失败: {result.get('error', '未知错误')}")
        await builder.send()
        return 1
    
    data = result.get("data", {})
    group_list_type = data.get("group_list_type", "whitelist")
    
    if group_list_type == "whitelist":
        action = "add"
        message = f"群 {group_id} 已成功加入AI聊天白名单"
    else:
        action = "rm"
        message = f"群 {group_id} 已成功从AI聊天黑名单中移除"
    
    update_result = update_group_list_via_api(context, group_id, action)
    
    if update_result.get("success"):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(message)
        await builder.send()
        return 0
    else:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(f"操作失败: {update_result.get('error', '未知错误')}")
        await builder.send()
        return 1

async def handle_disable(context: BotContext, group_id: str, user_id: str) -> int:
    """处理/chat disable命令
    
    Args:
        context: BotContext对象
        group_id: 群组ID
        user_id: 发送命令的用户ID
    
    Returns:
        int: 0表示成功，1表示失败
    """
    result = get_group_list_from_api(context)
    
    if not result.get("success"):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(f"获取群聊列表失败: {result.get('error', '未知错误')}")
        await builder.send()
        return 1
    
    data = result.get("data", {})
    group_list_type = data.get("group_list_type", "whitelist")
    
    if group_list_type == "whitelist":
        action = "rm"
        message = f"群 {group_id} 已成功从AI聊天白名单中移除"
    else:
        action = "add"
        message = f"群 {group_id} 已成功加入AI聊天黑名单"
    
    update_result = update_group_list_via_api(context, group_id, action)
    
    if update_result.get("success"):
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(message)
        await builder.send()
        return 0
    else:
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(f"操作失败: {update_result.get('error', '未知错误')}")
        await builder.send()
        return 1
