# commands/plugin_command.py
# 处理 /plugin 命令，管理插件系统

import os
import asyncio
from logger_config import get_logger
from core.bot_context import BotContext
from utils.message_sender.message_builder import MessageBuilder


logger = get_logger("PluginCommand")

async def handle_plugin_command(context: BotContext, args: list, user_id: str, group_id: str, **kwargs) -> int:
    """处理 /plugin 命令，管理插件系统。
    
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
            builder.add_text("❓ 请指定子命令：list、load、unload、reload、enable、disable")
            await builder.send()
            return 0
        
        # 获取子命令
        sub_cmd = args[0].lower()
        
        # 检查是否有plugin_manager
        if not hasattr(context, 'plugin_manager'):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text("❌ 插件管理器未初始化")
            await builder.send()
            return 0
        
        plugin_manager = context.plugin_manager
        
        # 处理子命令
        if sub_cmd == 'list':
            await handle_plugin_list(context, plugin_manager, user_id, group_id)
        elif sub_cmd == 'unload':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要卸载的插件名称")
                await builder.send()
                return 0
            plugin_name = args[1]
            await handle_plugin_unload(context, plugin_manager, plugin_name, user_id, group_id)
        elif sub_cmd == 'load':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要加载的插件名称")
                await builder.send()
                return 0
            plugin_name = args[1]
            await handle_plugin_load(context, plugin_manager, plugin_name, user_id, group_id)
        elif sub_cmd == 'reload':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要重载的插件名称")
                await builder.send()
                return 0
            plugin_name = args[1]
            await handle_plugin_reload(context, plugin_manager, plugin_name, user_id, group_id)
        elif sub_cmd == 'enable':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要启用的插件名称")
                await builder.send()
                return 0
            plugin_name = args[1]
            await handle_plugin_enable(context, plugin_manager, plugin_name, user_id, group_id)
        elif sub_cmd == 'disable':
            if len(args) < 2:
                builder = MessageBuilder(context)
                builder.set_group_id(group_id)
                builder.set_user_id(user_id)
                builder.add_at()
                builder.add_text("❓ 请指定要禁用的插件名称")
                await builder.send()
                return 0
            plugin_name = args[1]
            await handle_plugin_disable(context, plugin_manager, plugin_name, user_id, group_id)
        else:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❓ 未知子命令: {sub_cmd}，可用命令：list、load、unload、reload、enable、disable")
            await builder.send()
        
        return 0
    except Exception as e:
        logger.error(f"处理plugin命令时发生异常: {e}")
        
        # 发送错误消息
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 处理命令时发生错误: {str(e)}")
        await error_builder.send()
        
        return 1

async def handle_plugin_list(context: BotContext, plugin_manager, user_id: str, group_id: str):
    """处理 /plugin list 命令，列出所有插件及其状态"""
    try:
        # 获取所有插件
        all_plugins = plugin_manager.list_plugins()
        enabled_plugins = plugin_manager.get_enabled_plugins()
        
        # 实时扫描插件目录
        plugins_dir = os.path.join(os.path.dirname(__file__), '..', 'plugins')
        available_plugins = []
        
        if os.path.exists(plugins_dir):
            for item in os.listdir(plugins_dir):
                item_path = os.path.join(plugins_dir, item)
                if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'plugin.yml')):
                    available_plugins.append(item)
        
        # 构建消息
        builder = MessageBuilder(context)
        builder.set_group_id(group_id)
        builder.set_user_id(user_id)
        builder.add_at()
        builder.add_text("📋 插件列表及运行状态：\n\n")
        
        if not available_plugins and not all_plugins:
            builder.add_text("❌ 未发现可用的插件")
        else:
            # 合并可用插件和已加载插件
            all_plugin_names = set(available_plugins + [p.id for p in all_plugins])
            
            for plugin_name in all_plugin_names:
                # 检查插件状态
                status = "🔴 未加载"
                version = "N/A"
                
                for plugin in all_plugins:
                    if plugin.id == plugin_name:
                        if plugin.status == 'enabled':
                            status = "🟢 已启用"
                        else:
                            status = "🟡 已加载（禁用）"
                        version = plugin.meta.get('version', 'N/A')
                        break
                
                builder.add_text(f"• {plugin_name} v{version}: {status}\n")
        
        await builder.send()
    except Exception as e:
        logger.error(f"处理plugin list命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 获取插件列表失败: {str(e)}")
        await error_builder.send()

async def handle_plugin_unload(context: BotContext, plugin_manager, plugin_name: str, user_id: str, group_id: str):
    """处理 /plugin unload 命令，卸载指定插件"""
    try:
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if not plugin_info:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 插件 {plugin_name} 未加载")
            await builder.send()
            return
        
        # 卸载插件
        success = await plugin_manager.unload(plugin_name)
        
        if success:
            # 发送成功消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"✅ 插件 {plugin_name} 已成功卸载")
            await builder.send()
        else:
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 卸载插件 {plugin_name} 失败")
            await builder.send()
    except Exception as e:
        logger.error(f"处理plugin unload命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 卸载插件失败: {str(e)}")
        await error_builder.send()

async def handle_plugin_load(context: BotContext, plugin_manager, plugin_name: str, user_id: str, group_id: str):
    """处理 /plugin load 命令，加载指定插件"""
    try:
        # 检查插件是否存在
        plugin_path = os.path.join(os.path.dirname(__file__), '..', 'plugins', plugin_name)
        if not os.path.exists(plugin_path) or not os.path.exists(os.path.join(plugin_path, 'plugin.yml')):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 插件 {plugin_name} 不存在")
            await builder.send()
            return
        
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if plugin_info:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"⚠️ 插件 {plugin_name} 已经加载")
            await builder.send()
            return
        
        # 加载插件
        success = await plugin_manager.load(plugin_name)
        
        if success:
            # 发送成功消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"✅ 插件 {plugin_name} 已成功加载")
            await builder.send()
        else:
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 加载插件 {plugin_name} 失败")
            await builder.send()
    except Exception as e:
        logger.error(f"处理plugin load命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 加载插件失败: {str(e)}")
        await error_builder.send()

async def handle_plugin_reload(context: BotContext, plugin_manager, plugin_name: str, user_id: str, group_id: str):
    """处理 /plugin reload 命令，重载指定插件"""
    try:
        # 检查插件是否存在
        plugin_path = os.path.join(os.path.dirname(__file__), '..', 'plugins', plugin_name)
        if not os.path.exists(plugin_path) or not os.path.exists(os.path.join(plugin_path, 'plugin.yml')):
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 插件 {plugin_name} 不存在")
            await builder.send()
            return
        
        # 重载插件
        success = await plugin_manager.reload(plugin_name)
        
        if success:
            # 发送成功消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"✅ 插件 {plugin_name} 已成功重载")
            await builder.send()
        else:
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 重载插件 {plugin_name} 失败")
            await builder.send()
    except Exception as e:
        logger.error(f"处理plugin reload命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 重载插件失败: {str(e)}")
        await error_builder.send()

async def handle_plugin_enable(context: BotContext, plugin_manager, plugin_name: str, user_id: str, group_id: str):
    """处理 /plugin enable 命令，启用指定插件"""
    try:
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if not plugin_info:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 插件 {plugin_name} 未加载")
            await builder.send()
            return
        
        # 启用插件
        success = await plugin_manager.enable(plugin_name)
        
        if success:
            # 发送成功消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"✅ 插件 {plugin_name} 已成功启用")
            await builder.send()
        else:
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 启用插件 {plugin_name} 失败")
            await builder.send()
    except Exception as e:
        logger.error(f"处理plugin enable命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 启用插件失败: {str(e)}")
        await error_builder.send()

async def handle_plugin_disable(context: BotContext, plugin_manager, plugin_name: str, user_id: str, group_id: str):
    """处理 /plugin disable 命令，禁用指定插件"""
    try:
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if not plugin_info:
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 插件 {plugin_name} 未加载")
            await builder.send()
            return
        
        # 禁用插件
        success = await plugin_manager.disable(plugin_name)
        
        if success:
            # 发送成功消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"✅ 插件 {plugin_name} 已成功禁用")
            await builder.send()
        else:
            # 发送失败消息
            builder = MessageBuilder(context)
            builder.set_group_id(group_id)
            builder.set_user_id(user_id)
            builder.add_at()
            builder.add_text(f"❌ 禁用插件 {plugin_name} 失败")
            await builder.send()
    except Exception as e:
        logger.error(f"处理plugin disable命令时发生异常: {e}")
        
        error_builder = MessageBuilder(context)
        error_builder.set_group_id(group_id)
        error_builder.set_user_id(user_id)
        error_builder.add_at()
        error_builder.add_text(f"🛑 禁用插件失败: {str(e)}")
        await error_builder.send()
