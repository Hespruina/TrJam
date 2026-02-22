# app.py - 重构后
# 核心入口文件，负责初始化、启动服务和协调各模块

import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
import subprocess
from typing import TYPE_CHECKING
import yaml

# 解析命令行参数，检查是否禁用 colorama
_no_colorama = '--no_colorama' in sys.argv

if TYPE_CHECKING:
    from core.multi_websocket_manager import MultiWebSocketManager

def print_sky_blue_art():
    """打印启动时的天蓝色ASCII艺术字"""
    if _no_colorama:
        # 使用 Linux 原生 ANSI 颜色码
        cyan = '\033[96m'
        reset = '\033[0m'
    else:
        # 使用 colorama
        try:
            import colorama
            colorama.init()
            from colorama import Fore, Style
            cyan = Fore.CYAN
            reset = Style.RESET_ALL
        except ImportError:
            # 如果没有安装colorama，定义空的样式类
            class ForeClass:
                CYAN = ''
                RESET = ''
            class StyleClass:
                RESET_ALL = ''
            cyan = ''
            reset = ''
    
    art = f"""{cyan}
#   _____  _   _   ____                   _               _   
#  |__  / | | | | |  _ \   _ __    ___   | |__     ___   | |_ 
#    / /  | |_| | | |_) | | '__|  / _ \  | '_ \   / _ \  | __|
#   / /_  |  _  | |  _ <  | |    | (_) | | |_) | | (_) | | |_ 
#  /____| |_| |_| |_| \_\ |_|     \___/  |_.__/   \___/   \__|
#                                                             {reset}"""
    
    print(art)

# 检查Python版本和自动安装缺失的库
def check_and_install_dependencies():
    # 检查Python版本 (需要至少3.8)
    if sys.version_info < (3, 8):
        print(f"错误: Python版本过低 ({sys.version_info.major}.{sys.version_info.minor})，需要至少Python 3.8")
        sys.exit(1)
    
    # 需要检查的第三方库列表
    required_packages = [
        'aiohttp',
        'aiosqlite',
        'PyYAML',
        'Pillow',
        'playwright',
        'mcstatus',
        'requests'
    ]
    
    missing_packages = []
    
    # 检查每个包是否已安装
    for package in required_packages:
        try:
            # 特殊处理一些包名和导入名不一致的情况
            if package == 'PyYAML':
                import yaml
            elif package == 'Pillow':
                from PIL import Image
            elif package == 'playwright':
                import playwright
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    # 如果有缺失的包，尝试自动安装
    if missing_packages:
        print(f"检测到缺失的依赖包: {', '.join(missing_packages)}")
        print("正在尝试自动安装...")
        
        import subprocess
        for package in missing_packages:
            try:
                # 使用阿里云镜像安装
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', package, 
                    '-i', 'https://mirrors.aliyun.com/pypi/simple/'
                ])
                print(f"成功安装 {package}")
            except subprocess.CalledProcessError:
                print(f"安装 {package} 失败，请手动安装")
                sys.exit(1)
        print("所有依赖包安装完成")

# 在程序开始时检查依赖
check_and_install_dependencies()

# ---------------------- 日志系统 ----------------------
from logger_config import get_logger, log_exception, set_no_colorama
set_no_colorama(_no_colorama)
logger = get_logger("QQBot")

# ---------------------- 核心上下文管理 ----------------------
import asyncio
from core.bot_context import BotContext
from core.config_manager import load_config
from core.config_watcher import config_watcher
from core.multi_websocket_manager import MultiWebSocketManager
from core.message_router import MessageRouter
from core.subbot_manager import SubBotManager

# ---------------------- 命令系统 ----------------------
from commands.command_dispatcher import initialize_command_mappings
from commands.command_loader import load_command_handlers


# ---------------------- 后台任务 ----------------------
from utils.task_utils import start_background_tasks



# ---------------------- 浏览器管理器 ----------------------
from core.browser_manager import ensure_browser_initialized, cleanup_browser

# ---------------------- 控制台处理器 ----------------------
from handlers.console_handler import ConsoleHandler

# 用于快速退出的全局标志
_fast_exit = False

