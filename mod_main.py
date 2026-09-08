from datetime import datetime, timedelta
import os
from tool import ToolUtil
from flask import Response
from .setup import *
from .model import ModelPanliveItem

from .source_pdtv_handler import PDTV_Handler


class ModuleMain(PluginModuleBase):
    def __init__(self, P):
        super(ModuleMain, self).__init__(P, name="main", first_menu="setting", scheduler_desc="팬더TV")
        self.db_default = {
            f"{self.name}_db_version": "1",
            f"{self.name}_auto_start": "False",
            f"{self.name}_interval": "5",
            f"{self.name}_db_delete_day": "3",
            f"{self.name}_db_auto_delete": "False",
            "plex_server_url": "http://localhost:32400",
            "plex_token": "",
            "plex_meta_item": "",
            "yaml_path": "",
            "use_quality": "1920x1080",
            "streaming_type": "redirect",
            "username": "",
            "password": "",
            "token_refresh_hour": "5",
            "token": "",
            "token_time": "",
            "use_proxy": "False",
            "use_proxy2": "False",
            "proxy_url": "",
        }
        self.web_list_model = ModelPanliveItem

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg["api_m3u"] = ToolUtil.make_apikey_url(f"/{P.package_name}/api/m3u")
        arg["api_playlist"] = ToolUtil.make_apikey_url(f"/{P.package_name}/api/playlist")
        arg["api_yaml"] = ToolUtil.make_apikey_url(f"/{P.package_name}/api/yaml")
        arg["hls_playback"] = "https://chrome.google.com/webstore/detail/native-hls-playback/emnphkkblegpebimobpbekeedfgemhof"
        if sub == "setting":
            arg["is_include"] = F.scheduler.is_include(self.get_scheduler_name())
            arg["is_running"] = F.scheduler.is_running(self.get_scheduler_name())
        return render_template(f"{P.package_name}_{self.name}_{sub}.html", arg=arg)

    def process_command(self, command, arg1, arg2, arg3, req):
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        streaming_type = P.ModelSetting.get("streaming_type")

        if command == "broad_list":
            token = self.token_refresh()
            data = PDTV_Handler.ch_list(token)
            return jsonify({"list": data, "updated_at": updated_at, "streaming_type": streaming_type})
        elif command == "play_url":
            url = arg1
            if streaming_type == "redirect":
                token = self.token_refresh()
                url = PDTV_Handler.play_url(url, token, self.web_list_model)
            if url:
                ret = {"ret": "success", "data": url}
            else:
                err_msg = getattr(PDTV_Handler, "LAST_ERROR", None) or "스트림 주소를 가져오지 못했습니다."
                ret = {"ret": "error", "data": None, "msg": err_msg}
        elif command == "login_check":
            data = self.token_refresh(force=True)
            if data:
                ret = {"ret": "success", "json": data}
            else:
                ret = {"ret": "warning", "json": "로그인 실패 (아이디/비밀번호 또는 프록시 설정을 확인하세요)"}
        elif command == "token_delete":
            P.ModelSetting.set("token", "")
            P.ModelSetting.set("token_time", "")
            data = "OK"
            ret = {"ret": "success", "json": data}
        return jsonify(ret)

    def process_api(self, sub, req):
        try:
            if sub == "m3u":
                token = self.token_refresh()
                return PDTV_Handler.make_m3u(token)
            if sub == "playlist":
                return PDTV_Handler.make_playlist(self.web_list_model)
            elif sub == "yaml":
                token = self.token_refresh()
                return PDTV_Handler.make_yaml(token)
            elif sub == "url.m3u8":
                token = self.token_refresh()
                return PDTV_Handler.url_m3u8(req, token, self.web_list_model)
            elif sub == "play":
                return PDTV_Handler.play(req)
            elif sub == "segment":
                return PDTV_Handler.segment(req)

        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())

    def scheduler_function(self):
        try:
            PDTV_Handler.sync_yaml_data()
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())

    def token_refresh(self, force=False):
        flag = False
        form = "%Y-%m-%d %H:%M:%S"
        if force:
            flag = True
        if flag == False and P.ModelSetting.get("token") == "":
            flag = True
        if flag == False:
            last_time_str = P.ModelSetting.get("token_time")
            if last_time_str == "":
                flag = True
            else:
                last_time = datetime.strptime(last_time_str, form)
                if last_time + timedelta(hours=P.ModelSetting.get_int("token_refresh_hour")) < datetime.now():
                    flag = True
        if flag:
            data = PDTV_Handler.login(P.ModelSetting.get("username"), P.ModelSetting.get("password"))
            if data:
                P.ModelSetting.set("token", data)
                P.ModelSetting.set("token_time", datetime.now().strftime(form))
            return data
        return P.ModelSetting.get("token")
