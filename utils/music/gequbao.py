# 文件名: gequbao_search.py
"""
歌曲宝 (gequbao.com) 音乐搜索与解析库
功能：输入歌名，返回歌曲列表及真实 MP3 下载链接（无 VIP 限制）
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import urllib.parse
from typing import Dict, List, Any, Optional

# 禁用警告
requests.packages.urllib3.disable_warnings()

class GeQuBaoMusicSearch:
    def __init__(self):
        self.base_url = "https://www.gequbao.com"
        self.search_url = self.base_url + "/s/{keyword}"
        self.api_play_url = self.base_url + "/api/play-url"

        self.session = requests.Session()
        self.session.headers.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Connection": "keep-alive",
            "referer": self.base_url,
            "priority": "u=0, i",
            "sec-ch-ua": "\"Microsoft Edge\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
        })

        # 设置 Cookie 模拟登录状态
        self.session.cookies.set("Hm_tf_t8h1bavogbi", "1759233760")
        self.session.cookies.set("Hm_lvt_t8h1bavogbi", "1759233760,1760702524")
        self.session.cookies.set("Hm_lpvt_t8h1bavogbi", "1760702537")

    def _extract_song_list(self, html: str) -> List[Dict[str, Any]]:
        """从搜索结果页面提取歌曲列表（不含直链）"""
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('a.music-link')
        songs = []

        for item in items:
            title_span = item.select_one('.music-title span')
            artist_small = item.select_one('.text-jade')
            href = item['href']

            music_id_match = re.search(r'/music/(\d+)', href)
            music_id = music_id_match.group(1) if music_id_match else "0"

            songs.append({
                "title": (title_span.get_text(strip=True) if title_span else "未知标题"),
                "author": (artist_small.get_text(strip=True) if artist_small else "未知歌手"),
                "page_url": self.base_url + href,
                "music_id": music_id
            })

        return songs

    def _extract_play_id(self, detail_page_url: str) -> Optional[str]:
        """访问详情页，提取 window.appData.play_id"""
        try:
            resp = self.session.get(detail_page_url, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'

            match = re.search(r'window\.appData\s*=\s*(\{.*?\});\s*</script>', resp.text, re.DOTALL)
            if not match:
                return None

            app_data_str = match.group(1).replace('\/', '/')
            app_data = json.loads(app_data_str)
            return app_data.get('play_id')

        except Exception as e:
            print(f"[DEBUG] 提取 play_id 失败: {e}")
            return None

    def _get_real_mp3_url(self, play_id: str) -> Optional[str]:
        """调用 API 获取真实 MP3 直链"""
        try:
            resp = self.session.post(
                self.api_play_url,
                data={"id": play_id},
                headers={"content-type": "application/x-www-form-urlencoded"},
                timeout=30
            )
            result = resp.json()
            if result.get("code") == 1:
                return result["data"]["url"]
            else:
                print(f"[DEBUG] API 错误: {result.get('msg')}")
                return None
        except Exception as e:
            print(f"[DEBUG] 请求 API 失败: {e}")
            return None

    def search(self, keyword: str, page: int = 1) -> Dict[str, Any]:
        """
        搜索歌曲并返回结构化 JSON 数据（包含真实 MP3 链接）
        :param keyword: 歌名关键词
        :param page: 页码（目前歌曲宝不分页，仅第一页）
        :return: dict (JSON 格式数据)
        """
        encoded_keyword = urllib.parse.quote(keyword.strip())
        url = self.search_url.format(keyword=encoded_keyword)

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
        except Exception as e:
            return {
                "success": False,
                "error": f"请求失败: {str(e)}",
                "songs": []
            }

        # 1. 提取初步信息（title, author, page_url, music_id）
        raw_songs = self._extract_song_list(response.text)
        if not raw_songs:
            return {
                "success": True,
                "query": keyword,
                "total": 0,
                "songs": []
            }

        # 2. 遍历每首歌，获取详情页中的 play_id，并请求真实链接
        result_songs = []
        for song in raw_songs:
            play_id = self._extract_play_id(song["page_url"])
            if not play_id:
                mp3_url = ""
            else:
                mp3_url = self._get_real_mp3_url(play_id)

            result_songs.append({
                "title": song["title"],
                "author": song["author"],
                "album": "未知专辑",       # 歌曲宝搜索页不提供专辑
                "pic": "",               # 不提供封面图（除非再爬一次）
                "lrc": "",               # 不提供歌词文本（除非额外处理）
                "url": mp3_url or "",
                "can_download": bool(mp3_url),  # 能拿到链接即可下载
                "vip_tag": False,        # 歌曲宝无 VIP 概念
                "platform": "gequbao"
            })

        return {
            "success": True,
            "query": keyword,
            "total": len(result_songs),
            "songs": result_songs
        }


# --------------------------
# 兼容旧调用方式
# --------------------------

def search_songs(keyword: str, page: int = 1) -> Dict[str, Any]:
    """
    简化接口：直接调用搜索并返回 JSON
    """
    searcher = GeQuBaoMusicSearch()
    return searcher.search(keyword, page)


# --------------------------
# 使用示例
# --------------------------

if __name__ == "__main__":
    # 示例：搜索歌曲
    result = search_songs("Cry For Me The Weeknd", page=1)

    if result["success"]:
        print(f"✅ 搜索 '{result['query']}' 成功，共找到 {result['total']} 首歌：\n")
        for idx, song in enumerate(result["songs"], start=1):
            print(f"{idx}. {song['title']} - {song['author']}")
            print(f"   🔗 {song['url']}\n")
    else:
        print(f"❌ 搜索失败: {result['error']}")