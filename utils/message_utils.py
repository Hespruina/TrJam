# utils/message_utils.py
# 提供消息解析、敏感词检查、繁体字转换等通用工具

import re
from opencc import OpenCC

def parse_message(raw_message):
    """解析原始消息，提取纯文本和CQ码"""
    if isinstance(raw_message, str):
        return re.sub(r'\s+', ' ', raw_message.strip())
    text_parts = []
    if isinstance(raw_message, list):
        for segment in raw_message:
            if isinstance(segment, dict):
                seg_type = segment.get('type')
                if seg_type == 'text':
                    text = str(segment.get('data', {}).get('text', ''))
                    text_parts.append(text)
                elif seg_type == 'at':
                    qq = str(segment.get('data', {}).get('qq', ''))
                    text_parts.append(f'[CQ:at,qq={qq}]')
    return ' '.join(text_parts).strip()

def is_traditional_chinese(text):
    """检测文本是否包含繁体字。"""
    cc = OpenCC('t2s')
    converted = cc.convert(text)
    return text != converted

def convert_to_simplified(text):
    """将繁体字转换为简体字。"""
    cc = OpenCC('t2s')
    return cc.convert(text)

def parse_at_or_qq(args, group_id=None):
    """解析命令参数中的 @ 或 QQ 号。"""
    if not args:
        return None, args
    raw_target = args[0]
    target_user_id = None
    remaining_args = args[1:]
    at_match = re.search(r'\[CQ:at,qq=(\d+)\]', raw_target)
    if at_match:
        target_user_id = at_match.group(1)
    elif raw_target.isdigit():
        target_user_id = raw_target
    if target_user_id:
        return target_user_id, remaining_args
    else:
        return None, args