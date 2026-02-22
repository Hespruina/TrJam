# handlers/request_handler.py
# 处理好友和群聊请求事件

import time
import json
from datetime import datetime
import os
import re
from typing import Optional
from logger_config import get_logger, log_exception
from core.bot_context import BotContext
from utils.api_utils import call_onebot_api
from utils.message_sender import MessageBuilder

logger = get_logger("RequestHandler")

async def handle_request_event(context: BotContext, event: dict):
    """处理好友和群聊请求事件。"""
    # 检查是否应该处理该消息（基于当前活跃账号）
    if not context.should_handle_message(event):
        return
        
    # 添加debug级别的详细原始事件日志
    logger.debug(f"收到请求事件的完整数据: {json.dumps(event, ensure_ascii=False)}")
    
    request_type = event.get('request_type')
    logger.debug(f"处理请求事件，类型: {request_type}")

    if request_type == 'friend':
        await _handle_friend_request(context, event)
    elif request_type == 'group':
        await _handle_group_request(context, event)

async def _handle_friend_request(context: BotContext, event: dict):
    """处理好友申请。"""
    user_id = event.get('user_id', '')
    comment = event.get('comment', '无验证信息')
    flag = event.get('flag', '')
    logger.info(f"收到好友申请 - QQ: {user_id}, 验证信息: {comment}")
    
    # 添加debug级别的详细日志
    logger.debug(f"好友申请详细信息 - 用户ID: {user_id}, 验证信息: {comment}, flag: {flag}")

    api_params = {
        "flag": flag,
        "approve": True
    }
    
    logger.debug(f"准备发送同意好友申请的请求: {api_params}")
    
    response = await call_onebot_api(context, 'set_friend_add_request', api_params)
    if response and response.get('success'):
        logger.info(f"已自动同意好友申请: {user_id}")
        logger.debug(f"成功发送同意好友申请的请求")
    else:
        error_msg = response.get('error', '未知错误') if response else '无响应'
        logger.warning(f"同意好友申请失败: {error_msg}")

async def _handle_group_request(context: BotContext, event: dict):
    """处理群聊请求（邀请或加群）。"""
    sub_type = event.get('sub_type')
    group_id = event.get('group_id', '')
    user_id = event.get('user_id', '')
    group_name = event.get('group_name', '未知群')
    flag = event.get('flag', '')
    
    # 添加debug级别的详细日志
    logger.debug(f"群请求详细信息 - 类型: {sub_type}, 用户ID: {user_id}, 群ID: {group_id}, 群名称: {group_name}, flag: {flag}")

    if sub_type == 'invite':
        await _handle_group_invite(context, user_id, group_name, group_id, flag)
    elif sub_type == 'add':
        await _handle_group_add_request(context, user_id, group_name, group_id, flag, event)

