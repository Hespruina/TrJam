# commands/group_command/join_handler.py
# 加群处理功能

import json
import os
from core.trust_manager import trust_manager
from utils.message_sender import CommandResponse
from logger_config import get_logger

logger = get_logger("GroupCommandJoin")

# 全局变量：未信任群组的统一提示信息
UNTRUSTED_GROUP_MESSAGE = "当前群未被信任，无法使用该功能。请联系ROOT用户了解如何信任本群。Root用户QQ：2711631445"

async def handle_join_command(context, args, user_id, group_id, user_level, sender_role=None):
    """处理 /group join 子命令（原 toggle event 功能）"""
    # 检查权限，群主、管理员及以上权限可以使用
    has_permission = user_level >= 1 or sender_role in ["admin", "owner"]
    if not has_permission:
        return CommandResponse.text("❌ 权限不足，需要管理员权限")
    
    if len(args) < 1:
        return CommandResponse.text("用法: /group join set [level/answer] [值]\n或: /group join list\n或: /group join rm [编号]\n或: /group join welcome [消息内容]")
    
    event_action = args[0].lower()
    
    if event_action == "list":
        return await list_event_approvals(context, group_id)
    elif event_action == "set":
        if len(args) < 3:
            return CommandResponse.text("用法: /group join set [level/answer] [值]")
        return await set_event_approval(context, args[1:], user_id, group_id)
    elif event_action == "rm":
        if len(args) < 2:
            return CommandResponse.text("用法: /group join rm [编号]")
        return await remove_event_approval(context, args[1], user_id, group_id)
    elif event_action == "welcome":
        if len(args) < 2:
            return CommandResponse.text("用法: /group join welcome [消息内容]")
        return await set_welcome_message(context, args[1:], group_id)
    else:
        return CommandResponse.text("❌ 无效的操作，支持的操作: set, list, rm, welcome")

async def list_event_approvals(context, group_id):
    """列出所有事件审批条件"""
    # 获取群组配置文件路径
    group_config_path = f"data/group_config/{group_id}.json"
    
    # 读取现有配置
    group_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_config = json.load(f)
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 检查是否存在event_approvals
    if "event_approvals" not in group_config or not group_config["event_approvals"]:
        return CommandResponse.text("📋 当前没有设置任何事件审批条件")
    
    # 构建审批条件列表
    approvals = group_config["event_approvals"]
    approval_list = ["📋 事件审批条件列表:"]
    for i, approval in enumerate(approvals):
        if approval["type"] == "level":
            approval_list.append(f"{i+1}. 等级条件: {approval['value']}")
        elif approval["type"] == "answer":
            approval_list.append(f"{i+1}. 关键词条件: {approval['value']}")
    
    # 显示欢迎消息
    if "welcome_message" in group_config:
        approval_list.append(f"\n🎉 欢迎消息: {group_config['welcome_message']}")
    else:
        approval_list.append("\n🎉 欢迎消息: 未设置")
    
    return CommandResponse.text("\n".join(approval_list))

async def set_event_approval(context, args, user_id, group_id):
    """设置事件审批条件"""
    event_type = args[0].lower()
    value = args[1]
    
    if event_type not in ["level", "answer"]:
        return CommandResponse.text("❌ 无效的类型，仅支持 level 或 answer")
    
    # 获取群组配置文件路径
    group_config_path = f"data/group_config/{group_id}.json"
    
    # 读取现有配置
    group_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_config = json.load(f)
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 确保 event_approvals 字段存在
    if "event_approvals" not in group_config:
        group_config["event_approvals"] = []
    
    # 对于level类型，检查是否已存在相同类型的条件
    if event_type == "level":
        for approval in group_config["event_approvals"]:
            if approval["type"] == "level":
                return CommandResponse.text("❌ 已存在等级条件，每种类型只能设置一个")
    
    # 创建新的审批条件
    new_approval = {
        "type": event_type,
        "value": value
    }
    
    # 添加到审批条件列表
    group_config["event_approvals"].append(new_approval)
    
    # 保存配置
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(group_config_path), exist_ok=True)
        
        with open(group_config_path, 'w', encoding='utf-8') as f:
            json.dump(group_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置文件失败: {e}")
        return CommandResponse.text("❌ 保存群组配置文件失败")
    
    type_text = "等级" if event_type == "level" else "关键词"
    return CommandResponse.text(f"✅ 已添加自动审批条件: 当{type_text}为 '{value}' 时自动通过")

async def set_welcome_message(context, args, group_id):
    """设置欢迎消息"""
    # 重写的信任检查逻辑 - 确保group_id为字符串类型
    group_id_str = str(group_id)
    logger.info(f"欢迎消息设置请求 - 群ID: {group_id_str} (原始类型: {type(group_id)})")
    
    # 检查群组是否被信任
    is_trusted = trust_manager.is_trusted_group(group_id_str)
    logger.info(f"群组信任状态检查结果: {is_trusted} (群ID: {group_id_str})")
    
    if not is_trusted:
        logger.warning(f"未信任群尝试设置欢迎消息: {group_id_str}")
        return CommandResponse.text(UNTRUSTED_GROUP_MESSAGE)
    
    # 将参数合并为完整的消息内容
    welcome_message = " ".join(args)
    
    # 获取群组配置文件路径
    group_config_path = f"data/group_config/{group_id}.json"
    
    # 读取现有配置
    group_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_config = json.load(f)
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 设置欢迎消息
    group_config["welcome_message"] = welcome_message
    
    # 保存配置
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(group_config_path), exist_ok=True)
        
        with open(group_config_path, 'w', encoding='utf-8') as f:
            json.dump(group_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置文件失败: {e}")
        return CommandResponse.text("❌ 保存群组配置文件失败")
    
    return CommandResponse.text(f"✅ 已设置欢迎消息: {welcome_message}")

async def remove_event_approval(context, index_str, user_id, group_id):
    """删除事件审批条件"""
    try:
        index = int(index_str) - 1  # 转换为0基索引
    except ValueError:
        return CommandResponse.text("❌ 编号必须是数字")
    
    # 获取群组配置文件路径
    group_config_path = f"data/group_config/{group_id}.json"
    
    # 读取现有配置
    group_config = {}
    if os.path.exists(group_config_path):
        try:
            with open(group_config_path, 'r', encoding='utf-8') as f:
                group_config = json.load(f)
        except Exception as e:
            logger.error(f"读取群组配置文件失败: {e}")
            return CommandResponse.text("❌ 读取群组配置文件失败")
    
    # 检查是否存在event_approvals
    if "event_approvals" not in group_config or not group_config["event_approvals"]:
        return CommandResponse.text("❌ 当前没有设置任何事件审批条件")
    
    # 检查索引是否有效
    approvals = group_config["event_approvals"]
    if index < 0 or index >= len(approvals):
        return CommandResponse.text("❌ 编号超出范围")
    
    # 删除指定的审批条件
    removed_approval = approvals.pop(index)
    
    # 保存配置
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(group_config_path), exist_ok=True)
        
        with open(group_config_path, 'w', encoding='utf-8') as f:
            json.dump(group_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群组配置文件失败: {e}")
        return CommandResponse.text("❌ 保存群组配置文件失败")
    
    type_text = "等级" if removed_approval["type"] == "level" else "关键词"
    return CommandResponse.text(f"✅ 已删除{type_text}条件: {removed_approval['value']}")