# start.py - 启动脚本
# 作为机器人的主入口，负责启动和监控bot.py子进程

import os
import sys
import subprocess
import time
import signal
import platform

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.join(PROJECT_ROOT, 'runtime')
BUNDLED_PYTHON = os.path.join(RUNTIME_DIR, 'python31211', 'bin', 'python.exe')
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, 'requirements.txt')

RESTART_FLAG = os.path.join(PROJECT_ROOT, '.restart_flag')


def get_python_executable():
    """获取Python解释器路径"""
    is_windows = sys.platform == 'win32'
    bundled_exists = os.path.exists(BUNDLED_PYTHON)
    venv_dir = os.path.join(PROJECT_ROOT, 'venv')
    venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe') if is_windows else os.path.join(venv_dir, 'bin', 'python')

    if os.path.exists(venv_python):
        print(f"检测到虚拟环境，使用虚拟环境Python: {venv_python}")
        return venv_python

    if is_windows and bundled_exists:
        return BUNDLED_PYTHON

    print("未找到自带runtime或虚拟环境，正在创建uv虚拟环境...")

    uv_path = None
    for cmd in ['uv', 'uv.exe']:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                uv_path = cmd
                print(f"找到uv: {result.stdout.strip()}")
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if not uv_path:
        print("未找到uv，正在使用pip创建虚拟环境...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True, timeout=120)
            print(f"虚拟环境创建成功: {venv_dir}")
            return venv_python
        except subprocess.CalledProcessError as e:
            print(f"创建虚拟环境失败: {e}")
            sys.exit(1)

    try:
        subprocess.run(
            [uv_path, 'venv', venv_dir],
            check=True,
            timeout=120
        )
        print(f"uv虚拟环境创建成功: {venv_dir}")
        return venv_python
    except subprocess.CalledProcessError as e:
        print(f"创建uv虚拟环境失败: {e}")
        sys.exit(1)


def install_dependencies(python_executable):
    """安装项目依赖"""
    if not os.path.exists(REQUIREMENTS_FILE):
        print("警告: requirements.txt 不存在，跳过依赖安装")
        return

    print("正在检查并安装依赖...")

    is_windows = sys.platform == 'win32'
    venv_dir = os.path.join(PROJECT_ROOT, 'venv')
    venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe') if is_windows else os.path.join(venv_dir, 'bin', 'python')
    is_venv = python_executable == venv_python

    for cmd in ['uv', 'uv.exe']:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"使用uv安装依赖...")
                try:
                    if is_venv:
                        subprocess.run(
                            [cmd, 'pip', 'install', '--python', python_executable, '-r', REQUIREMENTS_FILE],
                            check=True,
                            timeout=300
                        )
                    else:
                        subprocess.run(
                            [cmd, 'pip', 'install', '-r', REQUIREMENTS_FILE],
                            check=True,
                            timeout=300
                        )
                    print("依赖安装完成!")
                    return
                except subprocess.CalledProcessError as e:
                    print(f"uv pip安装失败，尝试uv直接安装: {e}")
                    try:
                        if is_venv:
                            subprocess.run(
                                [cmd, 'install', '--python', python_executable, '-r', REQUIREMENTS_FILE],
                                check=True,
                                timeout=300
                            )
                        else:
                            subprocess.run(
                                [cmd, 'install', '-r', REQUIREMENTS_FILE],
                                check=True,
                                timeout=300
                            )
                        print("依赖安装完成!")
                        return
                    except subprocess.CalledProcessError as e2:
                        print(f"uv直接安装也失败: {e2}")
                        break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    pip_cmd = [python_executable, '-m', 'pip']

    if is_venv:
        for cmd in ['uv', 'uv.exe']:
            try:
                if is_venv:
                    subprocess.run(
                        [cmd, 'pip', 'install', '--python', python_executable, 'pip', '--upgrade'],
                        check=True,
                        timeout=120
                    )
                else:
                    subprocess.run(
                        [cmd, 'pip', 'install', '--upgrade', 'pip'],
                        check=True,
                        timeout=120
                    )
                print("pip升级完成")
                break
            except:
                continue
        else:
            print("虚拟环境无pip，尝试安装pip...")
            try:
                import ensurepip
                subprocess.run([python_executable, '-m', 'ensurepip', '--upgrade'], check=True, timeout=60)
            except:
                try:
                    bootstrap_url = 'https://bootstrap.pypa.io/get-pip.py'
                    get_pip_script = os.path.join(PROJECT_ROOT, 'get-pip.py')
                    subprocess.run(
                        [sys.executable, '-c', f'import urllib.request; urllib.request.urlretrieve("{bootstrap_url}", "{get_pip_script}")'],
                        check=True,
                        timeout=30
                    )
                    subprocess.run([python_executable, get_pip_script], check=True, timeout=60)
                    if os.path.exists(get_pip_script):
                        os.remove(get_pip_script)
                except Exception as e:
                    print(f"安装pip失败: {e}")

    try:
        subprocess.run(
            pip_cmd + ['install', '-r', REQUIREMENTS_FILE],
            check=True,
            timeout=300
        )
        print("依赖安装完成!")
    except subprocess.CalledProcessError as e:
        print(f"安装依赖失败: {e}")
        sys.exit(1)


def is_psutil_available():
    """检查psutil是否可用"""
    try:
        import psutil
        return True
    except ImportError:
        return False

