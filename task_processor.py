# coding:utf-8
import datetime
import json
import os
import random
import string
import threading
import time
from multiprocessing import Process

from dotenv import load_dotenv
load_dotenv()

from utils.dingding_api import DingDingAPI
from utils.log_utils import init_env
from utils.media_utils import download_image_io
from utils.task_api import MJApi
from utils.variables import LOGGER, CARD_MSG_TEMPLATE
from utils.func_utils import error_cap
threads = []


dingding_api = DingDingAPI(os.getenv("DINGTALK_APPKEY"), os.getenv("DINGTALK_APPSECRET"), os.getenv("DINGTALK_ROBOT_CODE"))
template_id = os.getenv("DINGTALK_TEMPLATE_ID")
server_ip = os.getenv("SEVER_IP")
MAX_THREAD_NUM = int(os.getenv("MAX_THREAD_NUM", 5))
CACHE_INFO = {}
from model import Task, initialize_db
initialize_db()


def get_random_string(length):
    # 定义所有可能的字符：大小写字母和数字
    possible_characters = string.ascii_letters + string.digits
    # 从可能的字符中随机选择指定数量的字符
    random_string = ''.join(random.choice(possible_characters) for i in range(length))
    return random_string

@error_cap()
def send_text_msg(msg, user_id, chat_type, chat_id):
    if dingding_api.token_is_expired:
        result = dingding_api.get_assess_token()
        dingding_api.set_access_token(result["accessToken"], time.time() + 7100)
    if chat_type == "1":
        dingding_api.batch_send_message([user_id],json.dumps({"content": msg}), msg_type="sampleText")
    else:
        dingding_api.send_group_message(chat_id, json.dumps({"content": msg}), msg_type="sampleText")



def process_task(task_params, task_type, task_id, user_id, chat_type, chat_id, user_nick):
    try:
        init_env(filename="dingding_mj_bot_thread.log")
        api = MJApi(os.getenv("MJ_TASK_APIKEY"))
        Task.update(status="schedule").where(Task.id == task_id).execute()
        task_params = json.loads(task_params)
        LOGGER.info("task %s params %s", task_id, task_params)
        if task_type == "imagine":
            mj_task_id = api.create_task(**task_params)["data"]["task_id"]
        elif task_type in ["upscale", "variation"]:
            mj_task_id = api.child_task(**task_params)["data"]["task_id"]
        else:
            raise Exception("not support task type %s" % task_type)
        timeout = int(os.getenv("TASK_TIMEOUT", "600"))
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                Task.update(status="error", desc="timeout").where(Task.id == task_id).execute()
                send_text_msg("timeout", user_id, chat_type, chat_id)
                break
            result = api.query_task(mj_task_id)
            status = result["data"]["status"]
            Task.update(status=status).where(Task.id == task_id).execute()
            if result["data"]["status"] == "finished":
                if dingding_api.token_is_expired:
                    access_token_result = dingding_api.get_assess_token()
                    dingding_api.set_access_token(access_token_result["accessToken"], time.time() + 7100)
                image_url = result["data"]["image_url"]
                if task_type in ["upscale", "variation"]:
                    if chat_type == "1":
                        dingding_api.batch_send_message([user_id],json.dumps({"photoURL": image_url}))
                    else:
                        dingding_api.send_group_message(chat_id, json.dumps({"photoURL": image_url}))
                else:
                    if CACHE_INFO.get("CALL_BACK_ID", None) is None:
                        callback_id = get_random_string(16)
                        CACHE_INFO["CALL_BACK_ID"] = callback_id
                        dingding_api.register_call_back(f"http://{server_ip}/event_callback", callback_id)
                    track_id = str(int(time.time()*1000))
                    if chat_type == "1":
                        dingding_api.send_card_message(template_id, chat_id, track_id, CACHE_INFO["CALL_BACK_ID"], {"image": image_url, "task_id": mj_task_id}, {}, json.dumps({user_id: user_nick}), chat_type=chat_type, receive_user_ids=[user_id])
                    else:
                        dingding_api.send_card_message(template_id, chat_id, track_id, CACHE_INFO["CALL_BACK_ID"], {"image": image_url, "task_id": mj_task_id}, {}, json.dumps({user_id: user_nick}), chat_type=chat_type)

                    Task.update(track_id=track_id).where(Task.id == task_id).execute()
                break
            if result["data"]["status"] == "error":
                msg = result.get("msg", "error")
                Task.update(status="error", desc=msg).where(Task.id == task_id).execute()
                send_text_msg(msg, user_id, chat_type, chat_id)
                break
            time.sleep(1)
    except Exception as e:
        Task.update(status="error", desc=str(e)).where(Task.id == task_id).execute()
        send_text_msg(str(e), user_id, chat_type, chat_id)
        LOGGER.error("run error", exc_info=True)


@error_cap()
def delete_old_data():
    check_time = datetime.datetime.now() - datetime.timedelta(days=7)
    query = Task.delete().where(Task.timestamp < check_time)
    query.execute()


def process_tasks():
    init_env("dingding_bot_process.log")
    time.sleep(10)
    next_time = time.time() - 100
    while True:
        try:
            if next_time < time.time():
                delete_old_data()
                next_time = time.time() + 3600
            tasks = Task.select().where(Task.status == "init", Task.retry_count <= 3)
            for t in tasks:
                if len(threads) >= MAX_THREAD_NUM:
                    LOGGER.warning("max thread !")
                    continue
                th = threading.Thread(target=process_task, args=(t.params, t.task_type, t.id, t.user_id, t.chat_type,
                                                                    t.chat_id, t.user_nick))
                th.start()
                threads.append(th)
            for i in range(len(threads) - 1):
                t = threads[i]
                if not t.is_alive():
                    threads.pop(i)
            time.sleep(3)
        except:
            LOGGER.error("run error", exc_info=True)


def main():
    process_tasks()

if __name__ == "__main__":
    main()
