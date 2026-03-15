# commands/account_command.py
# 账号管理命令，用于查看账号状态和切换运行模式

from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender import MessageBuilder, CommandResponse
from typing import Optional

logger = get_logger("AccountCommand")

async def handle_account_command(context: BotContext, **kwargs) -> CommandResponse:
    """处理 /account 命令
    
    用法:
    /account list - 查看所有账号状态
    /account mode - 查看当前运行模式
    /account mode parallel - 切换到并行模式
    /account mode fallback - 切换到故障转移模式
    """
    args = kwargs.get('args', [])
    user_id = kwargs.get('user_id')
    group_id = kwargs.get('group_id')
    
    if not args:
        # 默认显示帮助信息
        return CommandResponse.text("用法:\n/account list - 查看所有账号状态\n/account mode - 查看当前运行模式\n/account mode parallel|fallback - 切换运行模式")
    
    sub_command = args[0].lower()
    
    if sub_command == 'list':
        return await _handle_list_command(context, group_id, user_id)
    elif sub_command == 'mode':
        if len(args) > 1:
            return await _handle_mode_switch(context, group_id, user_id, args[1])
        else:
            return await _handle_mode_query(context, group_id, user_id)
    else:
        return CommandResponse.text(f"未知子命令: {sub_command}\n用法:\n/account list - 查看所有账号状态\n/account mode - 查看当前运行模式\n/account mode parallel|fallback - 切换运行模式")

async def _handle_list_command(context: BotContext, group_id: str, user_id: str) -> CommandResponse:
    """处理 list 子命令，显示所有账号状态"""
    try:
        # 获取所有账号信息
        accounts = context._account_manager.get_all_accounts()
        
        if not accounts:
            return CommandResponse.text("当前没有配置任何账号")
        
        # 获取 MultiWebSocketManager 的连接信息
        ws_manager = getattr(context, 'multi_ws_manager', None)
        
        # 构建账号状态信息
        lines = ["📋 账号状态列表", "=" * 40]
        
        for account_id, account_info in sorted(accounts.items()):
            bot_qq = account_info.get('bot_qq', '未知')
            priority = account_info.get('priority', 0)
            
            # 获取连接状态
            status_emoji = "⚪"
            status_text = "未连接"
            
            if ws_manager and hasattr(ws_manager, 'connections'):
                conn = ws_manager.connections.get(account_id)
                if conn:
                    if conn.is_connected:
                        if conn.is_healthy:
                            status_emoji = "🟢"
                            status_text = "正常"
                        else:
                            status_emoji = "🟡"
                            status_text = "心跳超时"
                    else:
                        status_emoji = "🔴"
                        status_text = "已断开"
            
            # 检查是否为活跃账号（fallback模式下）
            active_marker = ""
            if ws_manager and hasattr(ws_manager, 'active_connection_id'):
                if ws_manager.active_connection_id == account_id:
                    active_marker = " [活跃]"
            
            lines.append(f"{status_emoji} 账号 {account_id} (QQ: {bot_qq})")
            lines.append(f"   状态: {status_text}{active_marker}")
            lines.append(f"   优先级: {priority}")
            
            # 添加 WebSocket 和 API 地址
            ws_uri = account_info.get('ws_uri', '')
            api_base = account_info.get('onebot_api_base', '')
            if ws_uri:
                lines.append(f"   WS: {ws_uri}")
            if api_base:
                lines.append(f"   API: {api_base}")
            
            lines.append("")
        
        # 添加当前运行模式信息
        current_mode = context._config.get('mode', 'fallback')
        lines.append("=" * 40)
        lines.append(f"当前运行模式: {current_mode}")
        
        if current_mode == 'parallel':
            lines.append("说明: 所有账号同时在线，各自处理消息")
        else:
            lines.append("说明: 只有一个活跃账号，故障时自动切换")
        
        return CommandResponse.text("\n".join(lines))
        
    except Exception as e:
        logger.error(f"获取账号列表时发生错误: {e}", exc_info=True)
        return CommandResponse.text(f"获取账号列表失败: {str(e)}")

async def _handle_mode_query(context: BotContext, group_id: str, user_id: str) -> CommandResponse:
    """处理 mode 查询子命令"""
    current_mode = context._config.get('mode', 'fallback')
    
    lines = ["⚙️ 当前运行模式", "=" * 30]
    lines.append(f"模式: {current_mode}")
    lines.append("")
    
    if current_mode == 'parallel':
        lines.append("📖 并行模式说明:")
        lines.append("• 所有账号同时保持WebSocket连接")
        lines.append("• 哪个账号接收到的消息，就用哪个账号回复")
        lines.append("• 账号间互不影响，单个账号故障不影响其他账号")
        lines.append("• 适用于多账号独立运营场景")
    else:
        lines.append("📖 故障转移模式说明:")
        lines.append("• 只有一个活跃账号处理所有消息")
        lines.append("• 账号按优先级排序，数字越小优先级越高")
        lines.append("• 高优先级账号故障时自动切换到低优先级账号")
        lines.append("• 高优先级账号恢复后自动切回")
        lines.append("• 适用于主备容灾场景")
    
    lines.append("")
    lines.append("💡 使用 /account mode parallel|fallback 切换模式")
    
    return CommandResponse.text("\n".join(lines))

async def _handle_mode_switch(context: BotContext, group_id: str, user_id: str, new_mode: str) -> CommandResponse:
    """处理 mode 切换子命令"""
    new_mode = new_mode.lower()
    
    if new_mode not in ['parallel', 'fallback']:
        return CommandResponse.text("无效的模式，请使用 parallel 或 fallback")
    
    current_mode = context._config.get('mode', 'fallback')
    
    if current_mode == new_mode:
        return CommandResponse.text(f"当前已经是 {new_mode} 模式，无需切换")
    
    try:
        # 更新配置
        context._config['mode'] = new_mode
        
        # 更新 MultiWebSocketManager 的模式
        ws_manager = getattr(context, 'multi_ws_manager', None)
        if ws_manager:
            ws_manager.mode = new_mode
            logger.info(f"已切换运行模式: {current_mode} -> {new_mode}")
            
            # 如果切换到 parallel 模式，需要确保所有连接都活跃
            if new_mode == 'parallel':
                logger.info("切换到 parallel 模式，所有账号将同时保持活跃")
                # 在 parallel 模式下，不需要特别的切换逻辑
                # 因为每个连接独立处理消息
            else:
                # 切换到 fallback 模式，需要重新评估活跃连接
                logger.info("切换到 fallback 模式，将选择优先级最高的健康账号作为活跃账号")
                if hasattr(ws_manager, '_set_initial_active_connection'):
                    ws_manager._set_initial_active_connection()
        
        # 保存配置到文件（可选，如果需要持久化）
        # 注意：这里我们只修改内存中的配置，不写入文件
        # 如果需要持久化，可以取消下面的注释
        # await _save_config(context)
        
        return CommandResponse.text(f"✅ 已成功切换运行模式\n\n{current_mode} -> {new_mode}\n\n注意: 此更改仅对当前运行会话有效，重启后将恢复配置文件中的设置")
        
    except Exception as e:
        logger.error(f"切换运行模式时发生错误: {e}", exc_info=True)
        return CommandResponse.text(f"❌ 切换模式失败: {str(e)}")

# 为了兼容旧版命令加载机制，提供一个同步包装函数
def handle_account(context: BotContext, **kwargs):
    """同步包装函数，用于命令注册"""
    import asyncio
    return asyncio.create_task(handle_account_command(context, **kwargs))
