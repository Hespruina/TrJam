# 音频文件处理工具

import asyncio
import os
import aiohttp
import uuid
from logger_config import get_logger

logger = get_logger("AudioUtils")

# 临时文件存储目录
temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_audio")

# 确保临时目录存在
def ensure_temp_dir():
    """确保临时文件目录存在"""
    if not os.path.exists(temp_dir):
        try:
            os.makedirs(temp_dir)
            logger.info(f"创建临时音频文件目录: {temp_dir}")
        except Exception as e:
            logger.error(f"创建临时目录失败: {e}")

# 初始化临时目录
ensure_temp_dir()

async def download_audio_file(url: str, filename: str, platform: str = 'netease') -> str:
    """
    下载音频文件到临时目录
    :param url: 音频文件URL
    :param filename: 保存的文件名
    :param platform: 音乐平台，默认为'netease'（网易云音乐）
    :return: 本地文件的绝对路径，如果下载失败则返回空字符串
    """
    try:
        # 生成唯一的临时文件名，避免冲突
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"{unique_id}_{filename}"
        file_path = os.path.join(temp_dir, safe_filename)
        
        logger.info(f"开始下载音频文件到: {file_path}")
        
        # 根据不同平台设置HTTP请求头
        headers = None
        if platform == 'netease':
            # 构建HTTP请求头，模拟浏览器行为
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "cache-control": "max-age=0",
                "cookie": "timing_user_id=time_6DNQxwoHpE; _ga=GA1.1.1702229402.1757418227; _ga_EPDQHDTJH5=GS2.1.s1759032859^$o2^$g0^$t1759032879^$j40^$l0^$h0; NMTID=00OhzOmPuovPdh7L0F5ulFwnAMHH1QAAAGZkLsT9w; _iuqxldmzr_=32; _ntes_nnid=6bfc7b7ab0e5a72ed78b0cd8c706ce83,1759069804415; _ntes_nuid=6bfc7b7ab0e5a72ed78b0cd8c706ce83; JSESSIONID-WYYY=s2ga4eMlF2wOsM30ChZ655AziYuV8xrvRbJKoO^%^2BQX6pB79^%^5C^%^2BwbpxegVa1xtMdMHgU^%^5CHlAX9l9eywxZ0C9YMfIDdr6UzmaQoYhZIcfpRQC2uAV^%^5CpQwE4a^%^2BP^%^2B9Y8JrOY^%^5ChcbK7HpENFioXnYkbZOQCKQTV0P71G3zGA^%^5CXYZdpiTHJe8r2M^%^3A1759248359753; WM_NI=eNBaU85S63uwpTvHuHWXNHYzCzakaYNIh8VP83JFj9DUwXDnXHDcsPPX2McddadNrnHIr6jD3BKddlPPRBH02e3VoBmnO2xyk6C^%^2FVtvn6NPSRtI0dWJk7p3BHnLMPMKdVDg^%^3D; WM_NIKE=9ca17ae2e6ffcda170e2e6ee8fc566b7eaaba4f73e8f928eb7c14e879b9a83c67df89184afc74bf38ba583cb2af0fea7c3b92aa7928e82d834f78dfad4f87db48cbaa9f844958882a9dc7281a6af8ce4538e97a8d9d55cfced86a7e933888bb9b9c7669c988c84f25c9488feaee270a8bfacaff1668c97bed7e950f19e8585e76894909ea3cb3cf2bbfdb7ee4aafb281d3fb73a9ea8dd0d580b6b2faafd35992ac87d1e75d8ab5f991b24a8cb284aed34789bc9aa5e637e2a3; WM_TID=Ugoa0FYUL4xEUAVRFEfX09fLNCUwEheH; sDeviceId=YD-yDLNHHkXzFdAU0FVFFPTksefIWFxCHci; ntes_utid=tid._.isI1mVnJfGxAAgUVQVKTk8beZWF0B2M9._.0",
                "priority": "u=0, i",
                "sec-ch-ua": "\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Microsoft Edge\";v=\"140\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "cross-site",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
            }
        elif platform == 'qq':
            # 构建QQ音乐特定的HTTP请求头
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "cache-control": "max-age=0",
                "cookie": "pgv_pvid=9699050496; fqm_pvqid=4ccfe34d-87b3-4a76-9136-599eb2464bfe; fqm_sessionid=14ed2ae3-731f-4ee3-af93-71d12416f898; pgv_info=ssid=s5253609305; ts_last=y.qq.com/n/ryqq/songDetail/0030aivo12ixUT; ts_refer=xmsj.org/; ts_uid=2507794196; _qpsvr_localtk=0.31856094683999836",
                "priority": "u=0, i",
                "sec-ch-ua": "\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Microsoft Edge\";v=\"140\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "cross-site",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
            }
        
        # 下载文件
        async with aiohttp.ClientSession() as session:
            if headers:
                async with session.get(url, timeout=30, headers=headers) as response:
                    if response.status == 200:
                        # 获取文件大小
                        file_size = int(response.headers.get('content-length', 0))
                        downloaded_size = 0
                        
                        # 写入文件
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_any():
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    
                                    # 记录下载进度（每下载20%记录一次）
                                    if file_size > 0:
                                        progress = (downloaded_size / file_size) * 100
                                        if int(progress) % 20 == 0 and downloaded_size > 0:
                                            logger.info(f"音频文件下载进度: {progress:.1f}%")
                        
                        logger.info(f"音频文件下载完成: {file_path}, 文件大小: {os.path.getsize(file_path)}字节")
                        return file_path
                    else:
                        logger.error(f"音频文件下载失败，状态码: {response.status}")
                    return ""
            else:
                # 不使用请求头的情况
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        # 获取文件大小
                        file_size = int(response.headers.get('content-length', 0))
                        downloaded_size = 0
                        
                        # 写入文件
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_any():
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    
                                    # 记录下载进度（每下载20%记录一次）
                                    if file_size > 0:
                                        progress = (downloaded_size / file_size) * 100
                                        if int(progress) % 20 == 0 and downloaded_size > 0:
                                            logger.info(f"音频文件下载进度: {progress:.1f}%")
                        
                        logger.info(f"音频文件下载完成: {file_path}, 文件大小: {os.path.getsize(file_path)}字节")
                        return file_path
                    else:
                        logger.error(f"音频文件下载失败，状态码: {response.status}")
                        return ""
    except asyncio.TimeoutError:
        logger.error(f"音频文件下载超时: {url}")
    except aiohttp.ClientError as e:
        logger.error(f"音频文件下载网络错误: {str(e)}")
    except IOError as e:
        logger.error(f"音频文件写入失败: {str(e)}")
    except Exception as e:
        logger.error(f"音频文件下载过程中发生未知错误: {str(e)}")
    
    # 发生错误时清理可能的部分文件
    if 'file_path' in locals() and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"清理未完成的临时文件: {file_path}")
        except:
            pass
    
    return ""

def clean_temp_files(max_age_hours: int = 24):
    """
    清理过期的临时文件
    :param max_age_hours: 文件最大保留时间（小时）
    """
    try:
        if not os.path.exists(temp_dir):
            return
        
        current_time = os.path.getmtime(temp_dir)
        max_age_seconds = max_age_hours * 3600
        
        files_removed = 0
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if current_time - file_mtime > max_age_seconds:
                    os.remove(file_path)
                    files_removed += 1
                    logger.info(f"清理过期临时文件: {file_path}")
        
        if files_removed > 0:
            logger.info(f"共清理 {files_removed} 个过期临时音频文件")
    except Exception as e:
        logger.error(f"清理临时文件时发生错误: {str(e)}")

async def safe_remove_file(file_path: str):
    """
    安全删除文件，处理可能的异常
    :param file_path: 要删除的文件路径
    """
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"成功删除临时文件: {file_path}")
        except Exception as e:
            logger.error(f"删除临时文件失败: {str(e)}")