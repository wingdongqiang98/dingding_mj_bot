# coding:utf-8

import json
import os
import time

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv()
from utils.log_utils import init_env

from utils.variables import LOGGER
from utils.dingding_api import DingDingAPI

from model import Task, initialize_db

app = Flask(__name__)

@app.before_request
def before_request():
    initialize_db()

@app.after_request
def after_request(response):
    Task._meta.database.close()
    return response

# If we want to exclude particular views from the automatic connection
# management, we list them this way:
FLASKDB_EXCLUDED_ROUTES = ('logout',)

dingding_api = DingDingAPI(os.getenv("DINGTALK_APPKEY"), os.getenv("DINGTALK_APPSECRET"), os.getenv("DINGTALK_ROBOT_CODE"))

@app.route("/message", methods=["POST"])
def message_handler():
    try:
        LOGGER.info("msg %s", request.json)
        msg_type = request.json["msgtype"]
        if msg_type != "text":
            LOGGER.warning("get not support type %s", msg_type)
            return jsonify({})
        chat_type = request.json["conversationType"]
        user_id = request.json["senderStaffId"]
        user_nickname = request.json["senderNick"]
        chat_id = request.json["conversationId"]
        message_id = request.json["msgId"]
        content = request.json["text"]["content"]
        if chat_type != "1" and not content.startswith("@"):
            LOGGER.warning("not get @ from message")
            return jsonify({})
        if chat_type != "1":
            content = content.split(" ", 1)[-1]
        params = json.dumps({"prompt": content})
        Task.create(user_id=user_id, user_nick=user_nickname, chat_id=chat_id, message_id=message_id, chat_type=chat_type, params=params, status="init",
                task_type="imagine")
        if dingding_api.token_is_expired:
            result = dingding_api.get_assess_token()
            dingding_api.set_access_token(result["accessToken"], time.time() + 7100)
        if chat_type == "1":
            dingding_api.batch_send_message([user_id],json.dumps({"content": "图片处理中，请稍后。。。"}), msg_type="sampleText")
        else:
            dingding_api.send_group_message(chat_id, json.dumps({"content": "图片处理中，请稍后。。。"}), msg_type="sampleText")
        return jsonify({})
    except:
        LOGGER.error("message handler error", exc_info=True)
        return jsonify({})


@app.route("/create_task", methods=["POST"])
def create_task():
    t = request.json["text"]
    Task.create(user="ou_903c5bc25e57543d52c6869634fa681c", params=json.dumps({"prompt": t}), status="init",
                task_type="imagine")
    return jsonify({})


@app.route("/event_callback", methods=["POST"])
def card_message():
    try:
        LOGGER.info("card message %s", request.json)
        value = json.loads(request.json.get("value", "{}"))
        if not value:
            return jsonify({})
    
        user_id = request.json["userId"]
        chat_id = request.json["openConversationId"]
        track_id = request.json["outTrackId"]
        param = value["cardPrivateData"]["params"]
        task_action = param["action"]
        parent_task = Task.get(Task.track_id == track_id)
        # "upscale", "variation"
        if task_action and task_action.startswith("u"):
            Task.create(user_id=user_id, user_nick=parent_task.user_nick, chat_id=chat_id, message_id="", chat_type=parent_task.chat_type, params=json.dumps(param), status="init",
            task_type="upscale")
        elif task_action and task_action.startswith("v"):
            Task.create(user_id=user_id, user_nick=parent_task.user_nick, chat_id=chat_id, message_id="", chat_type=parent_task.chat_type, params=json.dumps(param), status="init",
            task_type="variation")
        else:
            return "BAD REQUEST", 400
        if dingding_api.token_is_expired:
            result = dingding_api.get_assess_token()
            dingding_api.set_access_token(result["accessToken"], time.time() + 7100)
        if parent_task.chat_type == "1":
            dingding_api.batch_send_message([user_id],json.dumps({"content": "图片处理中，请稍后。。。"}), msg_type="sampleText")
        else:
            dingding_api.send_group_message(chat_id, json.dumps({"content": "图片处理中，请稍后。。。"}), msg_type="sampleText")
        return jsonify({})
    except:
        LOGGER.error("card_message error", exc_info=True)
        return jsonify({})


def main():
    app.run()


if __name__ == "__main__":
    main()
