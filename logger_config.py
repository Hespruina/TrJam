import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

# 全局回调函数，用于在日志输出前后处理控制台状态
_pre_log_callbacks = []
_post_log_callbacks = []
_callbacks_lock = threading.Lock()

# 全局标志，控制是否禁用 colorama
_no_colorama = False

def set_no_colorama(value: bool):
    """设置是否禁用 colorama"""
    global _no_colorama
    _no_colorama = value

def is_no_colorama() -> bool:
    """获取是否禁用 colorama"""
    return _no_colorama

# 👇 启用 colorama 以支持 Windows 颜色显示
try:
    import colorama
    if not _no_colorama:
        colorama.init()
except ImportError:
    # 如果没有安装 colorama，忽略颜色（不中断程序）
    class MockColorama:
        @staticmethod
        def init():
            pass
    colorama = MockColorama()


# 自定义控制台处理器，支持在日志输出前后执行回调
class CustomConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        # 在输出日志前执行所有预回调
        with _callbacks_lock:
            for callback in _pre_log_callbacks:
                try:
                    callback()
                except Exception:
                    pass  # 忽略回调中的错误
        
        # 正常输出日志
        super().emit(record)
        
        # 在输出日志后执行所有后回调
        with _callbacks_lock:
            for callback in _post_log_callbacks:
                try:
                    callback()
                except Exception:
                    pass  # 忽略回调中的错误

# 注册日志回调函数的接口
def register_log_callbacks(pre_callback=None, post_callback=None):
    """
    注册日志输出前后的回调函数
    :param pre_callback: 日志输出前的回调函数
    :param post_callback: 日志输出后的回调函数
    """
    with _callbacks_lock:
        if pre_callback and callable(pre_callback):
            _pre_log_callbacks.append(pre_callback)
        if post_callback and callable(post_callback):
            _post_log_callbacks.append(post_callback)

# 彩色日志格式化器（仅在终端启用颜色）
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[90m',      # 灰色
        'INFO': '\033[38;2;243;238;210m',  # 浅紫色 #f3eed2
        'SUCCESS': '\033[92m',    # 绿色
        'WARNING': '\033[93m',    # 黄色
        'ERROR': '\033[91m',      # 红色
        'CRITICAL': '\033[41m',   # 红底白字
        'WHITE': '\033[97m',      # 白色
        'SKY_BLUE': '\033[96m',   # 天蓝色
        'RESET': '\033[0m'
    }

    def __init__(self, fmt, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        # 仅当输出到终端时启用颜色
        self.use_color = sys.stdout.isatty()

    def format(self, record):
        # 先获取格式化后的消息
        message = record.getMessage()
        
        # 格式化时间
        asctime = self.formatTime(record, self.datefmt)
        
        if self.use_color:
            # 添加 SUCCESS 级别支持
            if record.levelname == 'SUCCESS':
                record.levelname = 'INFO'
                color = self.COLORS['SUCCESS']
            else:
                color = self.COLORS.get(record.levelname, self.COLORS['INFO'])

            # 构建格式化输出
            # 月-日（白色） 时:分:秒（白色） [模块（颜色取决于level）] 正文
            date_part = asctime.split(' ')
            if len(date_part) >= 2:
                date_str = date_part[0]  # 月-日
                time_str = date_part[1]  # 时:分:秒
            else:
                date_str = asctime
                time_str = ''
            
            # 使用白色显示日期和时间
            white = self.COLORS['WHITE']
            reset = self.COLORS['RESET']
            
            # 组合最终格式
            formatted = f"{white}{date_str} {time_str}{reset} {color}[{record.name}]{reset} {message}"
        else:
            # 不使用颜色时的格式
            formatted = f"{asctime} [{record.name}] {message}"
        
        return formatted


# 定义日志格式
LOG_FORMAT = '%(asctime)s %(name)s %(message)s'
DATE_FORMAT = '%m-%d %H:%M:%S'

# 创建日志目录
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)

# 创建自定义控制台处理器（带颜色）
console_handler = CustomConsoleHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter(LOG_FORMAT, DATE_FORMAT))