# ---------------------- 主函数 ----------------------
async def main():
    """主函数，协调整个程序的启动和运行。"""
    global _fast_exit
    # 使用导入的get_logger函数
    from logger_config import get_logger
    logger = get_logger("Main")
    print_sky_blue_art()  # 打印天蓝色ASCII艺术字
    logger.info("正在初始化ZHRrobot...")
    


    # 加载配置
    config = load_config()

    # 2. 创建核心上下文
    context = BotContext(config)

    # 3. 初始化中文命令映射
    initialize_command_mappings(config)
    load_command_handlers(config)
    
    # 4. 启动配置文件监控
    config_watcher.add_callback(on_config_change)
    config_watcher.start()

    # 5. 创建多WebSocket管理器
    multi_websocket_manager: 'MultiWebSocketManager' = MultiWebSocketManager(context)
    # 将多连接管理器添加到上下文中（通过自定义属性）
    setattr(context, 'multi_ws_manager', multi_websocket_manager)
    
    # 设置连接成功回调函数，当主机器人连接成功时启动子机器人管理器
    async def on_connection_success():
        logger.info("主机器人连接成功，启动子机器人管理器")
        if hasattr(context, 'subbot_manager'):
            await context.subbot_manager.start()
    
    multi_websocket_manager.set_connection_success_callback(on_connection_success)

    # 6. 创建消息路由器
    message_router = MessageRouter(context)
    # 将MessageRouter实例存储到BotContext中，以便控制台处理器访问
    setattr(context, 'message_router', message_router)

    # 6.1 初始化插件管理器并加载插件
    from plugin_system import PluginManager
    logger.info("正在初始化插件管理器...")
    plugin_manager = PluginManager(context, plugins_dir="plugins")
    message_router.plugin_manager = plugin_manager
    # 将plugin_manager设置到context中，以便插件命令能够访问
    setattr(context, 'plugin_manager', plugin_manager)
    logger.info("正在加载插件...")
    load_results = await plugin_manager.load_all()
    loaded_count = sum(1 for success in load_results.values() if success)
    logger.info(f"插件加载完成: 成功 {loaded_count}/{len(load_results)}")

    # 7. 初始化子机器人管理器（暂不启动，等待主机器人连接成功后再启动）
    # 这里需要根据实际的主机器人WebSocket URL和token进行配置
    # 假设主机器人的WebSocket服务在本地8080端口
    parent_ws_url = "ws://127.0.0.1:8080"
    parent_token = "main_bot_token"  # 实际使用时应该从配置中读取
    
    subbot_manager = SubBotManager(parent_ws_url, parent_token)
    subbot_manager.context = context  # 设置上下文对象
    setattr(context, 'subbot_manager', subbot_manager)
    
    # 注意：子机器人管理器将在主机器人连接成功后通过回调启动

    # 8. 启动HTTP服务（已移至D-Cloud插件中处理）
    # await start_http_servers(context, message_router.handle_http_request)
    # HTTP服务器启动代码已移除

    # 8. 预初始化浏览器管理器（提高渲染速度）
    try:
        logger.info("正在预热浏览器渲染引擎...")
        await ensure_browser_initialized()
        logger.info("浏览器渲染引擎预热完成")
    except Exception as e:
        logger.error(f"浏览器预热失败，将在需要时尝试初始化: {e}")
    
    # 9. 启动后台任务
    start_background_tasks()
    
    # 9.1 初始化SiliconFlow功能



    # 10. 创建并启动控制台处理器
    console_handler = ConsoleHandler(context)
    console_task = asyncio.create_task(console_handler.handle_console_input())
    
    # 存储所有需要管理的任务
    background_tasks = [console_task]
    
    try:
        # 11. 启动多WebSocket主循环
        logger.info("准备启动多WebSocket主循环...")
        logger.debug(f"多WebSocket管理器: {multi_websocket_manager}")
        logger.debug(f"消息路由器: {message_router}")
        
        # 创建快速重启检测任务
        async def check_fast_exit():
            global _fast_exit
            while not _fast_exit:
                await asyncio.sleep(0.1)
            return True
        
        exit_check_task = asyncio.create_task(check_fast_exit())
        
        # 将主循环也创建为任务
        main_loop_task = asyncio.create_task(
            multi_websocket_manager.start_main_loop(message_router.handle_websocket_message)
        )
        
        # 等待WebSocket主循环或快速退出信号
        done, pending = await asyncio.wait(
            [main_loop_task, exit_check_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 取消未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"任务已取消: {task}")
            except Exception as e:
                logger.error(f"取消任务时发生错误: {e}", exc_info=True)
        
        logger.info("多WebSocket主循环正常退出")
        return _fast_exit  # 返回是否需要快速重启
        
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return False  # 用户中断，不需要重启
    except Exception as e:
        logger.critical(f"WebSocket主循环发生异常: {e}", exc_info=True)
        return False  # 异常退出，不需要重启
    finally:
        # 取消所有后台任务
        logger.info("正在取消后台任务...")
        for task in background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"任务已取消: {task}")
                except Exception as e:
                    logger.error(f"取消任务时发生错误: {e}", exc_info=True)
        
        # 停止子机器人管理器
        if hasattr(context, 'subbot_manager'):
            try:
                await context.subbot_manager.stop()
            except Exception as e:
                logger.error(f"停止子机器人管理器时发生错误: {e}")
        
        # 停止配置监控
        config_watcher.stop()
        
        # 如果不是快速退出，则清理浏览器资源
        if not _fast_exit:
            await cleanup_browser()
        
        logger.info("主程序结束")


def on_config_change(changed_files):
    """配置文件变化回调函数"""
    logger.info(f"配置文件 {', '.join(changed_files)} 已更新并生效")
    
    # 重新加载配置
    config = load_config()


async def run_qqbot():
    global _fast_exit
    logger = get_logger("RunQQBot")  # 初始化logger变量
    print("=====================================")
    print_sky_blue_art()
    print("=====================================")
    print("ZHRrobot 启动中...")
    print("输入 'help' 查看可用命令")
    print("=====================================")
    print("注意：输入命令时，提示符 '> ' 可能会被日志覆盖，请直接输入命令后按回车")
    
    try:
        # 运行主函数并获取是否需要重启的标志
        should_restart = await main()
        
        # 如果需要重启，创建重启标志文件
        if should_restart:
            logger.info("创建重启标志，等待start.py重启机器人...")
            # 创建重启标志文件
            restart_flag = os.path.join(os.path.dirname(__file__), '.restart_flag')
            with open(restart_flag, 'w') as f:
                f.write(str(time.time()))
                
            # 快速退出，不执行清理操作
            os._exit(0)
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.critical(f"程序发生未处理异常: {e}", exc_info=True)
    finally:
        logger.info("程序完全退出")


if __name__ == "__main__":
    asyncio.run(run_qqbot())