async def _handle_group_invite(context: BotContext, user_id: str, group_name: str, group_id: str, flag: str):
    """处理群聊邀请。"""
    logger.info(f"收到群聊邀请 - 邀请人: {user_id}, 群: {group_name}({group_id})")
    
    # 检查邀请人是否在群组黑名单中
    if await _is_user_blacklisted(context, group_id, user_id):
        logger.info(f"邀请人 {user_id} 在群 {group_id} 的黑名单中，拒绝其邀请")
        # 拒绝群邀请
        await _reject_group_invite(context, flag, "邀请人在群黑名单中")
        
        # 向report群发送通知
        report_group_id = context.get_config_value("report_group")
        if report_group_id:
            timestamp = int(time.time())
            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            report_message = [
                {"type": "text", "data": {"text": "【机器人拒绝入群通知】"}},
                {"type": "text", "data": {"text": f"\n时间: {formatted_time}"}},
                {"type": "text", "data": {"text": f"\n邀请人: {user_id}"}},
                {"type": "text", "data": {"text": f"\n群名称: {group_name}"}},
                {"type": "text", "data": {"text": f"\n群号: {group_id}"}},
                {"type": "text", "data": {"text": f"\n原因: 邀请人在群黑名单中"}}
            ]
            
            # 使用MessageBuilder构建并发送消息，避免再次触发敏感词检测
            builder = MessageBuilder(context)
            builder.set_group_id(str(report_group_id))
            builder.set_badword_bypass(True, "管理员敏感词报告", "system")
            for text in report_message:
                builder.add_text(text['data']['text'])
            await builder.send()
            logger.info(f"已向report群 {report_group_id} 发送拒绝入群通知")
        return
    
    api_params = {
        "flag": flag,
        "sub_type": "invite",
        "approve": True
    }
    
    logger.debug(f"准备发送同意群邀请的请求: {api_params}")
    
    response = await call_onebot_api(context, 'set_group_add_request', api_params)
    if response and response.get('success'):
        logger.info(f"已自动同意入群邀请: {group_name}({group_id})")
        logger.debug(f"成功发送同意群邀请的请求")
        
        # 获取邀请人昵称
        from utils.user_utils import get_user_nickname
        inviter_nickname = await get_user_nickname(context, user_id)
        
        # 向report群发送日志
        report_group_id = context.get_config_value("report_group")
        if report_group_id:
            timestamp = int(time.time())
            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            report_message = [
                {"type": "text", "data": {"text": "【机器人被邀请事件】"}},
                {"type": "text", "data": {"text": f"\n时间: {formatted_time}"}},
                {"type": "text", "data": {"text": f"\n邀请人: {inviter_nickname}({user_id})"}},
                {"type": "text", "data": {"text": f"\n群名称: {group_name}"}},
                {"type": "text", "data": {"text": f"\n群号: {group_id}"}},
            ]
            
            # 使用MessageBuilder构建并发送消息，避免再次触发敏感词检测
            builder = MessageBuilder(context)
            builder.set_group_id(str(report_group_id))
            builder.set_badword_bypass(True, "管理员敏感词报告", "system")
            for text in report_message:
                builder.add_text(text['data']['text'])
            await builder.send()
            logger.info(f"已向report群 {report_group_id} 发送入群日志")
        else:
            logger.warning("未配置report群，无法发送入群日志")
    else:
        error_msg = response.get('error', '未知错误') if response else '无响应'
        logger.warning(f"同意入群邀请失败: {error_msg}")

async def _reject_group_invite(context: BotContext, flag: str, reason: str):
    """拒绝群邀请"""
    api_params = {
        "flag": flag,
        "sub_type": "invite",
        "approve": False,
        "reason": reason
    }
    
    logger.debug(f"准备发送拒绝群邀请的请求: {api_params}")
    
    response = await call_onebot_api(context, 'set_group_add_request', api_params)
    if response and response.get('success'):
        logger.info(f"已拒绝群邀请，原因: {reason}")
        logger.debug(f"成功发送拒绝群邀请的请求")
    else:
        error_msg = response.get('error', '未知错误') if response else '无响应'
        logger.warning(f"拒绝群邀请失败: {error_msg}")

