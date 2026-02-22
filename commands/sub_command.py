# commands/sub_command.py
# 处理 /sub 命令，管理子系统

import os
import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender.message_builder import MessageBuilder

logger = get_logger("SubCommand")

async def handle_sub_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> int:
    """处理 /sub 命令，管理子系统。
    
    Returns:
        int: 0 表示消息处理流程正常完成，1 表示消息处理过程中出现错误
    """
    try:
        # 检查是否为Root用户
        root_user_id = context.get_config_value("Root_user")
        if str(user_id) != str(root_user_id):
            # 使用MessageBuilder发送权限错误消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("⚠️ 该命令仅限Root用户使用")
            await builder.send()
            return 0
        
        # 检查是否有子命令
        if not args:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("❓ 请指定子命令：list、load、unload、reload、info")
            await builder.send()
            return 0
        
        # 获取子命令
        sub_cmd = args[0].lower()
        
        # 检查是否有subbot_manager
        if not hasattr(context, 'subbot_manager'):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("❌ 子机器人管理器未初始化")
            await builder.send()
            return 0
        
        subbot_manager = context.subbot_manager
        
        # 处理子命令
        if sub_cmd == 'list':
            await handle_sub_list(context, subbot_manager, user_id, group_id)
        elif sub_cmd == 'unload':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要卸载的子系统名称")
                await builder.send()
                return 0
            sub_name = args[1]
            await handle_sub_unload(context, subbot_manager, sub_name, user_id, group_id)
        elif sub_cmd == 'load':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要加载的子系统名称")
                await builder.send()
                return 0
            sub_name = args[1]
            await handle_sub_load(context, subbot_manager, sub_name, user_id, group_id)
        elif sub_cmd == 'reload':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要重载的子系统名称")
                await builder.send()
                return 0
            sub_name = args[1]
            await handle_sub_reload(context, subbot_manager, sub_name, user_id, group_id)
        elif sub_cmd == 'info':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要查看信息的子系统名称")
                await builder.send()
                return 0
            sub_name = args[1]
            await handle_sub_info(context, subbot_manager, sub_name, user_id, group_id)
        else:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❓ 未知子命令: {sub_cmd}\n可用命令: list、load、unload、reload、info")
            await builder.send()
        
        return 0
    except Exception as e:
        logger.error(f"处理sub命令时发生异常: {e}")
        
        # 发送错误消息
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 处理命令时发生错误: {str(e)}")
        await error_builder.send()
        
        return 1

async def handle_sub_list(context: BotContext, subbot_manager, user_id: str, group_id: str):
    """处理 /sub list 命令，实时扫描子系统列表和运行状态"""
    try:
        # 实时扫描子系统目录
        subsystem_dir = os.path.join(os.path.dirname(__file__), '..', 'subbot')
        available_subsystems = []
        
        if os.path.exists(subsystem_dir):
            for item in os.listdir(subsystem_dir):
                item_path = os.path.join(subsystem_dir, item)
                if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
                    available_subsystems.append(item)
        
        # 获取当前运行的子系统
        running_subsystems = subbot_manager.get_subbots()
        subbot_metadata = subbot_manager.get_all_subbot_metadata()
        
        # 构建消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("📋 子系统列表及运行状态：\n\n")
        
        if not available_subsystems:
            builder.add_text("❌ 未发现可用的子系统")
        else:
            for sub_name in available_subsystems:
                # 获取状态信息
                status = "🟢 运行中" if sub_name in running_subsystems else "🔴 未运行"
                
                # 获取元数据信息
                metadata = subbot_metadata.get(sub_name, {})
                version = metadata.get('version', 'N/A')
                description = metadata.get('description', '无描述')
                
                builder.add_text(f"🤖 {sub_name} ({version})\n")
                builder.add_text(f"   状态: {status}\n")
                builder.add_text(f"   描述: {description}\n")
                builder.add_text(f"   作者: {metadata.get('author', '未知')}\n\n")
        
        await builder.send()
    except Exception as e:
        logger.error(f"处理sub list命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 获取子系统列表失败: {str(e)}")
        await error_builder.send()