# 创建文件处理器（无颜色，纯文本，轮转）
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'app.log'),
    maxBytes=1024 * 1024 * 5,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# 设置默认日志级别为最低级别(DEBUG)，确保所有日志都能被记录
# 然后在get_logger函数中根据配置动态调整每个logger的级别
DEFAULT_LOG_LEVEL = logging.DEBUG

# 设置根日志配置为DEBUG级别
logging.basicConfig(
    level=DEFAULT_LOG_LEVEL,
    handlers=[console_handler, file_handler]
)

# 日志级别映射
LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# 获取配置的日志级别的函数
def _get_configured_log_level():
    try:
        # 动态导入以避免循环依赖
        from core.config_manager import load_config
        config = load_config()
        log_level_str = config.get('log_level', 'INFO').upper()
        return LOG_LEVEL_MAP.get(log_level_str, logging.INFO)
    except ImportError:
        # 如果无法导入配置管理器，使用默认日志级别
        return logging.INFO

# 控制第三方库的日志级别

def _configure_third_party_loggers():
    """配置第三方库的日志级别，避免大量debug日志输出"""
    # 抑制matplotlib的debug日志
    matplotlib_logger = logging.getLogger('matplotlib')
    matplotlib_logger.setLevel(logging.WARNING)
    matplotlib_logger = logging.getLogger('matplotlib.font_manager')
    matplotlib_logger.setLevel(logging.WARNING)
    
    # 抑制PIL的debug日志
    pil_logger = logging.getLogger('PIL')
    pil_logger.setLevel(logging.WARNING)
    pil_logger = logging.getLogger('PIL.PngImagePlugin')
    pil_logger.setLevel(logging.WARNING)
    
    # 抑制urllib3的debug日志
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.WARNING)
    urllib3_logger = logging.getLogger('urllib3.connectionpool')
    urllib3_logger.setLevel(logging.WARNING)
    
    # 抑制httpcore的debug日志
    httpcore_logger = logging.getLogger('httpcore')
    httpcore_logger.setLevel(logging.WARNING)
    httpcore_logger = logging.getLogger('httpcore.connection')
    httpcore_logger.setLevel(logging.WARNING)
    httpcore_logger = logging.getLogger('httpcore.http11')
    httpcore_logger.setLevel(logging.WARNING)
    
    # 抑制httpx的debug日志
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.setLevel(logging.WARNING)
    
    # 抑制peewee的debug日志
    peewee_logger = logging.getLogger('peewee')
    peewee_logger.setLevel(logging.WARNING)
    
    # 抑制playwright的debug日志
    playwright_logger = logging.getLogger('playwright')
    playwright_logger.setLevel(logging.WARNING)
    
    # 抑制sqlalchemy的debug日志
    sqlalchemy_logger = logging.getLogger('sqlalchemy')
    sqlalchemy_logger.setLevel(logging.WARNING)
    
    # 抑制asyncio的debug日志
    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.setLevel(logging.WARNING)
    
    # 抑制aiohttp的debug日志
    aiohttp_logger = logging.getLogger('aiohttp')
    aiohttp_logger.setLevel(logging.WARNING)
    
    # 抑制websockets的debug日志
    websockets_logger = logging.getLogger('websockets')
    websockets_logger.setLevel(logging.WARNING)
    websockets_logger = logging.getLogger('websockets.server')
    websockets_logger.setLevel(logging.WARNING)

# 配置第三方库的日志级别
_configure_third_party_loggers()

# 注册 SUCCESS 级别（复用 INFO 级别值，仅改名）
logging.addLevelName(logging.INFO, 'SUCCESS')

# 为 Logger 类动态添加 .success() 方法
def success(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.INFO):
        self._log(logging.INFO, message, args, **kwargs)

logging.Logger.success = success


# 敏感信息字段列表
sensitive_fields = [
    'access_token',
    'onebot_access_token',
    'api_key',
    'password',
    'token'
]


