# commands/debug_command.py
# 实现 /debug 命令，用于调试API调用

import json
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api

logger = get_logger("DebugCommand")

# 存储命令执行状态的全局字典
# key: (user_id, group_id) 元组
# value: dict 包含当前状态和已输入的参数
DEBUG_SESSIONS = {}

# 会话状态
class DebugSessionState:
    WAITING_FOR_ENDPOINT = 1  # 等待用户输入API端点
    WAITING_FOR_PAYLOAD = 2   # 等待用户输入负载内容

async def handle_debug_command(context: BotContext, args: list, user_id: str, group_id: str, server_name: str, user_level: int, **kwargs) -> str:
    """
    处理 /debug 命令，用于调试API调用
    :param context: 机器人上下文，包含配置和WebSocket
    :param args: 命令参数列表
    :param user_id: 触发命令的用户QQ号
    :param group_id: 触发命令的群号
    :param server_name: 当前服务器名称
    :param user_level: 用户权限级别
    :param kwargs: 其他可能的参数
    :return: 要发送给用户的回复文本
    """
    # 检查是否为Root用户
    if user_level < 2:
        return "⚠️ 需要Root权限"
    
    # 如果没有参数，显示帮助信息
    if not args:
        return "❓ 调试命令使用方法：\n"\
               "/debug api onebot - 开始调试onebot API调用"
    
    # 处理子命令
    subcommand = args[0].lower()
    
    if subcommand == 'api':
        # 处理API调试子命令
        return await _handle_api_debug(context, args[1:], user_id, group_id)
    elif subcommand == 'input':
        # 处理用户输入子命令
        return await _handle_debug_input(context, args[1:], user_id, group_id)
    else:
        return f"❌ 未知的调试子命令：{subcommand}"

async def _handle_api_debug(context: BotContext, sub_args: list, user_id: str, group_id: str) -> str:
    """处理API调试子命令"""
    if not sub_args:
        return "❓ 请指定API类型：\n"\
               "/debug api onebot - 调试onebot API"
    
    api_type = sub_args[0].lower()
    if api_type != 'onebot':
        return f"❌ 不支持的API类型：{api_type}\n目前仅支持 'onebot'"
    
    # 检查onebot API配置
    onebot_api_base = context.get_config_value('onebot_api_base')
    if not onebot_api_base:
        return "❌ onebot API基础地址未配置"
    
    # 初始化调试会话
    session_key = (user_id, group_id)
    DEBUG_SESSIONS[session_key] = {
        'state': DebugSessionState.WAITING_FOR_ENDPOINT,
        'api_type': api_type,
        'context': context,  # 保存context供后续调用使用
        'endpoint': None,
        'payload': None
    }
    
    return f"🔍 开始调试 {api_type} API，当前API基础地址：{onebot_api_base}\n"\
           "请使用以下命令输入API端点：\n"\
           "/debug input <端点路径>\n例如：/debug input set_essence_msg"

async def _handle_debug_input(context: BotContext, sub_args: list, user_id: str, group_id: str) -> str:
    """处理用户输入的调试参数"""
    session_key = (user_id, group_id)
    
    # 检查是否有活跃的调试会话
    if session_key not in DEBUG_SESSIONS:
        return "❌ 没有活跃的调试会话，请先使用 /debug api onebot 开始"
    
    session = DEBUG_SESSIONS[session_key]
    
    # 根据当前状态处理输入
    if session['state'] == DebugSessionState.WAITING_FOR_ENDPOINT:
        # 处理API端点输入
        if not sub_args:
            return "❌ 请输入有效的API端点路径"
        
        endpoint = sub_args[0]
        session['endpoint'] = endpoint
        session['state'] = DebugSessionState.WAITING_FOR_PAYLOAD
        
        return f"✅ 已设置API端点：{endpoint}\n"\
               "请使用以下命令输入JSON格式的负载内容：\n"\
               "/debug input <JSON负载>\n例如：/debug input { \"message_id\": 0 }"
    
    elif session['state'] == DebugSessionState.WAITING_FOR_PAYLOAD:
        # 处理负载内容输入
        if not sub_args:
            return "❌ 请输入有效的JSON负载内容"
        
        # 尝试解析JSON负载
        try:
            # 合并所有参数为一个字符串，处理可能的空格分隔
            payload_str = ' '.join(sub_args)
            # 尝试解析JSON
            payload = json.loads(payload_str)
            
            # 保存负载并执行API调用
            session['payload'] = payload
            result = await _execute_api_call(session)
            
            # 清除会话状态
            del DEBUG_SESSIONS[session_key]
            
            return result
        except json.JSONDecodeError:
            return "❌ JSON格式错误，请检查输入的负载内容"
        except Exception as e:
            log_exception(logger, "处理调试输入时发生异常", e)
            # 发生异常时也清除会话
            if session_key in DEBUG_SESSIONS:
                del DEBUG_SESSIONS[session_key]
            return f"🛑 处理请求时发生错误：{str(e)}"

async def _execute_api_call(session: dict) -> str:
    """执行API调用并返回结果"""
    context = session['context']
    endpoint = session['endpoint']
    payload = session['payload']
    
    try:
        logger.info(f"执行调试onebot API调用：{endpoint}")
        logger.debug(f"负载内容：{payload}")
        
        # 执行onebot API请求
        result = await call_onebot_api(
            context=context,
            action=endpoint,
            params=payload
        )
        
        if result is None:
            return "❌ API请求失败，未获取到响应"
        
        # 直接使用原始返回的JSON数据
        response_str = str(result)
        
        # 检查消息长度，避免超过QQ消息限制
        if len(response_str) > 4000:
            response_str = response_str[:3900] + "\n...\n[消息过长，已截断]"
        
        return f"✅ API调用成功！\n"\
               f"请求端点：{endpoint}\n"\
               f"请求参数：{str(payload)}\n"\
               f"响应结果：\n{response_str}"
    except Exception as e:
        log_exception(logger, "执行API调用时发生异常", e)
        return f"🛑 API调用失败：{str(e)}"