async def _handle_group_add_request(context: BotContext, user_id: str, group_name: str, group_id: str, flag: str, event: dict):
    """处理加群申请。"""
    logger.info(f"收到加群申请 - 申请人: {user_id}, 群: {group_name}({group_id})")
    
    # 检查用户是否在黑名单中
    if await _is_user_blacklisted(context, group_id, user_id):
        logger.info(f"用户 {user_id} 在群 {group_id} 的黑名单中，拒绝其加群申请")
        # 拒绝加群申请
        await _reject_group_application(context, flag, "用户在黑名单中")
        
        # 向群内发送通知
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(f"已自动拒绝黑名单用户 {user_id} 的加群申请")
        await builder.send()
        return
    
    # 获取验证信息（问题答案）
    comment = event.get('comment', '')
    logger.info(f"加群验证信息: {comment}")
    
    # 获取申请人信息
    stranger_info = None
    try:
        logger.debug(f"尝试获取申请人 {user_id} 的陌生人信息")
        stranger_info_data = await call_onebot_api(
            context, 'get_stranger_info',
            {'user_id': int(user_id), 'no_cache': False}
        )
        
        logger.debug(f"获取陌生人信息的API响应: {str(stranger_info_data)}")
        
        if stranger_info_data and stranger_info_data.get('success') and stranger_info_data.get('data', {}).get('status') == 'ok':
            stranger_info = stranger_info_data.get('data', {}).get('data')
            logger.debug(f"获取到申请人 {user_id} 的信息: {str(stranger_info)}")
        else:
            logger.warning(f"获取申请人 {user_id} 信息失败或返回错误: {str(stranger_info_data)}")
    except Exception as e:
        log_exception(logger, f"获取申请人 {user_id} 信息时发生异常", e)
        stranger_info = None
    
    # 构建申请人详细信息
    nickname = stranger_info.get('nick', '未知用户') if stranger_info else '未知用户'
    level = stranger_info.get('qqLevel', '未知') if stranger_info else '未知'
    
    # 检查群组是否已配置
    group_config = context.get_group_config(str(group_id))
    is_configured_group = group_config is not None
    
    root_user_id = context.get_config_value("Root_user")
    logger.debug(f"当前配置的Root用户ID: {root_user_id}")
    
    # 如果是ROOT用户，特殊处理
    if root_user_id and str(user_id) == str(root_user_id):
        logger.info(f"ROOT用户 {user_id} 申请加群，无条件通过，不记录成员信息。")
        await _approve_root_user_request(context, user_id, group_name, group_id, flag)
        return

    # 检查是否有自动审批条件
    if group_config and "event_approvals" in group_config:
        await _process_event_approvals(context, user_id, group_name, group_id, flag, group_config["event_approvals"], comment)
        return

    # 如果没有配置event_approvals或群组未配置，发送详细通知消息到群里
    logger.info(f"群 {group_name}({group_id}) 未配置自动审批条件或群组未配置，发送详细通知消息到群里。")
    if context.websocket and not context.websocket.closed:
        notification_msg = f"❕ 检测到 {nickname}({user_id}) 的加群申请，但未配置自动审批条件，请管理员处理。\n"
        notification_msg += f"等级: {level}\n"
        notification_msg += f"验证信息: {comment}"
        
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(notification_msg)
        await builder.send()
        logger.info(f"已发送未配置审批条件的详细通知到群 {group_name}({group_id})")
    else:
        logger.warning(f"WebSocket连接无效，无法发送未配置审批条件通知到群 {group_name}({group_id})")

async def _is_user_blacklisted(context: BotContext, group_id: str, user_id: str) -> bool:
    """检查用户是否在群组黑名单中"""
    # 获取群组配置文件路径
    group_config_path = f"data/group_config/{group_id}.json"
    
    # 读取现有配置
    group_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_config = json.load(f)
                logger.debug(f"读取群组配置: {group_config}")
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")
            return False
    else:
        logger.debug(f"群组配置文件不存在: {group_config_path}")
    
    # 检查是否存在blacklist以及用户是否在其中
    if "blacklist" in group_config:
        logger.debug(f"群组黑名单列表: {group_config['blacklist']}")
        # 确保类型匹配，将user_id转换为字符串进行比较
        if str(user_id) in group_config["blacklist"]:
            logger.info(f"用户 {user_id} 在群组 {group_id} 的黑名单中")
            return True
        else:
            logger.debug(f"用户 {user_id} 不在群组 {group_id} 的黑名单中")
    else:
        logger.debug(f"群组 {group_id} 没有配置黑名单")
    
    return False

async def _reject_group_application(context: BotContext, flag: str, reason: str):
    """拒绝群申请"""
    api_params = {
        "flag": flag,
        "sub_type": "add",
        "approve": False,
        "reason": reason
    }
    
    logger.debug(f"准备发送拒绝加群申请的请求: {api_params}")
    
    response = await call_onebot_api(context, 'set_group_add_request', api_params)
    if response and response.get('success'):
        logger.info(f"已拒绝加群申请，原因: {reason}")
        logger.debug(f"成功发送拒绝加群申请的请求")
    else:
        error_msg = response.get('error', '未知错误') if response else '无响应'
        logger.warning(f"拒绝加群申请失败: {error_msg}")

