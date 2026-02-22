import json
import os
from utils.message_sender import CommandResponse
from logger_config import get_logger

logger = get_logger("ToggleCommand")

# 定义可用的功能列表及其默认状态
AVAILABLE_FEATURES = {
    "group_exit": {
        "name": "退群和踢出推送",
        "description": "当有成员退群或被踢出时发送推送通知",
        "default": False
    },
    "sensitive_word_recall": {
        "name": "敏感词自动撤回",
        "description": "检测到敏感词时自动撤回消息",
        "default": False,
        "alias": "autorecall"  # 添加别名
    },
    "leg_photo_essence": {
        "name": "腿照自动设为精华",
        "description": "识别到腿照时自动设为精华消息",
        "default": False,
        "alias": "leg"  # 添加别名
    }
    # 移除了 mc_push 功能，将其交给插件处理
}

async def handle_toggle_command(context, args, user_id, group_id, user_level, sender_role=None, **kwargs):
    """处理 /toggle 命令，用于控制群聊中的各种功能开关"""
    
    # 检查权限，群主、管理员及以上权限可以使用
    # user_level 0: User, 1: Admin, 2: Root
    # sender_role: "member", "admin", "owner"
    has_permission = user_level >= 1 or sender_role in ["admin", "owner"]
    if not has_permission:
        return CommandResponse.text("❌ 权限不足，需要管理员权限")
    
    if len(args) < 1:
        # 显示功能列表
        feature_list = ["📋 可用功能列表:"]
        for key, feature in AVAILABLE_FEATURES.items():
            alias_info = f" ({feature.get('alias')})" if feature.get('alias') else ""
            feature_list.append(f"- {key}: {feature['name']}{alias_info}")
        feature_list.append("\n用法:")
        feature_list.append("/toggle enable/disable <功能名> - 开启/关闭功能")
        return CommandResponse.text("\n".join(feature_list))
    
    subcommand = args[0].lower()
    
    # 处理原有的功能开关
    if len(args) < 2:
        return CommandResponse.text("用法: /toggle enable/disable 功能名\n可用功能:\n" + 
                                  "\n".join([f"- {key}: {feature['name']}" for key, feature in AVAILABLE_FEATURES.items()]))
    
    action = args[0].lower()
    feature_name = args[1].lower()
    
    # 检查动作是否有效
    if action not in ["enable", "disable"]:
        return CommandResponse.text("❌ 无效的动作，仅支持 enable 或 disable")
    
    # 查找功能（支持别名）
    found_feature_key = None
    for key, feature in AVAILABLE_FEATURES.items():
        if key == feature_name or feature.get('alias') == feature_name:
            found_feature_key = key
            break
    
    # 检查功能是否存在
    if found_feature_key is None:
        return CommandResponse.text("❌ 未知的功能\n可用功能:\n" + 
                                  "\n".join([f"- {key}: {feature['name']}" for key, feature in AVAILABLE_FEATURES.items()]))
    
    # 如果是内置功能，继续处理
    if found_feature_key in AVAILABLE_FEATURES:
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
        
        # 设置功能开关
        feature_key = f"{found_feature_key}_enabled"
        enabled = action == "enable"
        
        # 更新配置
        group_config[feature_key] = enabled
        
        # 保存配置
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(group_config_path), exist_ok=True)
            
            with open(group_config_path, 'w', encoding='utf-8') as f:
                json.dump(group_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存群组配置文件失败: {e}")
            return CommandResponse.text("❌ 保存群组配置文件失败")
        
        feature_info = AVAILABLE_FEATURES[found_feature_key]
        status_text = "启用" if enabled else "禁用"
        
        return CommandResponse.text(f"✅ 功能 '{feature_info['name']}' 已{status_text}")
    
    return CommandResponse.text("❌ 功能处理失败")