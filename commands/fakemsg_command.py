# commands/fakemsg_command.py
# 实现 /fakemsg 命令，用于构建和发送伪造的群聊转发消息

import re
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api

logger = get_logger("FakeMsgCommand")

async def handle_fakemsg_command(context: BotContext, args: list, user_id: str, group_id: str, server_name: str = None, **kwargs) -> str:
    """
    处理 /fakemsg 命令，用于构建和发送伪造的群聊转发消息
    :param context: 机器人上下文，包含配置和WebSocket
    :param args: 命令参数列表
    :param user_id: 触发命令的用户QQ号
    :param group_id: 触发命令的群号
    :param server_name: 当前服务器名称
    :param kwargs: 其他可能的参数
    :return: 要发送给用户的回复文本
    """
    # 检查用户是否为Root用户
    if str(user_id) != str(context.get_config_value("Root_user")):
        return "⚠️ 该命令仅限Root用户使用"
    
    # 获取原始消息内容
    raw_message = kwargs.get('raw_message', [])
    
    # 处理消息内容，提取消息块
    # 消息格式示例：
    # /fakemsg
    # /fakemsg/
    # 2669171627
    # 苏打不水
    # 晚上好喵
    # /fakemsg/
    # 2669171627
    # 苏打不水
    # 喵喵喵
    
    # 检查是否是纯文本消息
    if not raw_message or not isinstance(raw_message, list):
        return "❌ 请使用正确的消息格式，使用纯文本发送命令"
    
    # 组合所有消息段的文本内容
    full_text = ''
    for segment in raw_message:
        if segment.get('type') == 'text':
            full_text += segment.get('data', {}).get('text', '')
    
    # 分割消息块
    # 首先匹配完整的命令行，然后是消息块
    cmd_pattern = r'^/fakemsg\s*'
    match = re.match(cmd_pattern, full_text)
    if not match:
        return "❌ 无效的命令格式，请以/fakemsg开头"
    
    # 提取命令后的内容
    content_after_cmd = full_text[match.end():].strip()
    
    # 使用/fakemsg/分割消息块
    message_blocks = content_after_cmd.split('/fakemsg/')
    
    # 过滤掉空消息块
    message_blocks = [block.strip() for block in message_blocks if block.strip()]
    
    if not message_blocks:
        return "❌ 未找到有效的消息块，请使用/fakemsg/分隔各个消息块"
    
    # 解析每个消息块
    messages = []
    for block in message_blocks:
        lines = block.split('\n')
        # 过滤掉空行
        lines = [line.strip() for line in lines if line.strip()]
        
        if len(lines) < 3:
            return f"❌ 消息块格式错误，需要至少3行（用户ID、昵称、消息内容）\n错误块：{block}"
        
        # 提取用户ID、昵称和消息内容
        user_id_in_block = lines[0]
        nickname_in_block = lines[1]
        # 剩余的所有行作为消息内容
        message_content = '\n'.join(lines[2:])
        
        # 验证用户ID是否为数字
        if not user_id_in_block.isdigit():
            return f"❌ 用户ID必须是数字：{user_id_in_block}"
        
        # 构建消息节点
        message_node = {
            'type': 'node',
            'data': {
                'user_id': user_id_in_block,
                'nickname': nickname_in_block,
                'content': [{
                    'type': 'text',
                    'data': {
                        'text': message_content
                    }
                }]
            }
        }
        
        messages.append(message_node)
    
    # 确保至少有一个有效的消息节点
    if not messages:
        return "❌ 未解析到有效的消息节点"
    
    # 构建API调用参数
    payload = {
        'group_id': group_id,
        'messages': messages
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
            return "❌ API请求失败，未获取到响应"
        
        if result.get('success'):
            # 成功发送消息
            return f"✅ 伪造消息发送成功！\n发送了 {len(messages)} 条消息节点"
        else:
            # 发送失败
            error_msg = result.get('error', '未知错误')
            return f"❌ API调用失败：{error_msg}"
    except Exception as e:
        log_exception(logger, "发送伪造消息时发生异常", e)
        return f"🛑 发送消息时发生错误：{str(e)}"