async def _process_event_approvals(context: BotContext, user_id: str, group_name: str, group_id: str, flag: str, approvals: list, comment: str):
    """根据配置的审批条件处理加群申请。"""
    logger.debug(f"开始处理审批条件: {approvals}")
    
    # 再次检查用户是否在黑名单中（双重保险）
    if await _is_user_blacklisted(context, group_id, user_id):
        logger.info(f"用户 {user_id} 在群 {group_id} 的黑名单中，拒绝其加群申请（在审批处理中）")
        # 拒绝加群申请
        await _reject_group_application(context, flag, "用户在黑名单中")
        
        # 向群内发送通知
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(f"已自动拒绝黑名单用户 {user_id} 的加群申请")
        await builder.send()
        return
    
    # 获取申请人信息
    stranger_info = None
    try:
        logger.debug(f"尝试获取申请人 {user_id} 的陌生人信息")
        stranger_info_data = await call_onebot_api(
            context, 'get_stranger_info',
            {'user_id': int(user_id), 'no_cache': False}
        )
        
        logger.debug(f"获取陌生人信息的API响应: {str(stranger_info_data)}")
        
        if stranger_info_data and stranger_info_data.get('success') and stranger_info_data.get('data', {}).get('status') == 'ok':
            stranger_info = stranger_info_data.get('data', {}).get('data')
            logger.debug(f"获取到申请人 {user_id} 的信息: {str(stranger_info)}")
        else:
            logger.warning(f"获取申请人 {user_id} 信息失败或返回错误: {str(stranger_info_data)}")
    except Exception as e:
        log_exception(logger, f"获取申请人 {user_id} 信息时发生异常", e)
        stranger_info = None

    # 检查是否符合任何审批条件
    approval_matched = False
    matched_conditions = []  # 改为列表以支持多个匹配条件
    
    for i, approval in enumerate(approvals):
        approval_type = approval.get("type")
        approval_value = approval.get("value")
        
        if approval_type == "level" and stranger_info:
            # 检查等级条件
            applicant_level = stranger_info.get('qqLevel', 0)
            try:
                required_level = int(approval_value)
                if applicant_level >= required_level:
                    approval_matched = True
                    matched_conditions.append(f"等级条件: {required_level}")
            except ValueError:
                logger.warning(f"无效的等级值: {approval_value}")
                
        elif approval_type == "answer":
            # 优化的答案验证逻辑
            # 1. 首先尝试提取"问题：.....答案：......."的格式获取验证信息
            # 2. 如果没有找到这种格式，再进行全文匹配
            approval_matched = False
            valid_answers = [ans.strip() for ans in approval_value.split(',') if ans.strip() and ans.strip() != "答案"]
            
            # 格式1：尝试提取"问题：.....答案：......."格式
            if "问题：" in comment and "答案：" in comment:
                # 确保答案在问题之后
                question_pos = comment.find("问题：")
                answer_pos = comment.find("答案：")
                
                if answer_pos > question_pos:
                    # 从"答案："后面提取答案部分
                    answer_start = answer_pos + 3
                    answer = comment[answer_start:].strip()
                    
                    # 检查提取的答案是否包含有效答案
                    for valid_answer in valid_answers:
                        if valid_answer in answer and valid_answer != "答案":
                            approval_matched = True
                            matched_conditions.append(f"答案条件：{valid_answer}")
                            break
            
            # 如果格式1未匹配，尝试整个评论内容匹配
            if not approval_matched:
                for valid_answer in valid_answers:
                    # 避免仅"答案"二字匹配
                    if valid_answer != "答案" and valid_answer in comment:
                        approval_matched = True
                        matched_conditions.append(f"答案条件：{valid_answer}")
                        break
    
    # 构建详细的日志信息
    nickname = stranger_info.get('nick', '未知用户') if stranger_info else '未知用户'
    level = stranger_info.get('qqLevel', '未知') if stranger_info else '未知'
    
    # 确保始终向群内发送审批处理结果，即使WebSocket连接有问题
    try:
        if approval_matched:
            logger.info(f"申请人 {user_id} ({nickname}) 符合自动审批条件:")
            logger.info(f"  - 等级: {level}")
            logger.info(f"  - 验证信息: {comment}")
            logger.info(f"  - 匹配条件: {', '.join(matched_conditions)}")
            
            logger.info(f"申请人 {user_id} 符合自动审批条件 ({', '.join(matched_conditions)})，自动通过")
            
            # 发送自动审批log到群里
            if context.websocket and not context.websocket.closed:
                approval_detail_msg = f"✅ 用户 {nickname}({user_id}) 的加群申请已自动通过\n"
                approval_detail_msg += f"等级: {level}\n"
                approval_detail_msg += f"验证信息: {comment}\n"
                approval_detail_msg += f"匹配条件: {', '.join(matched_conditions)}"
                
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.add_text(approval_detail_msg)
                await builder.send()
                logger.info(f"已发送审批通过详情到群 {group_name}({group_id})")
            else:
                logger.warning(f"WebSocket连接无效，无法发送审批通过详情到群 {group_name}({group_id})")
            
            await _approve_applicant(context, user_id, group_name, group_id, flag, stranger_info)
        else:
            logger.info(f"申请人 {user_id} 不符合任何自动审批条件，发送通知消息到群里")
            # 发送详细审批拒绝信息到群里
            if context.websocket and not context.websocket.closed:
                notification_msg = f"❕ 检测到 {nickname}({user_id}) 的加群申请，但不符合自动审批条件，请管理员处理。\n"
                notification_msg += f"等级: {level}\n"
                notification_msg += f"验证信息: {comment}"
                
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.add_text(notification_msg)
                await builder.send()
                logger.info(f"已发送审批拒绝详情到群 {group_name}({group_id})")
            else:
                logger.warning(f"WebSocket连接无效，无法发送审批拒绝详情到群 {group_name}({group_id})")
    except Exception as e:
        log_exception(logger, f"处理审批结果通知时发生异常", e)
        # 即使出现异常，也尝试发送简要通知到群里
        try:
            if context.websocket and not context.websocket.closed:
                error_msg = f"⚠️ 处理用户 {user_id} 的加群申请时发生错误，请查看日志"
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.add_text(error_msg)
                await builder.send()
        except:
            pass  # 忽略发送错误通知时的异常