async def handle_sub_info(context: BotContext, subbot_manager, sub_name: str, user_id: str, group_id: str):
    """处理 /sub info 命令，显示子系统的详细信息"""
    try:
        # 获取元数据
        metadata = subbot_manager.get_subbot_metadata(sub_name)
        if not metadata:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 未找到子系统 {sub_name} 的元数据")
            await builder.send()
            return
        
        # 获取运行状态
        running_subsystems = subbot_manager.get_subbots()
        status = "🟢 运行中" if sub_name in running_subsystems else "🔴 未运行"
        
        # 构建详细信息消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"📊 子系统 {sub_name} 详细信息：\n\n")
        
        # 基本信息
        builder.add_text("📝 基本信息：\n")
        builder.add_text(f"   名称: {metadata.get('name', 'N/A')}\n")
        builder.add_text(f"   版本: {metadata.get('version', 'N/A')}\n")
        builder.add_text(f"   状态: {status}\n")
        builder.add_text(f"   作者: {metadata.get('author', '未知')}\n")
        builder.add_text(f"   描述: {metadata.get('description', '无描述')}\n\n")
        
        # 功能特性
        features = metadata.get('supported_features', [])
        if features:
            builder.add_text("⚡ 支持功能：\n")
            for feature in features:
                builder.add_text(f"   • {feature}\n")
            builder.add_text("\n")
        
        # 权限信息
        permissions = metadata.get('permissions', [])
        if permissions:
            builder.add_text("🔐 所需权限：\n")
            for perm in permissions:
                builder.add_text(f"   • {perm}\n")
            builder.add_text("\n")
        
        # 配置信息
        config = metadata.get('config', {})
        if config:
            builder.add_text("⚙️ 配置参数：\n")
            for key, value in config.items():
                builder.add_text(f"   {key}: {value}\n")
            builder.add_text("\n")
        
        # 元数据
        meta_info = metadata.get('metadata', {})
        if meta_info:
            builder.add_text("📄 其他信息：\n")
            if 'created_date' in meta_info:
                builder.add_text(f"   创建日期: {meta_info['created_date']}\n")
            if 'last_updated' in meta_info:
                builder.add_text(f"   最后更新: {meta_info['last_updated']}\n")
            if 'tags' in meta_info and meta_info['tags']:
                tags = ', '.join(meta_info['tags'])
                builder.add_text(f"   标签: {tags}\n")
        
        await builder.send()
    except Exception as e:
        logger.error(f"处理sub info命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 获取子系统信息失败: {str(e)}")
        await error_builder.send()

async def handle_sub_unload(context: BotContext, subbot_manager, sub_name: str, user_id: str, group_id: str):
    """处理 /sub unload 命令，停止指定子系统"""
    try:
        # 检查子系统是否运行
        running_subsystems = subbot_manager.get_subbots()
        if sub_name not in running_subsystems:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 子系统 {sub_name} 未运行")
            await builder.send()
            return
        
        # 停止子系统
        await subbot_manager.stop_subbot(sub_name)
        
        # 发送成功消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"✅ 子系统 {sub_name} 已成功停止")
        await builder.send()
    except Exception as e:
        logger.error(f"处理sub unload命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 停止子系统失败: {str(e)}")
        await error_builder.send()

async def handle_sub_load(context: BotContext, subbot_manager, sub_name: str, user_id: str, group_id: str):
    """处理 /sub load 命令，启动指定子系统"""
    try:
        # 检查子系统是否存在
        subsystem_dir = os.path.join(os.path.dirname(__file__), '..', 'subbot', sub_name)
        if not os.path.exists(subsystem_dir) or not os.path.exists(os.path.join(subsystem_dir, "__init__.py")):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 子系统 {sub_name} 不存在")
            await builder.send()
            return
        
        # 检查子系统是否已运行
        running_subsystems = subbot_manager.get_subbots()
        if sub_name in running_subsystems:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"⚠️ 子系统 {sub_name} 已经在运行")
            await builder.send()
            return
        
        # 加载子系统
        await subbot_manager.load_subbot(sub_name)
        
        # 发送成功消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"✅ 子系统 {sub_name} 已成功加载")
        await builder.send()
    except Exception as e:
        logger.error(f"处理sub load命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 加载子系统失败: {str(e)}")
        await error_builder.send()

async def handle_sub_reload(context: BotContext, subbot_manager, sub_name: str, user_id: str, group_id: str):
    """处理 /sub reload 命令，重载指定子系统"""
    try:
        # 检查子系统是否存在
        subsystem_dir = os.path.join(os.path.dirname(__file__), '..', 'subbot', sub_name)
        if not os.path.exists(subsystem_dir) or not os.path.exists(os.path.join(subsystem_dir, "__init__.py")):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 子系统 {sub_name} 不存在")
            await builder.send()
            return
        
        # 停止子系统（如果运行中）
        running_subsystems = subbot_manager.get_subbots()
        if sub_name in running_subsystems:
            await subbot_manager.stop_subbot(sub_name)
        
        # 重新加载子系统
        await subbot_manager.load_subbot(sub_name)
        
        # 发送成功消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text(f"✅ 子系统 {sub_name} 已成功重载")
        await builder.send()
    except Exception as e:
        logger.error(f"处理sub reload命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 重载子系统失败: {str(e)}")
        await error_builder.send()