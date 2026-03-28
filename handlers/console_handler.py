# handlers/console_handler.py
# 负责处理控制台输入和命令

import asyncio
import sys
import logging
import threading
import queue
import os
import time
import json
from typing import Dict, Any

from logger_config import get_logger, LOG_LEVEL_MAP
from core.config_manager import reload_config
from utils.api_utils import call_onebot_api

logger = get_logger("ConsoleHandler")

class ConsoleHandler:
    """控制台处理器，负责接收和处理用户输入的命令"""
    
    def __init__(self, context=None):
        self.context = context
        self.should_exit = False
        self.should_restart = False
        self.valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.input_queue = queue.Queue()  # 用于存储用户输入的队列
        self.input_thread = None  # 输入处理线程
        self.current_input = ""  # 当前用户输入的内容
        self.prompt = "> "  # 命令提示符
        self.lock = threading.RLock()  # 用于保护控制台输出的锁
        self.is_input_active = False  # 标记是否有活动的输入行
        self.input_buffer = ""  # 用于实时跟踪用户输入的缓冲区
        
        # 注册日志回调函数，确保日志输出不干扰输入行
        try:
            from logger_config import register_log_callbacks
            register_log_callbacks(
                pre_callback=self._pre_log_output,
                post_callback=self._post_log_output
            )
        except ImportError:
            logger.warning("无法导入日志回调函数，日志输出可能会干扰输入行")
    
    def _clear_prompt_line(self):
        """清除当前提示行"""
        columns = 80
        try:
            import shutil
            size = shutil.get_terminal_size(fallback=(80, 24))
            columns = size.columns
        except:
            pass
         
        # 清除整行
        sys.stdout.write("\r" + " " * columns)
        sys.stdout.write("\r")
        sys.stdout.flush()
        self.is_input_active = False
    
    def _input_reader(self):
        """在单独线程中读取用户输入并放入队列"""
        import sys
        if sys.platform == 'win32':
            import msvcrt
        
        while not self.should_exit:
            try:
                # 非Windows使用标准输入
                if sys.platform != 'win32':
                    try:
                        import select
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            line = sys.stdin.readline()
                            if line:
                                cmd = line.strip().lower()
                                if cmd:
                                    self.input_queue.put(cmd)
                    except:
                        pass
                    threading.Event().wait(0.1)
                    continue

                with self.lock:
                    # 显示提示符
                    sys.stdout.write(f"\r{self.prompt}")
                    if self.input_buffer:  # 如果有缓存的输入，立即恢复显示
                        sys.stdout.write(self.input_buffer)
                    sys.stdout.flush()
                    self.is_input_active = True
                
                # 逐字符读取输入，实时跟踪用户输入内容
                self.input_buffer = ""
                line = ""
                while True:
                    if msvcrt.kbhit():
                        char = msvcrt.getch().decode('utf-8', errors='replace')
                        
                        if char == '\r':  # 回车键
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            line = self.input_buffer
                            self.input_buffer = ""  # 清除缓冲区
                            break
                        elif char == '\b':  # 退格键
                            if self.input_buffer:
                                self.input_buffer = self.input_buffer[:-1]
                                # 更新显示
                                with self.lock:
                                    sys.stdout.write(f"\r{self.prompt}{self.input_buffer} ")
                                    sys.stdout.write(f"\r{self.prompt}{self.input_buffer}")
                                    sys.stdout.flush()
                        else:
                            self.input_buffer += char
                            # 立即显示输入的字符
                            sys.stdout.write(char)
                            sys.stdout.flush()
                    
                    # 短暂检查是否需要退出
                    if self.should_exit:
                        break
                    threading.Event().wait(0.01)  # 短暂等待，减少CPU占用
                
                if line and not self.should_exit:
                    # 将命令放入队列进行处理
                    self.input_queue.put(line.strip().lower())
                    
            except Exception as e:
                if self.should_exit:
                    break
                logger.error(f"输入读取线程错误: {e}")
                # 短暂暂停后继续
                threading.Event().wait(0.1)
    
    async def handle_console_input(self):
        """处理控制台输入命令"""
        # 启动输入读取线程
        self.input_thread = threading.Thread(target=self._input_reader, daemon=True)
        self.input_thread.start()
        
        try:
            while not self.should_exit:
                try:
                    # 检查队列中是否有输入，使用非阻塞方式
                    try:
                        line = self.input_queue.get_nowait()
                        if line:
                            # 处理命令
                            await self._process_command(line)
                            # 命令处理完成后，输入线程会自动显示新的提示符
                    except queue.Empty:
                        # 队列为空，短暂等待后继续
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"处理控制台输入时出错: {e}")
                    # 错误处理完成后，输入线程会自动显示新的提示符
        finally:
            # 确保退出时设置标志
            self.should_exit = True
            if self.input_thread and self.input_thread.is_alive():
                # 等待输入线程结束
                self.input_thread.join(timeout=1.0)
    
    def _pre_log_output(self):
        """日志输出前的处理"""
        with self.lock:
            # 保存当前输入行状态
            if self.is_input_active:
                try:
                    # 在输出日志前，先清除当前输入行
                    self._clear_prompt_line()
                except Exception:
                    pass  # 忽略可能的错误
    
    def _post_log_output(self):
        """日志输出后的处理"""
        with self.lock:
            try:
                # 在新行显示提示符
                sys.stdout.write(f"\r{self.prompt}")
                # 立即恢复用户正在输入的内容
                if self.input_buffer:
                    sys.stdout.write(self.input_buffer)
                sys.stdout.flush()
                self.is_input_active = True
            except Exception:
                # 如果出现错误，至少确保提示符被重新显示
                try:
                    sys.stdout.write(f"\r{self.prompt}")
                    if self.input_buffer:
                        sys.stdout.write(self.input_buffer)
                    sys.stdout.flush()
                    self.is_input_active = True
                except Exception:
                    pass  # 忽略所有错误
    
    async def _process_command(self, command: str):
        """处理单个命令"""
        if command in ["exit", "quit", "q", "stop"]:
            await self._handle_exit()
        elif command == "reload":
            await self._handle_reload()
        elif command.startswith("log "):
            await self._handle_log_level(command)
        elif command in ["restart", "rst"]:
            await self._handle_restart()
        elif command == "help" or command == "h":
            self._show_help()
        elif command.startswith("ws send "):
            await self._handle_ws_send(command)

        elif command.startswith("plugin ") or command.startswith("pl "):
            await self._handle_plugin(command)
        else:
            logger.warning(f"未知命令: {command}，输入 'help' 查看可用命令")
    
    async def _handle_exit(self):
        """处理退出命令"""
        logger.info("收到退出命令，正在关闭程序...")
        self.should_exit = True
        # 直接终止程序，不进行任何清理
        os._exit(0)
    
    async def _handle_reload(self):
        """处理重新加载配置命令"""
        logger.info("收到重新加载配置命令")
        try:
            reload_config()
            logger.info("配置重新加载完成")
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
    
    async def _handle_log_level(self, command: str):
        """处理日志级别切换命令"""
        try:
            _, level = command.split(" ", 1)
            level = level.upper()
            
            if level in self.valid_log_levels:
                # 更新配置文件中的日志级别
                import yaml
                import os
                
                # 读取配置文件
                config_file_path = os.path.join(os.getcwd(), 'config.yml')
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                # 更新日志级别
                config['log_level'] = level
                
                # 写回配置文件
                with open(config_file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                
                # 更新所有logger的级别
                root_logger = logging.getLogger()
                new_level = LOG_LEVEL_MAP[level]
                root_logger.setLevel(new_level)
                
                # 更新所有处理器的级别
                for handler in root_logger.handlers:
                    handler.setLevel(new_level)
                
                logger.info(f"日志级别已切换为: {level}")
            else:
                logger.error(f"无效的日志级别: {level}，有效级别为: {', '.join(self.valid_log_levels)}")
        except Exception as e:
            logger.error(f"切换日志级别时出错: {e}")
    
    async def _handle_restart(self):
        """处理重启命令"""
        logger.info("收到重启命令，正在准备重启...")
        self.should_restart = True
        self.should_exit = True
        # 创建重启标志文件并快速退出
        restart_flag = os.path.join(os.path.dirname(__file__), '..', '.restart_flag')
        with open(restart_flag, 'w') as f:
            f.write(str(time.time()))
        os._exit(0)
    
    async def _handle_ws_send(self, command: str):
        """处理WebSocket发送命令"""
        try:
            # 解析命令，提取JSON内容
            json_str = command[7:].strip()
            if not json_str:
                logger.error("命令格式错误: ws send 后面需要接JSON内容")
                return
            
            # 解析JSON
            ws_message = json.loads(json_str)
            
            # 验证消息格式
            if "action" not in ws_message:
                logger.error("WebSocket消息缺少必填字段: action")
                return
            
            action = ws_message.get("action")
            params = ws_message.get("params", {})
            
            # 检查上下文
            if not self.context:
                logger.error("上下文未初始化，无法发送消息")
                return
            
            print(f"\n[控制台] 正在发送HTTP API请求:")
            print(f"  Action: {action}")
            print(f"  Params: {json.dumps(params, indent=2, ensure_ascii=False)}")
            
            # 使用 HTTP API 发送请求
            response = await call_onebot_api(self.context, action, params)
            
            if response:
                if response.get('success'):
                    print(f"\n[控制台] 收到HTTP API响应:")
                    print(json.dumps(response, indent=2, ensure_ascii=False))
                else:
                    print(f"\n[控制台] HTTP API请求失败:")
                    print(f"  错误: {response.get('error', '未知错误')}")
            else:
                print(f"\n[控制台] HTTP API请求无响应")
            print()
        except json.JSONDecodeError as e:
            logger.error(f"JSON格式错误: {e}")
        except Exception as e:
            logger.error(f"处理ws send命令时出错: {e}")
    




    async def _handle_plugin(self, command: str):
        """处理plugin系列命令"""
        try:
            # 解析命令
            parts = command.split()
            if len(parts) < 2:
                print("\n命令格式错误: plugin 后面需要接子命令")
                print("可用子命令: list, load, unload, reload, enable, disable")
                return
            
            sub_cmd = parts[1]
            
            # 检查是否有plugin_manager
            if not self.context or not hasattr(self.context, 'plugin_manager'):
                print("\n错误: 插件管理器未初始化")
                return
            
            plugin_manager = self.context.plugin_manager
            
            if sub_cmd == "list":
                await self._handle_plugin_list(plugin_manager)
            elif sub_cmd == "unload":
                if len(parts) < 3:
                    print("\n命令格式错误: plugin unload 后面需要接插件名称")
                    return
                plugin_name = parts[2]
                await self._handle_plugin_unload(plugin_manager, plugin_name)
            elif sub_cmd == "load":
                if len(parts) < 3:
                    print("\n命令格式错误: plugin load 后面需要接插件名称")
                    return
                plugin_name = parts[2]
                await self._handle_plugin_load(plugin_manager, plugin_name)
            elif sub_cmd == "reload":
                if len(parts) < 3:
                    print("\n命令格式错误: plugin reload 后面需要接插件名称")
                    return
                plugin_name = parts[2]
                await self._handle_plugin_reload(plugin_manager, plugin_name)
            elif sub_cmd == "enable":
                if len(parts) < 3:
                    print("\n命令格式错误: plugin enable 后面需要接插件名称")
                    return
                plugin_name = parts[2]
                await self._handle_plugin_enable(plugin_manager, plugin_name)
            elif sub_cmd == "disable":
                if len(parts) < 3:
                    print("\n命令格式错误: plugin disable 后面需要接插件名称")
                    return
                plugin_name = parts[2]
                await self._handle_plugin_disable(plugin_manager, plugin_name)
            else:
                print(f"\n未知子命令: {sub_cmd}")
                print("可用子命令: list, load, unload, reload, enable, disable")
        except Exception as e:
            logger.error(f"处理plugin命令时发生错误: {str(e)}")
            print(f"\n处理命令时发生错误: {str(e)}")

    async def _handle_plugin_list(self, plugin_manager):
        """处理plugin list命令"""
        import os
        print("\n正在扫描插件列表和运行状态...")
        
        # 实时扫描插件目录
        plugins_dir = os.path.join(os.path.dirname(__file__), '..', 'plugins')
        available_plugins = []
        
        if os.path.exists(plugins_dir):
            for item in os.listdir(plugins_dir):
                item_path = os.path.join(plugins_dir, item)
                if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'plugin.yml')):
                    available_plugins.append(item)
        
        # 获取所有插件
        all_plugins = plugin_manager.list_plugins()
        
        # 显示结果
        print("\n插件列表及运行状态:")
        print("-" * 50)
        
        if not available_plugins and not all_plugins:
            print("  未发现可用的插件")
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
                
                print(f"  {plugin_name} v{version}: {status}")
        print("-" * 50)

    async def _handle_plugin_unload(self, plugin_manager, plugin_name):
        """处理plugin unload命令"""
        print(f"\n正在卸载插件: {plugin_name}...")
        
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if not plugin_info:
            print(f"  插件 {plugin_name} 未加载")
            return
        
        # 卸载插件
        success = await plugin_manager.unload(plugin_name)
        
        if success:
            print(f"  插件 {plugin_name} 已成功卸载")
        else:
            print(f"  卸载插件 {plugin_name} 失败")

    async def _handle_plugin_load(self, plugin_manager, plugin_name):
        """处理plugin load命令"""
        import os
        print(f"\n正在加载插件: {plugin_name}...")
        
        # 检查插件是否存在
        plugin_path = os.path.join(os.path.dirname(__file__), '..', 'plugins', plugin_name)
        if not os.path.exists(plugin_path) or not os.path.exists(os.path.join(plugin_path, 'plugin.yml')):
            print(f"  插件 {plugin_name} 不存在")
            return
        
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if plugin_info:
            print(f"  插件 {plugin_name} 已经加载")
            return
        
        # 加载插件
        success = await plugin_manager.load(plugin_name)
        
        if success:
            print(f"  插件 {plugin_name} 已成功加载")
        else:
            print(f"  加载插件 {plugin_name} 失败")

    async def _handle_plugin_reload(self, plugin_manager, plugin_name):
        """处理plugin reload命令"""
        import os
        print(f"\n正在重载插件: {plugin_name}...")
        
        # 检查插件是否存在
        plugin_path = os.path.join(os.path.dirname(__file__), '..', 'plugins', plugin_name)
        if not os.path.exists(plugin_path) or not os.path.exists(os.path.join(plugin_path, 'plugin.yml')):
            print(f"  插件 {plugin_name} 不存在")
            return
        
        # 重载插件
        success = await plugin_manager.reload(plugin_name)
        
        if success:
            print(f"  插件 {plugin_name} 已成功重载")
        else:
            print(f"  重载插件 {plugin_name} 失败")

    async def _handle_plugin_enable(self, plugin_manager, plugin_name):
        """处理plugin enable命令"""
        print(f"\n正在启用插件: {plugin_name}...")
        
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if not plugin_info:
            print(f"  插件 {plugin_name} 未加载")
            return
        
        # 启用插件
        success = await plugin_manager.enable(plugin_name)
        
        if success:
            print(f"  插件 {plugin_name} 已成功启用")
        else:
            print(f"  启用插件 {plugin_name} 失败")

    async def _handle_plugin_disable(self, plugin_manager, plugin_name):
        """处理plugin disable命令"""
        print(f"\n正在禁用插件: {plugin_name}...")
        
        # 检查插件是否已加载
        plugin_info = plugin_manager.get_plugin_info(plugin_name)
        if not plugin_info:
            print(f"  插件 {plugin_name} 未加载")
            return
        
        # 禁用插件
        success = await plugin_manager.disable(plugin_name)
        
        if success:
            print(f"  插件 {plugin_name} 已成功禁用")
        else:
            print(f"  禁用插件 {plugin_name} 失败")

    def _show_help(self):
        """显示帮助信息"""
        print("\n可用命令:")
        print("  exit/quit/q/stop - 立即退出程序")
        print("  reload           - 重新加载配置")
        print("  log <级别>       - 切换日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)")
        print("  restart/rst      - 立即重启机器人")
        print("  ws send <json>   - 发送HTTP API消息")
        print("  plugin list      - 查看插件列表和运行状态")
        print("  plugin load <name> - 加载插件")
        print("  plugin unload <name> - 卸载插件")
        print("  plugin reload <name> - 重载插件")
        print("  plugin enable <name> - 启用插件")
        print("  plugin disable <name> - 禁用插件")
        print("  help/h           - 显示此帮助信息")
        print()
        print("示例:")
        print("  ws send {\"action\":\"get_stranger_info\",\"params\":{\"user_id\":123456789}}")
        print("  plugin list")
        print("  plugin load example_plugin")
    
    def reset_flags(self):
        """重置状态标志"""
        self.should_exit = False
        self.should_restart = False
        # 清空输入队列
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break