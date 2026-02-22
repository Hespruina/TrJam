# 文件名: netease_search.py
"""
网易云音乐第三方搜索库（基于 xmsj.org 接口）
功能：输入歌名，返回带 VIP 判断的 JSON 结果
"""

import requests
import urllib.parse
import json

# 禁用警告
requests.packages.urllib3.disable_warnings()

class NetEaseMusicSearch:
    def __init__(self):
        self.search_url = "http://xmsj.org/"
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.search_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
            "X-Requested-With": "XMLHttpRequest"
        })
        self.session.cookies.update({
            "ZDEDebuggerPresent": "php,phtml,php3",
            "__51cke__": "",
            "__51laig__": "1"
        })

    def _is_vip_song(self, mp3_url):
        """精准判断是否为 VIP 歌曲（防假200）"""
        if not mp3_url:
            return True

        try:
            resp = self.session.get(
                mp3_url,
                timeout=30,
                allow_redirects=True,
                stream=True
            )

            if resp.status_code != 200:
                return True

            content_type = resp.headers.get("Content-Type", "").lower()
            content_length = int(resp.headers.get("Content-Length", 0))

            # HTML 页面一定是错误页
            if "text/html" in content_type:
                return True

            # 音频类型认为是正常的
            if any(t in content_type for t in ["audio/", "video/"]):
                return False

            # 二进制流 + 内容较大 → 可能是音频
            if "octet-stream" in content_type:
                return content_length < 1024 * 50  # 小于50KB很可能是空响应

            # 超小文件不是真音乐
            if content_length < 1024 * 10:
                return True

            return False

        except Exception:
            return True

    def search(self, keyword, page=1):
        """
        搜索歌曲并返回结构化 JSON 数据
        :param keyword: 歌名关键词
        :param page: 页码（默认第1页）
        :return: dict (JSON 格式数据)
        """
        # 设置 cookies 中的 __tins__ 时间戳（模拟活跃用户）
        import time
        sid = int(time.time() * 1000)
        expires = int(time.time() * 1000) + 1800000  # +30分钟
        self.session.cookies.set(
            "__tins__19997613",
            f'{{"sid": {sid}, "vd": 1, "expires": {expires}}}'
        )

        data = {
            "input": keyword,
            "filter": "name",
            "type": "netease",
            "page": str(page)
        }

        referer = f"http://xmsj.org/?name={urllib.parse.quote(keyword)}&type=netease"
        self.session.headers["Referer"] = referer

        try:
            response = self.session.post(
                self.search_url,
                data=data,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            api_data = response.json()
        except Exception as e:
            return {
                "success": False,
                "error": f"请求失败: {str(e)}",
                "songs": []
            }

        if api_data.get("code") != 200:
            return {
                "success": False,
                "error": api_data.get("error", "未知错误"),
                "songs": []
            }

        songs = api_data.get("data", [])
        result_songs = []

        for song in songs:
            title = song.get("title", "未知标题").strip()
            author = song.get("author", "未知歌手").strip()
            album = song.get("album", "未知专辑").strip() if song.get("album") else "未知专辑"
            pic = song.get("pic", "")
            lrc = song.get("lrc", "")
            mp3_url = song.get("url", "")

            is_vip = self._is_vip_song(mp3_url)

            result_songs.append({
                "title": title,
                "author": author,
                "album": album,
                "pic": pic,
                "lrc": lrc,
                "url": mp3_url,
                "can_download": not is_vip,
                "vip_tag": is_vip,
                "platform": "netease"
            })

        return {
            "success": True,
            "query": keyword,
            "total": len(result_songs),
            "songs": result_songs
        }

# 兼容旧调用方式
def search_songs(keyword, page=1):
    """
    简化接口：直接调用搜索并返回 JSON
    """
    searcher = NetEaseMusicSearch()
    return searcher.search(keyword, page)