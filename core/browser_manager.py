import asyncio
import os
import platform
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page

# 导入浏览器配置
from browser_config import get_browser_manager_config


class BrowserManager:
    """
    浏览器管理器 - 负责管理Playwright浏览器实例的生命周期，实现浏览器常驻后台
    支持使用系统浏览器（如Edge、Chrome）或Playwright内置浏览器
    """
    
    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._lock = asyncio.Lock()
        self._pages = set()  # 跟踪所有创建的页面
        
        # 从配置文件加载设置
        config = get_browser_manager_config()
        self.use_system_browser = config.get("use_system_browser", True)
        self.browser_type = config.get("browser_type", "msedge")
        self.headless = config.get("headless", True)
        self.system_browser_paths = self._get_system_browser_paths()
    
    def _get_system_browser_paths(self) -> dict:
        """获取系统浏览器的默认安装路径"""
        system = platform.system()
        paths = {}
        
        if system == "Windows":
            # Windows系统浏览器路径
            paths.update({
                "msedge": [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")
                ],
                "chrome": [
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
                ],
                "firefox": [
                    r"C:\Program Files\Mozilla Firefox\firefox.exe",
                    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
                ]
            })
        elif system == "Darwin":  # macOS
            paths.update({
                "msedge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
                "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
                "firefox": ["/Applications/Firefox.app/Contents/MacOS/firefox"]
            })
        elif system == "Linux":
            paths.update({
                "msedge": ["/usr/bin/microsoft-edge", "/usr/bin/edge"],
                "chrome": ["/usr/bin/google-chrome", "/usr/bin/chrome"],
                "firefox": ["/usr/bin/firefox"]
            })
        
        return paths
    
    def _find_system_browser(self) -> Optional[str]:
        """查找系统中可用的浏览器可执行文件路径"""
        if self.browser_type in self.system_browser_paths:
            for path in self.system_browser_paths[self.browser_type]:
                if os.path.exists(path):
                    return path
        return None
    
    async def init_browser(self):
        """
        初始化浏览器实例
        """
        async with self._lock:
            if self._browser is None:
                self._playwright = await async_playwright().start()
                
                launch_kwargs = {
                    "headless": self.headless,
                    "args": [
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-extensions',
                        '--disable-features=site-per-process',
                        '--js-flags=--max-old-space-size=512',
                    ],
                    "chromium_sandbox": False,
                    "ignore_default_args": ['--enable-automation'],
                }
                
                browser_started = False
                last_error = None
                
                # 如果配置使用系统浏览器
                if self.use_system_browser:
                    system_browser_path = self._find_system_browser()
                    
                    if system_browser_path and os.path.exists(system_browser_path):
                        print(f"使用系统浏览器: {system_browser_path}")
                        launch_kwargs["executable_path"] = system_browser_path
                        try:
                            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
                            browser_started = True
                        except Exception as e:
                            print(f"使用系统浏览器失败: {e}")
                            last_error = e
                    
                    if not browser_started:
                        channel_map = {
                            "msedge": "msedge",
                            "chrome": "chrome",
                            "firefox": "firefox"
                        }
                        if self.browser_type in channel_map:
                            print(f"尝试使用系统浏览器渠道: {channel_map[self.browser_type]}")
                            launch_kwargs["channel"] = channel_map[self.browser_type]
                            try:
                                self._browser = await self._playwright.chromium.launch(**launch_kwargs)
                                browser_started = True
                            except Exception as e:
                                print(f"使用渠道 {channel_map[self.browser_type]} 失败: {e}")
                                last_error = e
                
                if not browser_started:
                    print("使用Playwright内置浏览器")
                    try:
                        self._browser = await self._playwright.chromium.launch(
                            headless=self.headless,
                            args=[
                                '--disable-gpu',
                                '--disable-dev-shm-usage',
                                '--disable-extensions',
                                '--disable-features=site-per-process',
                                '--js-flags=--max-old-space-size=512',
                            ],
                            chromium_sandbox=False,
                            ignore_default_args=['--enable-automation'],
                        )
                    except Exception as e:
                        print(f"启动Playwright内置浏览器也失败: {e}")
                        print("正在尝试安装Playwright Chromium浏览器...")
                        try:
                            import subprocess
                            import sys
                            subprocess.run(
                                [sys.executable, '-m', 'playwright', 'install', 'chromium'],
                                check=True,
                                timeout=300
                            )
                            self._browser = await self._playwright.chromium.launch(
                                headless=self.headless,
                                args=[
                                    '--disable-gpu',
                                    '--disable-dev-shm-usage',
                                    '--disable-extensions',
                                    '--disable-features=site-per-process',
                                    '--js-flags=--max-old-space-size=512',
                                ],
                                chromium_sandbox=False,
                                ignore_default_args=['--enable-automation'],
                            )
                            print("Playwright Chromium浏览器安装并启动成功!")
                        except Exception as install_error:
                            print(f"安装Playwright浏览器失败: {install_error}")
                            raise
                
                print(f"浏览器实例已启动并常驻后台 (使用{'系统' if self.use_system_browser and browser_started else '内置'}浏览器)")
    
    async def get_page(self) -> Page:
        """
        获取一个新的页面实例
        """
        await self.init_browser()
        page = await self._browser.new_page()
        self._pages.add(page)
        return page
    
    async def close_page(self, page: Page):
        """
        关闭指定的页面
        """
        if page in self._pages:
            await page.close()
            self._pages.remove(page)
    
    async def close_all_pages(self):
        """
        关闭所有页面
        """
        for page in list(self._pages):
            await self.close_page(page)
    
    async def shutdown(self):
        """
        关闭浏览器实例并清理资源
        """
        async with self._lock:
            if self._browser:
                try:
                    # 设置超时时间，避免在关闭时卡住
                    await asyncio.wait_for(self.close_all_pages(), timeout=5.0)
                except asyncio.TimeoutError:
                    print("警告: 关闭浏览器页面超时")
                
                try:
                    # 关闭浏览器实例，设置超时时间
                    await asyncio.wait_for(self._browser.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    print("警告: 关闭浏览器实例超时")
                
                try:
                    # 停止playwright，设置超时时间
                    await asyncio.wait_for(self._playwright.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    print("警告: 停止Playwright超时")
                
                self._browser = None
                self._playwright = None
                print("浏览器实例已关闭")
    
    @property
    def is_initialized(self) -> bool:
        """
        检查浏览器是否已初始化
        """
        return self._browser is not None
    
    def get_browser_info(self) -> dict:
        """获取当前浏览器配置信息"""
        return {
            "use_system_browser": self.use_system_browser,
            "browser_type": self.browser_type,
            "headless": self.headless,
            "is_initialized": self.is_initialized
        }


# 创建全局浏览器管理器实例
browser_manager = BrowserManager()


async def ensure_browser_initialized():
    """
    确保浏览器已初始化
    """
    await browser_manager.init_browser()


async def cleanup_browser():
    """
    清理浏览器资源
    """
    try:
        await asyncio.wait_for(browser_manager.shutdown(), timeout=15.0)
    except asyncio.TimeoutError:
        print("错误: 清理浏览器资源超时")