def print_startup_art():
    """打印启动时的粉红色ASCII艺术字"""
    if '--no_colorama' in sys.argv:
        # 使用 Linux 原生 ANSI 颜色码
        magenta = '\033[95m'
        reset = '\033[0m'
    else:
        # 使用 colorama
        try:
            import colorama
            colorama.init()
            from colorama import Fore, Style
            magenta = Fore.MAGENTA
            reset = Style.RESET_ALL
        except ImportError:
            # 如果没有安装colorama，定义空的样式类
            class Fore:
                MAGENTA = ''
                RESET = ''
            class Style:
                RESET_ALL = ''
            magenta = ''
            reset = ''
    
    art = f"""{magenta}________  __    __  _______                       __                    __            ________               _____                         
/        |/  |  /  |/       \\                     /  |                  /  |          /        |             /     |                        
$$$$$$$$/ $$ |  $$ |$$$$$$$  |  ______    ______  $$ |____    ______   _$$ |_         $$$$$$$$/   ______     $$$$$ |  ______   _____  ____  
    /$$/  $$ |__$$ |$$ |__$$ | /      \\  /      \\ $$      \\  /      \\ / $$   |           $$ |    /      \\       $$ | /      \\ /     \\/    \\ 
   /$$/   $$    $$ |$$    $$< /$$$$$$  |/$$$$$$  |$$$$$$$  |/$$$$$$  |$$$$$$/            $$ |   /$$$$$$  | __   $$ | $$$$$$  |$$$$$$ $$$$  |
  /$$/    $$$$$$$$ |$$$$$$$  |$$ |  $$/ $$ |  $$ |$$ |  $$ |$$ |  $$ |  $$ | __          $$ |   $$ |  $$/ /  |  $$ | /    $$ |$$ | $$ | $$ |
 /$$/____ $$ |  $$ |$$ |  $$ |$$ |      $$ \\__$$ |$$ |__$$ |$$ \\__$$ |  $$ |/  |         $$ |   $$ |      $$ \\__$$ |/$$$$$$$ |$$ | $$ | $$ |
/$$      |$$ |  $$ |$$ |  $$ |$$ |      $$    $$/ $$    $$/ $$    $$/   $$  $$/          $$ |   $$ |      $$    $$/ $$    $$ |$$ | $$ | $$ |
$$$$$$$$/ $$/   $$/ $$/   $$/ $$/        $$$$$$/  $$$$$$$/   $$$$$$/     $$$$/           $$/    $$/        $$$$$$/   $$$$$$$/ $$/  $$/  $$/ 
                                                                                                                                           
                                                                                                                                           
                                                                                                                                           {reset}"""
    
    print(art)

def setup_signal_handler():
    """设置信号处理器，用于优雅退出"""
    def signal_handler(sig, frame):
        print("\n收到退出信号，正在停止机器人...")
        if 'bot_process' in globals() and is_psutil_available():
            try:
                import psutil
                if sys.platform == 'win32':
                    os.kill(bot_process.pid, signal.CTRL_BREAK_EVENT)
                else:
                    bot_process.terminate()
                bot_process.wait(timeout=1)
            except:
                try:
                    bot_process.kill()
                except:
                    pass
        cleanup_all_child_processes()
        sys.exit(0)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Windows特有的信号
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal_handler)

def cleanup_all_child_processes():
    """清理所有子进程"""
    if not is_psutil_available():
        return

    try:
        import psutil
        current_process = psutil.Process()
        children = current_process.children(recursive=True)

        if children:
            print(f"发现 {len(children)} 个子进程，正在清理...")

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            gone, still_alive = psutil.wait_procs(children, timeout=1)

            for child in still_alive:
                try:
                    if platform.system() == 'Windows':
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(child.pid)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=1)
                    else:
                        child.kill()
                except (psutil.NoSuchProcess, subprocess.SubprocessError, subprocess.TimeoutExpired):
                    pass

            psutil.wait_procs(still_alive, timeout=0.5)

            print("子进程清理完成")
    except Exception as e:
        print(f"清理子进程时出错: {e}")

def start_bot(python_executable):
    """启动bot.py子进程"""
    global bot_process

    if os.path.exists(RESTART_FLAG):
        try:
            os.remove(RESTART_FLAG)
        except:
            pass

    bot_script = os.path.join(PROJECT_ROOT, 'bot.py')
    cmd = [python_executable, bot_script] + sys.argv[1:]

    print(f"启动机器人: {' '.join(cmd)}")

    bot_process = subprocess.Popen(
        cmd,
        stdout=None,
        stderr=None
    )

    return bot_process

def main():
    """主函数"""
    print_startup_art()
    print("ZHRrobot 启动器")
    print("输入 Ctrl+C 退出")

    python_executable = get_python_executable()
    install_dependencies(python_executable)

    setup_signal_handler()

    while True:
        process = start_bot(python_executable)
        
        # 更快速地检测子进程结束和重启标志
        restart_requested = False
        while process.poll() is None and not restart_requested:
            # 每100ms检查一次进程状态和重启标志
            time.sleep(0.1)
            if os.path.exists(RESTART_FLAG):
                restart_requested = True
                # 尝试快速终止进程
                try:
                    process.terminate()
                    # 等待最多0.5秒
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    # 如果进程没有及时终止，强制杀死
                    try:
                        process.kill()
                    except:
                        pass
        
        # 等待子进程完全结束
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except:
                pass
            process.wait()
        
        # 检查子进程的退出码或重启标志文件
        if os.path.exists(RESTART_FLAG) or restart_requested:
            print("检测到重启请求，正在重新启动机器人...")
            # 短暂延迟，确保资源释放
            time.sleep(0.5)
        else:
            print("机器人已停止，无重启请求")
            break
    
    # 程序退出前清理所有子进程
    cleanup_all_child_processes()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n收到键盘中断信号")
    except Exception as e:
        print(f"发生未预期的错误: {e}")
    finally:
        # 确保最终清理所有子进程
        cleanup_all_child_processes()