async def _approve_applicant(context: BotContext, user_id: str, group_name: str, group_id: str, flag: str, info: Optional[dict] = None):
    """同意用户的加群申请。"""
    # 再次检查用户是否在黑名单中，确保即使验证信息正确也不能通过黑名单检查
    if await _is_user_blacklisted(context, group_id, user_id):
        logger.info(f"用户 {user_id} 在群 {group_id} 的黑名单中，即使验证信息正确也拒绝其加群申请")
        # 拒绝加群申请
        await _reject_group_application(context, flag, "用户在黑名单中")
        
        # 向群内发送通知
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(f"已自动拒绝黑名单用户 {user_id} 的加群申请（即使验证信息正确）")
        await builder.send()
        return
    
    api_params = {
        "flag": flag,
        "sub_type": "add",
        "approve": True
    }
    
    logger.debug(f"准备发送同意用户加群申请的请求: {api_params}")
    
    response = await call_onebot_api(context, 'set_group_add_request', api_params)
    if response and response.get('success'):
        logger.info(f"已自动同意用户 {user_id} 的加群申请: {group_name}({group_id})")
        logger.debug(f"成功发送同意用户加群申请的请求")
        
        # 发送欢迎消息
        if info:
            nickname = info.get('nick', '未知用户')
        else:
            nickname = '未知用户'
            
        # 获取群组配置，检查是否有自定义欢迎消息
        group_config = context.get_group_config(str(group_id))
        if group_config and "welcome_message" in group_config:
            welcome_msg = group_config["welcome_message"]
            # 可以使用一些占位符替换
            welcome_msg = welcome_msg.replace("{user_id}", str(user_id))
            welcome_msg = welcome_msg.replace("{nickname}", nickname)
        else:
            welcome_msg = f'''欢→迎→光↘临↗～'''
        
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_text(welcome_msg)
        await builder.send()
        logger.info(f"已发送用户欢迎消息到群 {group_name}({group_id})")
    else:
        error_msg = response.get('error', '未知错误') if response else '无响应'
        logger.warning(f"同意加群申请失败: {error_msg}")

async def _approve_root_user_request(context: BotContext, user_id: str, group_name: str, group_id: str, flag: str):
    """处理ROOT用户的加群申请。"""
    api_params = {
        "flag": flag,
        "sub_type": "add",
        "approve": True
    }
    
    logger.debug(f"准备发送同意ROOT用户加群申请的请求: {api_params}")
    
    response = await call_onebot_api(context, 'set_group_add_request', api_params)
    if response and response.get('success'):
        logger.info(f"已通过ROOT用户 {user_id} 的加群申请: {group_name}({group_id})")
        logger.debug(f"成功发送同意ROOT用户加群申请的请求")
        
        # 发送欢迎消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.add_at(user_id)
        builder.add_text(" 欢迎主人回来~")
        await builder.send()
        logger.info(f"已发送ROOT用户欢迎消息到群 {group_name}({group_id})")
    else:
        error_msg = response.get('error', '未知错误') if response else '无响应'
        logger.warning(f"通过ROOT用户加群申请失败: {error_msg}")