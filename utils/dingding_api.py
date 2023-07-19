#coding:utf-8
import time
from utils.common_api import CommonAPIWrapper

class DingDingAPI(CommonAPIWrapper):
    def __init__(self, api_key, api_secret, robot_code, host="https://api.dingtalk.com"):
        super().__init__(host)
        self.api_key = api_key
        self.api_secret = api_secret
        self.robot_code = robot_code
        self.access_token = None
        self.access_token_expire_time = None

    def get_access_toke_old(self):
        path = "/gettoken"
        params = {
            "appkey": self.api_key,
            "appsecret": self.api_secret
        }
        return self.common_call(path, params=params, method="GET")
    
    def set_access_token(self, token, expire_time):
        self.access_token = token
        self.access_token_expire_time = expire_time

    @property
    def token_is_expired(self):
        if self.access_token_expire_time is None or self.access_token_expire_time < time.time() - 100:
            return True
        return False

    def get_assess_token(self):
        """
        
            {
            "accessToken" : "dsdsfsdfsf",
            "expireIn" : 7200
            }
        """
        if not self.token_is_expired:
            return self.access_token, self.access_token_expire_time
        path = '/v1.0/oauth2/accessToken'
        data = {
            "appKey" : self.api_key,
            "appSecret" : self.api_secret
        }
        result = self.common_call(path, json_=data, method="POST")
        self.access_token = result["accessToken"]
        self.access_token_expire_time = result["expireIn"] + time.time()
        return result
    
    def batch_send_message(self, user_ids, msg_param, msg_type="sampleImageMsg"):
        path = '/v1.0/robot/oToMessages/batchSend'
        headers = {"x-acs-dingtalk-access-token": self.access_token}
        data = {
            "robotCode" : self.robot_code,
            "userIds" : user_ids,
            "msgKey" : msg_type,
            "msgParam" : msg_param
        }
        return self.common_call(path, json_=data, method="POST", headers=headers)

    def send_group_message(self, open_conversation_id, msg_param, msg_type="sampleImageMsg"):
        path = '/v1.0/robot/groupMessages/send'
        headers = {"x-acs-dingtalk-access-token": self.access_token}
        data = {
            "robotCode" : self.robot_code,
            "openConversationId" : open_conversation_id,
            "msgKey" : msg_type,
            "msgParam" : msg_param
        }
        return self.common_call(path, json_=data, method="POST", headers=headers)
    
    def send_card_message(self, template_id, open_conversation_id, track_id, call_back_route_key, card_params, card_media_params, at_user_ids, chat_type=1, receive_user_ids=None):
        path = '/v1.0/im/interactiveCards/send'
        headers = {"x-acs-dingtalk-access-token": self.access_token}
        data = {
            "cardTemplateId" : template_id,
            "openConversationId" : open_conversation_id,
            "receiverUserIdList" : [],
            "outTrackId" : track_id,
            "conversationType" : chat_type,
            "callbackRouteKey" : call_back_route_key,
            "cardData" : {
                "cardParamMap" : card_params,
                "cardMediaIdParamMap" : card_media_params
            },
            "privateData" : {
            },
            "userIdType" : 1,
            "atOpenIds" : {
                "key" : at_user_ids  #"{123456:\"钉三多\"}"
            },
            "cardOptions" : {
                "supportForward" : True
            },
            "pullStrategy" : False,
    
        }
        if chat_type != "1":
            data["robotCode"] = self.robot_code
        else:
            data["receiverUserIdList"] = receive_user_ids
        return self.common_call(path, json_=data, method="POST", headers=headers)

    def register_call_back(self, call_back_url, route_key):
        # {'errcode': 0, 'errmsg': 'ok', 'result': {'apiSecret': 'xcscdsf, 'callbackUrl': 'http://xxx/event_callback'}, 'success': True, 'request_id': '16m5ch8drb5ud'}
        path = 'https://oapi.dingtalk.com/topapi/im/chat/scencegroup/interactivecard/callback/register'
        params = {"access_token": self.access_token}
        data = {
            "callback_url": call_back_url,
            "callbackRouteKey": route_key,
            "api_secret": self.api_secret
        }
        return self.common_call(path, json_=data, method="POST", params=params, need_urljoin=False)