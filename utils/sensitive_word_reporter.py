# utils/sensitive_word_reporter.py
# 敏感词报告处理器，支持多种推送目标

import os
import time
import json
from datetime import datetime
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder

logger = get_logger("SensitiveWordReporter")

class SensitiveWordReporter:
    """敏感词报告处理器"""
    
    @staticmethod
    async def send_report(context: BotContext, group_id: str, user_id: str, 
                         message: str, sensitive_word: str, recalled: bool = False,
                         additional_info: dict = None) -> bool:
        """
        发送敏感词报告到配置的目标
        
        Args:
            context: Bot上下文
            group_id: 群组ID
            user_id: 用户ID
            message: 原始消息内容
            sensitive_word: 检测到的敏感词
            recalled: 是否已撤回
            additional_info: 额外信息字典
            
        Returns:
            bool: 发送是否成功
        """
        # 获取推送目标配置，默认为report_group
        target = context.get_config_value("sensitive_word_target", "report_group")
        logger.debug(f"敏感词报告目标配置: {target}")
        
        if target == "out-file":
            return await SensitiveWordReporter._send_to_file(
                context, group_id, user_id, message, sensitive_word, recalled, additional_info
            )
        else:  # 默认为 report_group
            return await SensitiveWordReporter._send_to_group(
                context, group_id, user_id, message, sensitive_word, recalled, additional_info
            )
    
    @staticmethod
    async def _send_to_group(context: BotContext, group_id: str, user_id: str,
                            message: str, sensitive_word: str, recalled: bool,
                            additional_info: dict = None) -> bool:
        """发送敏感词报告到群聊"""
        try:
            # 获取报告群ID
            report_group_id = context.get_config_value("report_group")
            if not report_group_id:
                logger.warning("未配置report_group，无法发送敏感词报告到群聊")
                return False
            
            # 构建报告消息
            recall_status = "已撤回" if recalled else "未撤回"
            
            report_lines = [
                f"[敏感词检测报告]({recall_status})",
                f"用户: {user_id}",
                f"群聊: {group_id}",
                f"敏感词: {sensitive_word}",
                f"消息内容: {message[:200]}{'...' if len(message) > 200 else ''}",
                f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ]
            
            # 添加额外信息（如果有的话）
            if additional_info:
                for key, value in additional_info.items():
                    report_lines.append(f"{key}: {value}")
            
            # 使用MessageBuilder发送消息
            builder = MessageBuilder(context)
            builder.set_group_id(str(report_group_id))
            builder.set_badword_bypass(True, "管理员敏感词报告", "system")
            
            for line in report_lines:
                builder.add_text(f"{line}\n")
            
            await builder.send()
            logger.info(f"已发送敏感词报告到群聊 {report_group_id}")
            return True
            
        except Exception as e:
            logger.error(f"发送敏感词报告到群聊失败: {str(e)}")
            return False
    
    @staticmethod
    async def _send_to_file(context: BotContext, group_id: str, user_id: str,
                           message: str, sensitive_word: str, recalled: bool,
                           additional_info: dict = None) -> bool:
        """发送敏感词报告到文件"""
        try:
            # 确定日志文件路径
            log_dir = os.path.join(os.path.dirname(__file__), '..', 'lg')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'bad-word.log')
            
            # 构建报告数据
            report_data = {
                "timestamp": int(time.time()),
                "time_readable": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "type": "sensitive_word_report",
                "recalled": recalled,
                "group_id": str(group_id),
                "user_id": str(user_id),
                "sensitive_word": sensitive_word,
                "message": message[:500] + "..." if len(message) > 500 else message,  # 限制消息长度
                "message_length": len(message)
            }
            
            # 添加额外信息
            if additional_info:
                report_data.update(additional_info)
            
            # 写入日志文件
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(report_data, ensure_ascii=False) + '\n')
            
            logger.info(f"已写入敏感词报告到文件: {log_file}")
            return True
            
        except Exception as e:
            logger.error(f"写入敏感词报告到文件失败: {str(e)}")
            return False

# 保持向后兼容的函数接口
async def send_sensitive_report(context: BotContext, group_id: str, user_id: str,
                               message: str, sensitive_word: str, recalled: bool = False) -> bool:
    """
    向后兼容的敏感词报告发送函数
    
    Args:
        context: Bot上下文
        group_id: 群组ID
        user_id: 用户ID
        message: 原始消息内容
        sensitive_word: 检测到的敏感词
        recalled: 是否已撤回
        
    Returns:
        bool: 发送是否成功
    """
    return await SensitiveWordReporter.send_report(
        context, group_id, user_id, message, sensitive_word, recalled
    )
