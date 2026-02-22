# core/sensitive_word_manager.py
# 独立的敏感词管理模块

import os
from datetime import datetime
from logger_config import get_logger

logger = get_logger("SensitiveWordManager")

# 敏感词库和触发日志现在由本模块管理
sensitive_words = {}
sensitive_trigger_log = []
MAX_LOG_ENTRIES = 50

def load_sensitive_words():
    """加载敏感词库，支持新旧格式并自动转换"""
    global sensitive_words
    try:
        # 使用相对路径，确保在任何地方调用都能找到文件
        file_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'bad.txt')
        needs_conversion = False
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if '/badword/' in first_line:
                words = first_line.split('/badword/')
                for word in words:
                    if word.strip():
                        sensitive_words[word.strip()] = '敏感'
                needs_conversion = True
            else:
                if first_line.strip():
                    sensitive_words[first_line.strip()] = '敏感'
                for line in f:
                    word = line.strip()
                    if word:
                        sensitive_words[word.strip()] = '敏感'
        if needs_conversion:
            with open(file_path, 'w', encoding='utf-8') as f:
                for word in sensitive_words.keys():
                    f.write(f"{word}\n")
            logger.info(f"敏感词库已自动从旧格式转换为新格式，共转换 {len(sensitive_words)} 个敏感词")
        logger.info(f"已加载 {len(sensitive_words)} 个敏感词")
    except Exception as e:
        logger.error(f"加载敏感词库失败: {e}")

def add_sensitive_word(word: str) -> bool:
    """添加敏感词"""
    global sensitive_words
    if word in sensitive_words:
        return False
    sensitive_words[word] = '敏感'
    file_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'bad.txt')
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"{word}\n")
        return True
    except Exception as e:
        logger.error(f"写入敏感词文件失败: {e}")
        return False

def remove_sensitive_word(word: str) -> bool:
    """删除敏感词"""
    global sensitive_words
    if word not in sensitive_words:
        return False
    del sensitive_words[word]
    file_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'bad.txt')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            all_words = [line.strip() for line in f if line.strip()]
        with open(file_path, 'w', encoding='utf-8') as f:
            for w in all_words:
                if w != word:
                    f.write(f"{w}\n")
        return True
    except Exception as e:
        logger.error(f"更新敏感词文件失败: {e}")
        return False

def get_sensitive_trigger_log() -> list:
    """获取敏感词触发日志"""
    global sensitive_trigger_log
    return sensitive_trigger_log.copy() # 返回副本，防止外部修改

def clear_sensitive_trigger_log():
    """清空敏感词触发日志"""
    global sensitive_trigger_log
    sensitive_trigger_log.clear()

def log_sensitive_trigger(message: str, word: str, group_id: str, user_id: str):
    """记录敏感词触发日志"""
    global sensitive_trigger_log
    log_entry = {
        "message": message,
        "word": word,
        "group_id": str(group_id),
        "user_id": str(user_id),
        "timestamp": int(datetime.now().timestamp())
    }
    sensitive_trigger_log.append(log_entry)
    if len(sensitive_trigger_log) > MAX_LOG_ENTRIES:
        sensitive_trigger_log.pop(0)

def is_sensitive(text: str) -> tuple:
    """检查文本是否包含敏感词，返回 (是否包含, 触发的词, 原因)"""
    global sensitive_words
    # 确保text是字符串类型
    text_str = str(text)
    for word, reason in sensitive_words.items():
        if word in text_str:
            return True, word, reason
    return False, "", ""

# 在模块加载时自动加载敏感词
load_sensitive_words()