def _redact_sensitive_info(data, depth=0):
    """
    递归过滤敏感信息
    :param data: 要过滤的数据
    :param depth: 当前递归深度，防止无限递归
    :return: 过滤后的数据
    """
    if depth > 5:  # 限制递归深度，防止栈溢出
        return data
    
    if isinstance(data, dict):
        return {k: (_redact_sensitive_info(v, depth+1) if k.lower() not in sensitive_fields else '***REDACTED***') for k, v in data.items()}
    elif isinstance(data, list):
        return [_redact_sensitive_info(item, depth+1) for item in data]
    else:
        return data


# 公共接口函数
def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器，并应用配置的日志级别
    :param name: 日志记录器名称
    :return: 日志记录器实例
    """
    logger = logging.getLogger(name)
    # 应用配置的日志级别
    logger.setLevel(_get_configured_log_level())
    return logger



def log_exception(logger: logging.Logger, message: str, e: Exception, level: str = 'error', show_traceback: bool = False):
    """
    统一记录异常信息
    :param logger: 日志记录器
    :param message: 自定义消息
    :param e: 异常对象
    :param level: 日志级别 (debug/info/warning/error/critical)
    :param show_traceback: 是否显示完整堆栈跟踪，默认False避免控制台刷屏
    """
    log_func = getattr(logger, level.lower(), logger.error)  # 防止非法 level
    # 仅在show_traceback为True时记录完整堆栈跟踪
    log_func(f"{message}: {type(e).__name__}: {str(e)}", exc_info=show_traceback)



def log_api_request(logger: logging.Logger, url: str, method: str = 'GET', success: bool = True,
                    status_code: int = None, error: Exception = None, params: dict = None, headers: dict = None):
    """
    统一记录API请求日志
    :param logger: 日志记录器
    :param url: API URL
    :param method: 请求方法
    :param success: 是否成功
    :param status_code: HTTP状态码
    :param error: 错误异常
    :param params: 请求参数（会自动过滤敏感信息）
    :param headers: 请求头（会自动过滤敏感信息）
    """
    # 过滤敏感信息
    redacted_params = _redact_sensitive_info(params) if params else None
    redacted_headers = _redact_sensitive_info(headers) if headers else None
    
    # 构建请求信息字符串
    request_info = f"{method} {url}"
    if redacted_params:
        request_info += f" - 参数: {redacted_params}"
    if redacted_headers:
        request_info += f" - 头信息: {redacted_headers}"
    
    if success:
        # 成功的请求记录为DEBUG级别，避免日志刷屏
        logger.debug(f"API请求成功: {request_info} - 状态码: {status_code}")
    else:
        # 失败的请求仍然记录为ERROR级别
        if error:
            logger.error(f"API请求失败: {request_info} - 错误: {str(error)}")
        else:
            logger.error(f"API请求失败: {request_info} - 状态码: {status_code}")


def print_colored_message(timestamp: str, location: str, sender: str, message: str):
    """
    打印彩色消息日志
    格式：时间（白色） [（蓝色）群名（白色）]（蓝色） 发送者（白色）：（黄色）消息（白色）
    :param timestamp: 时间戳，格式为 "MM-DD HH:MM:SS"
    :param location: 位置（群名或"私信"）
    :param sender: 发送者名称
    :param message: 消息内容
    """
    # 仅在终端输出时使用颜色
    if sys.stdout.isatty():
        white = ColoredFormatter.COLORS['WHITE']
        blue = ColoredFormatter.COLORS['INFO']
        yellow = ColoredFormatter.COLORS['WARNING']
        reset = ColoredFormatter.COLORS['RESET']
        
        output = f"{white}{timestamp}{reset} {blue}[{location}] {sender}：{reset}{white}{message}{reset}"
    else:
        output = f"{timestamp} [{location}] {sender}：{message}"
    
    print(output)


# 示例用法（可选，用于测试）
if __name__ == "__main__":
    logger = get_logger("TestLogger")
    logger.info("这是一条普通信息")
    logger.success("这是一条成功信息 ✅")
    logger.warning("这是一条警告信息 ⚠️")
    logger.error("这是一条错误信息 ❌")

    try:
        1 / 0
    except Exception as e:
        log_exception(logger, "除零错误测试", e)

    log_api_request(logger, "https://api.example.com/data", "POST", success=False, error=Exception("网络超时"))