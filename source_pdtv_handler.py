import json
import os
import re
import traceback
from datetime import datetime
from urllib.parse import parse_qs, urlparse
import zlib

from flask import Response, redirect
import requests
import yaml

from tool import ToolUtil
from .setup import *


class PDTV_Handler:
    SOURCES = "PANDATV"
    CHANNELS = []
    LAST_ERROR = None
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    DEFAULT_HEADER = {
        "authority": "api.pandalive.co.kr",
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.pandalive.co.kr",
        "referer": "https://www.pandalive.co.kr/",
        "user-agent": USER_AGENT,
    }
    STREAM_HEADER = {
        "Accept": "application/x-mpegURL, application/vnd.apple.mpegurl, application/json, text/plain, */*",
        "Origin": "https://www.pandalive.co.kr",
        "Referer": "https://www.pandalive.co.kr/",
        "User-Agent": USER_AGENT,
    }

    @classmethod
    def get_proxies(cls, use_proxy2=False):
        key = "use_proxy2" if use_proxy2 else "use_proxy"
        if P.ModelSetting.get_bool(key):
            proxy_url = P.ModelSetting.get("proxy_url")
            if proxy_url:
                return {"http": proxy_url, "https": proxy_url}
        return None

    @classmethod
    def get_device_info(cls, token=None):
        ui = 0
        if token:
            m = re.search(r"userLoginIdx=(\d+)", token)
            if m:
                try:
                    ui = int(m.group(1))
                except Exception:
                    pass
        return json.dumps({"t": "webPc", "v": "1.0", "ui": ui})

    @classmethod
    def call_request(
        cls,
        http_method,
        url,
        payload=None,
        params=None,
        headers=None,
        cookies=None,
        redirects=False,
        proxies=None,
        stream=None,
        verify=None,
        timeout=15,
    ):
        updated_headers = cls.DEFAULT_HEADER.copy()
        if headers:
            updated_headers.update(headers)
        if http_method == "GET":
            response = requests.get(
                url,
                params=params,
                headers=updated_headers,
                cookies=cookies,
                allow_redirects=redirects,
                proxies=proxies,
                stream=stream,
                verify=verify,
                timeout=timeout,
            )
        elif http_method == "GET_NO_DEFAULT":
            response = requests.get(
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                allow_redirects=redirects,
                proxies=proxies,
                stream=stream,
                verify=verify,
                timeout=timeout,
            )
        elif http_method == "POST":
            response = requests.post(
                url,
                data=payload,
                params=params,
                headers=updated_headers,
                cookies=cookies,
                allow_redirects=redirects,
                proxies=proxies,
                stream=stream,
                verify=verify,
                timeout=timeout,
            )
        else:
            response = None
        return response

    @classmethod
    def get_certification(cls):
        return True

    @classmethod
    def check_token(cls, token):
        if not token:
            return None
        proxies = cls.get_proxies(use_proxy2=False)
        url = "https://api.pandalive.co.kr/v1/member/login_info"
        headers = {
            "cookie": token,
            "x-device-info": cls.get_device_info(token),
        }
        try:
            response = cls.call_request("POST", url, headers=headers, proxies=proxies)
            if response and response.status_code == 200:
                data = response.json()
                user_info = data.get("loginInfo", {}).get("userInfo", {})
                if user_info.get("isLogin"):
                    return user_info
        except Exception as e:
            P.logger.error(f"[ff_pdtv] check_token exception: {str(e)}")
        return None

    @classmethod
    def login(cls, username, password):
        if not username or not password:
            cls.LAST_ERROR = "아이디와 비밀번호를 입력해주세요."
            return None

        proxies = cls.get_proxies(use_proxy2=False)
        url = "https://api.pandalive.co.kr/v1/member/login"
        payload = {
            "id": username,
            "pw": password,
            "idSave": "Y",
        }
        headers = {
            "x-device-info": json.dumps({"t": "webPc", "v": "1.0", "ui": 0})
        }
        try:
            response = cls.call_request("POST", url, payload=payload, headers=headers, proxies=proxies)
            if not response or response.status_code != 200:
                if response:
                    P.logger.error(f"[ff_pdtv] Login HTTP error {response.status_code}: {response.text}")
                    try:
                        err_json = response.json()
                        err_code = err_json.get("errorData", {}).get("code")
                        if err_code == "recaptcha":
                            cls.LAST_ERROR = "팬더TV에서 캡차(reCAPTCHA) 인증을 요구합니다. 웹 브라우저 로그인 후 토큰(쿠키)을 설정에 직접 등록해주세요."
                        elif err_code == "nopw":
                            cls.LAST_ERROR = "비밀번호가 일치하지 않습니다. 다시 입력해주세요."
                        elif err_code == "noid":
                            cls.LAST_ERROR = "존재하지 않는 사용자입니다."
                        else:
                            cls.LAST_ERROR = err_json.get("message") or f"로그인 에러 ({err_code})"
                    except Exception:
                        cls.LAST_ERROR = f"로그인 HTTP 에러 ({response.status_code})"
                else:
                    cls.LAST_ERROR = "팬더TV 서버 응답이 없습니다. (프록시 확인 필요)"
                return None
            res_json = response.json()
            if not res_json.get("result"):
                err_code = res_json.get("errorData", {}).get("code")
                msg = res_json.get("message")
                P.logger.error(f"[ff_pdtv] Login failed: {msg} (errorData: {res_json.get('errorData')})")
                if err_code == "recaptcha":
                    cls.LAST_ERROR = "팬더TV에서 캡차(reCAPTCHA) 인증을 요구합니다. 웹 브라우저 로그인 후 토큰(쿠키)을 설정에 직접 등록해주세요."
                elif err_code == "nopw":
                    cls.LAST_ERROR = "비밀번호가 일치하지 않습니다. 다시 입력해주세요."
                else:
                    cls.LAST_ERROR = msg or f"로그인 실패 ({err_code})"
                return None
            cookies = response.cookies.get_dict()
            if not cookies or "userLoginYN" not in cookies:
                P.logger.error(f"[ff_pdtv] userLoginYN not in login response cookies: {cookies}")
                cls.LAST_ERROR = "로그인 쿠키에 userLoginYN이 없습니다."
                return None
            token = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            P.logger.info(f"[ff_pdtv] Login successful for {username}")
            cls.LAST_ERROR = None
            return token
        except Exception as e:
            cls.LAST_ERROR = f"로그인 예외 발생: {str(e)}"
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())
            return None

    @classmethod
    def get_play_video(cls, userIdx, token=None, web_list_model=None):
        proxies = cls.get_proxies(use_proxy2=False)
        url = "https://api.pandalive.co.kr/v1/live/play"
        payload = {
            "action": "watch",
            "userIdx": userIdx,
            "password": "",
            "width": "48",
            "height": "48",
            "imageResize": "crop",
            "fanIconWidth": "44",
            "fanIconHeight": "44",
            "fanIconImageResize": "crop",
        }
        headers = {
            "x-device-info": cls.get_device_info(token),
        }
        if token:
            headers["Cookie"] = token

        response = cls.call_request("POST", url, payload=payload, params=None, headers=headers, proxies=proxies)
        if not response or not response.ok:
            if response:
                P.logger.error(f"[ff_pdtv] /v1/live/play failed HTTP {response.status_code}: {response.text}")
            return None

        try:
            data = response.json()
            if data.get("result") is False:
                P.logger.error(f"[ff_pdtv] /v1/live/play result false: {data.get('message')} ({data.get('errorData')})")
                return None

            playlist = data.get("PlayList") or {}
            hls_url = None
            for key in ["hls3", "hls2", "hls"]:
                if key in playlist and isinstance(playlist[key], list) and len(playlist[key]) > 0:
                    hls_url = playlist[key][0].get("url")
                    if hls_url:
                        break

            # parse media information safely
            media = data.get("media")
            if isinstance(media, dict):
                channel = media.get("userNick", str(userIdx))
                user_cnt = media.get("user", "")
                title = media.get("title", "")
                current = f"{title} [{user_cnt}명]" if user_cnt != "" else title
                icon = []
                if media.get("isAdult"):
                    icon.append("성인")
                if media.get("type") == "fan":
                    icon.append("팬방")
                if media.get("isPw"):
                    icon.append("암호방")
                if icon:
                    current = f"[{' '.join(icon)}] {current}"
            else:
                channel = str(userIdx)
                current = f"채널 {userIdx}"

            if not hls_url:
                P.logger.error(f"[ff_pdtv] No HLS URL found in PlayList for userIdx {userIdx}")
                return None

            hls_headers = cls.STREAM_HEADER.copy()
            hls_response = cls.call_request("GET_NO_DEFAULT", hls_url, headers=hls_headers, proxies=proxies)
            if not hls_response or not hls_response.ok:
                P.logger.error(f"[ff_pdtv] Failed to fetch master playlist from {hls_url} (HTTP {getattr(hls_response, 'status_code', None)})")
                return None

            use_quality = P.ModelSetting.get("use_quality") or "1920x1080"
            pattern = r"RESOLUTION=" + re.escape(use_quality) + r".*?\n(.+)"
            quality_urls = re.search(pattern, hls_response.text, re.MULTILINE)
            m3u8_url = None
            if quality_urls:
                m3u8_url = quality_urls.group(1).strip()
            else:
                for line in hls_response.text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        m3u8_url = line
                        break

            if not m3u8_url:
                m3u8_url = hls_url
            else:
                m3u8_url = cls.resolve_relative_url(hls_url, m3u8_url)

            if web_list_model:
                try:
                    db_item = web_list_model()
                    db_item.url = m3u8_url
                    db_item.ch_id = int(userIdx)
                    db_item.current = current.replace(",", ".")
                    db_item.channel = channel.replace(",", ".")
                    db_item.save()
                except Exception as e:
                    P.logger.debug(f"[ff_pdtv] Failed to save play_item to db: {e}")

            return m3u8_url

        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())
            return None

    @classmethod
    def get_list_data(cls, token=None):
        proxies = cls.get_proxies(use_proxy2=False)
        url = "https://api.pandalive.co.kr/v1/live"
        payload = {
            "offset": "0",
            "limit": "100",
            "orderBy": "user",
            "width": "280",
            "height": "158",
            "imageResize": "crop",
        }
        headers = {
            "x-device-info": cls.get_device_info(token),
        }
        if token:
            headers["Cookie"] = token

        try:
            response = cls.call_request("POST", url, payload=payload, headers=headers, cookies=None, redirects=False, proxies=proxies)
            if not response or response.status_code != 200:
                return []
            data = response.json()
            data_list = []
            for item in data.get("list", []):
                userNick = item.get("userNick", "")
                title = item.get("title", "")
                current = f"{title} [{item.get('user', 0)}명]"
                icon = []
                if item.get("isAdult"):
                    icon.append("성인")
                if item.get("type") == "fan":
                    icon.append("팬방")
                if item.get("isPw"):
                    icon.append("암호방")
                if icon:
                    current = f"[{' '.join(icon)}] {current}"

                userIdx = str(item.get("userIdx"))
                data_list.append({
                    "source": cls.SOURCES,
                    "id": userIdx,
                    "streamer": item.get("userId", ""),
                    "logo": item.get("thumbUrl", ""),
                    "channel": userNick.replace(",", "."),
                    "current": current.replace(",", "."),
                    "url": ToolUtil.make_apikey_url(f"/{P.package_name}/api/url.m3u8?userIdx={userIdx}"),
                })
            return data_list
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())
            return []

    @classmethod
    def ch_list(cls, token=None):
        cls.CHANNELS = cls.get_list_data(token)
        return cls.CHANNELS

    @classmethod
    def play_url(cls, url, token=None, web_list_model=None):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        user_idx_list = query_params.get("userIdx")
        if not user_idx_list:
            return None
        cast_id = user_idx_list[0]
        url = cls.get_play_video(cast_id, token, web_list_model)
        return url

    @classmethod
    def url_m3u8(cls, req, token=None, web_list_model=None):
        streaming_type = P.ModelSetting.get("streaming_type")
        userIdx = req.args.get("userIdx")
        m3u8_url = cls.get_play_video(userIdx, token, web_list_model)
        if not m3u8_url:
            return Response("Failed to get stream URL", status=500)
        if streaming_type == "redirect":
            return redirect(m3u8_url, code=302)
        m3u8_url = cls.compress_text(m3u8_url)
        return_url = ToolUtil.make_apikey_url(f"/{P.package_name}/api/play?streaming_type={streaming_type}&url={m3u8_url}")
        return redirect(return_url, code=302)

    @classmethod
    def play(cls, req):
        streaming_type = req.args.get("streaming_type")
        url = cls.decompress_text(req.args.get("url"))
        proxies = cls.get_proxies(use_proxy2=True)
        headers = cls.STREAM_HEADER.copy()
        response = cls.call_request("GET_NO_DEFAULT", url, headers=headers, redirects=False, proxies=proxies)
        if not response or response.status_code != 200:
            return None
        new_data = []
        for line in response.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                new_data.append(line)
            else:
                if streaming_type == "proxy":
                    resolved = cls.resolve_relative_url(url, line)
                    compressed = cls.compress_text(resolved)
                    new_line = ToolUtil.make_apikey_url(f"/{P.package_name}/api/segment?ts={compressed}")
                    new_data.append(new_line)
                elif streaming_type == "direct":
                    resolved = cls.resolve_relative_url(url, line)
                    new_data.append(resolved)
                else:
                    new_data.append(line)
        data = "\n".join(new_data)
        return Response(data, content_type="application/vnd.apple.mpegurl")

    @classmethod
    def segment(cls, req):
        proxies = cls.get_proxies(use_proxy2=True)
        url = cls.decompress_text(req.args.get("ts"))
        headers = cls.STREAM_HEADER.copy()
        response = cls.call_request("GET_NO_DEFAULT", url, headers=headers, proxies=proxies, stream=True, verify=False)
        return Response(
            response.iter_content(chunk_size=1048576) if response else b"",
            content_type="application/octet-stream",
            direct_passthrough=True,
            status=response.status_code if response else 500,
        )

    @staticmethod
    def resolve_relative_url(base_url, relative_url):
        if relative_url.startswith("http"):
            return relative_url
        base_parts = base_url.split("/")[:-1]
        relative_parts = relative_url.split("/")
        for part in relative_parts:
            if part == "..":
                if base_parts:
                    base_parts.pop()
            elif part and part != ".":
                base_parts.append(part)
        return "/".join(base_parts)

    @staticmethod
    def compress_text(text):
        data = text.encode("utf-8")
        compressed_data = zlib.compress(data)
        return compressed_data.hex()

    @staticmethod
    def decompress_text(compressed_text):
        compressed_data = bytes.fromhex(compressed_text)
        data = zlib.decompress(compressed_data)
        return data.decode("utf-8")

    @classmethod
    def make_m3u(cls, token=None):
        M3U_FORMAT = '#EXTINF:-1 tvg-id="{id}" tvg-name="{title}" tvg-logo="{logo}" group-title="{group}" tvg-chno="{ch_no}" tvh-chnum="{ch_no}",{title}\n{url}\n'
        m3u = "#EXTM3U\n"
        for idx, item in enumerate(cls.ch_list(token)):
            m3u += M3U_FORMAT.format(
                id=item["id"],
                title=f"{item['current']} ({item['channel']})",
                group=item["source"],
                ch_no=str(idx + 1),
                url=item["url"],
                logo=item["logo"],
            )
        return Response(m3u, headers={"Content-Type": "text/plain; charset=utf-8"})

    @classmethod
    def make_playlist(cls, playlist):
        last_10_items = playlist.query.order_by(playlist.id.desc()).limit(10).all()
        M3U_FORMAT = '#EXTINF:-1 tvg-id="{id}" tvg-name="{title}" tvg-logo="{logo}" group-title="{group}" tvg-chno="{ch_no}" tvh-chnum="{ch_no}",{title}\n{url}\n'
        m3u = "#EXTM3U\n"
        for idx, item in enumerate(last_10_items):
            m3u += M3U_FORMAT.format(
                id=item.ch_id,
                title=f"{item.current} ({item.channel})",
                group="list",
                ch_no=str(idx + 1),
                url=item.url,
                logo="",
            )
        return Response(m3u, headers={"Content-Type": "text/plain; charset=utf-8"})

    @classmethod
    def make_yaml(cls, token=None):
        data = {
            "primary": True,
            "code": f"{cls.SOURCES.lower()}",
            "title": f"[{cls.SOURCES}]",
            "year": f"{datetime.now().year}",
            "genres": "Live",
            "posters": "https://cdn.discordapp.com/attachments/877784202651787316/1136977716378345472/pandatv.png",
            "summary": "",
            "extras": [],
        }
        playlist = cls.ch_list(token)
        if not playlist:
            data["extras"].append({
                "mode": "mp4",
                "type": "featurette",
                "param": "https://cdn.discordapp.com/attachments/877784202651787316/1128156544421343292/1.mp4",
                "title": "방송중인 채널이 없습니다.",
                "thumb": "https://media.discordapp.net/attachments/973582802102648882/1006128472856465458/unknown.png",
            })
        else:
            for idx, item in enumerate(playlist):
                data["extras"].append({
                    "mode": "m3u8",
                    "type": "featurette",
                    "param": item["url"],
                    "title": f"{item['current'].replace(',', '')} ({item['channel'].replace(',', '')})",
                    "thumb": item["logo"],
                })
        yaml_data = yaml.dump(data, allow_unicode=True, sort_keys=False, encoding="utf-8")
        return Response(yaml_data, headers={"Content-Type": "text/yaml; charset=utf-8"})

    @classmethod
    def plex_refresh_by_item(cls, item_id):
        try:
            plex_server_url = P.ModelSetting.get("plex_server_url")
            plex_token = P.ModelSetting.get("plex_token")
            url = f"{plex_server_url}/library/metadata/{item_id}/refresh?X-Plex-Token={plex_token}"
            ret = requests.put(url)
            ret.raise_for_status()
            P.logger.debug("Plex 메타 데이터 새로고침이 성공적으로 시작되었습니다.")
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())

    @classmethod
    def sync_yaml_data(cls):
        try:
            yaml_url = ToolUtil.make_apikey_url(f"/{P.package_name}/api/yaml")
            local_path = P.ModelSetting.get("yaml_path")
            plex_meta_item = P.ModelSetting.get("plex_meta_item")

            if not local_path or not os.path.exists(local_path):
                return

            P.logger.debug(f"yaml_url:{yaml_url}")
            response = requests.get(yaml_url, headers=cls.DEFAULT_HEADER)
            if response.status_code != 200:
                return

            new_data = yaml.safe_load(response.text)
            with open(local_path, "r", encoding="utf-8") as file:
                current_data = yaml.safe_load(file)

            if current_data.get("extras") != new_data.get("extras"):
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_data["summary"] = f"마지막 업데이트 시간 : {now_str}"
                with open(local_path, "w", encoding="utf-8") as file:
                    yaml.dump(new_data, file, allow_unicode=True, sort_keys=False, encoding="utf-8")
                P.logger.debug("데이터가 변경되어 로컬에 저장되었습니다.")
                if plex_meta_item:
                    cls.plex_refresh_by_item(plex_meta_item)
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())
