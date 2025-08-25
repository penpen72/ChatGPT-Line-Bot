from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import (WebhookHandler)
from linebot.v3.exceptions import (InvalidSignatureError)
from linebot.v3.messaging import (Configuration, ApiClient, MessagingApi,
                                  ReplyMessageRequest, TextMessage,
                                  ImageMessage, MessagingApiBlob, PushMessageRequest)
from linebot.v3.webhooks import (MessageEvent, TextMessageContent,
                                 AudioMessageContent, ImageMessageContent)

import os
import uuid
import base64

from src.models import OpenAIModel
from src.memory import Memory
# from src.logger import logger
from src.storage import Storage, FileStorage, MongoStorage
from src.utils import get_role_and_content
from src.service.youtube import Youtube, YoutubeTranscriptReader
from src.service.website import Website, WebsiteReader
from src.mongodb import mongodb
from datetime import datetime,timedelta


load_dotenv('.env')

app = Flask(__name__)
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
line_bot_api = MessagingApi(ApiClient(configuration))
blob_api = MessagingApiBlob(ApiClient(configuration))
line_handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
storage = None
youtube = Youtube()
website = Website()

memory = Memory(system_message=os.getenv('SYSTEM_MESSAGE'), memory_message_count=20)
image_detail = os.getenv('IMAGE_DETAIL') or 'low'  # low, high, or auto
model_management = {}
api_keys = {}


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'


@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    # logger.info(f'{user_id}: {text}')
    print(f'{user_id}: {text}')
    if user_id not in model_management:
        model_management[user_id] = OpenAIModel(api_key=os.getenv('OPENAI_API_KEY'))

    try:
        if text.startswith('/help'):
            msg = TextMessage(text="""指令：
/註冊 + API Token
👉 API Token 請先到 https://platform.openai.com/ 註冊登入後取得\n
/系統訊息 + Prompt
👉 Prompt 可以命令機器人扮演某個角色，例如：請你扮演擅長做總結的人\n
忘記
👉 當前每一次都會紀錄最後兩筆歷史紀錄，這個指令能夠清除歷史訊息\n
圖像 + Prompt
👉 會調用 DALL∙E 2 Model，以文字生成圖像\n
語音輸入
👉 會調用 Whisper 模型，先將語音轉換成文字，再調用 ChatGPT 以文字回覆\n
其他文字輸入
👉 調用 ChatGPT 以文字回覆\n
貼上連結可以總結
👉 Youtube 影片內容、新聞文章（支援：聯合報、Yahoo 新聞、三立新聞網、中央通訊社、風傳媒、TVBS、自由時報、ETtoday、中時新聞網、Line 新聞、台視新聞網）"""
                                )

        elif text.startswith('/系統訊息'):
            memory.change_system_message(user_id, text[5:].strip())
            msg = TextMessage(text='輸入成功')

        elif text.startswith('忘記'):
            memory.remove(user_id)
            msg = TextMessage(text='歷史訊息清除成功')

        elif text.startswith('圖像'):
            prompt = text[3:].strip()
            memory.append(user_id, 'user', prompt)
            is_successful, response, error_message = model_management[
                user_id].image_generations(prompt)
            if not is_successful:
                raise Exception(error_message)
            url = response['data'][0]['url']
            msg = ImageMessage(original_content_url=url, preview_image_url=url)
            memory.append(user_id, 'assistant', url)
        elif text.lower().startswith('ext'):
            prompt = text[3:].strip()
            user_model = model_management[user_id]
            memory.append(user_id, 'user', prompt)
            
            # 使用模型的多輪 tool calling 方法，設定合理的限制
            is_successful, result, error_message = user_model.chat_with_ext_multi_turn(
                memory.get(user_id), 
                os.getenv('OPENAI_MODEL_ENGINE'),
                max_iterations=3,  # 減少最大迭代次數
                max_tool_calls=5   # 限制工具調用總次數
            )
            
            if not is_successful:
                raise Exception(error_message)
            
            # result 是 {'role': role, 'content': content} 格式
            msg = TextMessage(text=result['content'])
            memory.append(user_id, result['role'], result['content'])
        else:
            user_model = model_management[user_id]
            memory.append(user_id, 'user', text)
            url = website.get_url_from_text(text)
            if url:
                if youtube.retrieve_video_id(text):
                    is_successful, chunks, error_message = youtube.get_transcript_chunks(
                        youtube.retrieve_video_id(text))
                    if not is_successful:
                        raise Exception(error_message)
                    youtube_transcript_reader = YoutubeTranscriptReader(
                        user_model, os.getenv('OPENAI_MODEL_ENGINE'))
                    is_successful, response, error_message = youtube_transcript_reader.summarize(
                        chunks)
                    if not is_successful:
                        raise Exception(error_message)
                    role, response = get_role_and_content(response)
                    msg = TextMessage(text=response)
                else:
                    chunks = website.get_content_from_url(url)
                    if len(chunks) == 0:
                        raise Exception('無法撈取此網站文字')
                    website_reader = WebsiteReader(user_model,os.getenv('OPENAI_MODEL_ENGINE'))
                    is_successful, response, error_message = website_reader.summarize(
                        chunks)
                    if not is_successful:
                        raise Exception(error_message)
                    role, response = get_role_and_content(response)
                    msg = TextMessage(text=response)
            else:
                is_successful, response, error_message = user_model.chat_completions(memory.get(user_id), os.getenv('OPENAI_MODEL_ENGINE'))
                if not is_successful:
                    raise Exception(error_message)
                role, response = get_role_and_content(response)
                msg = TextMessage(text=response)

            memory.append(user_id, role, response)
    except ValueError:
        msg = TextMessage(text='Token 無效，請重新註冊，格式為 /註冊 sk-xxxxx')
    # except KeyError:
    #     msg = TextMessage(text='請先註冊 Token，格式為 /註冊')
    except Exception as e:
        memory.remove(user_id)
        error_msg = str(e)
        if error_msg.startswith('Incorrect API key provided'):
            msg = TextMessage(text='OpenAI API Token 有誤，請重新註冊。')
        elif 'overloaded' in error_msg.lower():
            msg = TextMessage(text='已超過負荷，請稍後再試')
        else:
            msg = TextMessage(text=error_msg)
    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=[msg]))

@line_handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event: MessageEvent):
    user_id = event.source.user_id
    if user_id not in model_management:
        model_management[user_id] = OpenAIModel(api_key=os.getenv('OPENAI_API_KEY'))
    audio_content = blob_api.get_message_content(event.message.id)
    input_audio_path = f'{str(uuid.uuid4())}.m4a'
    
    try:
        with open(input_audio_path, 'wb') as fd:
            # for chunk in audio_content.iter_content():
            #     fd.write(chunk)
            fd.write(audio_content)

        if not model_management.get(user_id):
            raise ValueError('Invalid API token')
        else:
            is_successful, response, error_message = model_management[user_id].audio_transcriptions(input_audio_path, 'whisper-1')
            if not is_successful:
                raise Exception(error_message)
            memory.append(user_id, 'user', response['text'])
            is_successful, response, error_message = model_management[user_id].chat_completions(memory.get(user_id), os.getenv('OPENAI_MODEL_ENGINE'))
            if not is_successful:
                raise Exception(error_message)
            role, response = get_role_and_content(response)

            memory.append(user_id, role, response)
            msg = TextMessage(text=response)
    except ValueError:
        msg = TextMessage(text='請先註冊你的 API Token，格式為 /註冊 [API TOKEN]')
    except KeyError:
        msg = TextMessage(text='請先註冊 Token，格式為 /註冊 sk-xxxxx')
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextMessage(text='OpenAI API Token 有誤，請重新註冊。')
        else:
            msg = TextMessage(text=str(e))
    finally:
        # 確保檔案總是被清理
        if os.path.exists(input_audio_path):
            os.remove(input_audio_path)
    
    line_bot_api.reply_message(event.reply_token, msg)


@line_handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event: MessageEvent):
    user_id = event.source.user_id
    if user_id not in model_management:
        model_management[user_id] = OpenAIModel(api_key=os.getenv('OPENAI_API_KEY'))
    image_content = blob_api.get_message_content(event.message.id)
    image_data = base64.b64encode(image_content).decode('utf-8')
    user_content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f'data:image/jpeg;base64,{image_data}',
                "detail": image_detail  # low, high, or auto
            }
        },
        {
            "type": "text",
            "text": "仔細觀察圖片上面的所有細節包含文字。詳細描述圖片上的內容並說明；如果你覺得他是個meme，說明他想傳達的情境，如果不是就不用特別說明"
        }
    ]
    memory.append(user_id, 'user', user_content)

    try:
        if not model_management.get(user_id):
            raise ValueError('Invalid API token')
        else:
            # is_successful, response, error_message = model_management[user_id].image_recognition(image_data, os.getenv('OPENAI_MODEL_ENGINE'))
            is_successful, response, error_message = model_management[user_id].chat_completions(memory.get(user_id), os.getenv('OPENAI_MODEL_ENGINE'))
            if not is_successful:
                raise Exception(error_message)
            role, response = get_role_and_content(response)
            memory.append(user_id, role, response)
            msg = TextMessage(text=response)
    except ValueError:
        msg = TextMessage(text='請先註冊你的 API Token，格式為 /註冊 [API TOKEN]')
    except KeyError:
        msg = TextMessage(text='請先註冊 Token，格式為 /註冊 sk-xxxxx')
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextMessage(text='OpenAI API Token 有誤，請重新註冊。')
        else:
            msg = TextMessage(text=str(e))
    # print(f'{response=}')   
    # print(f'{msg=}')        
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(reply_token=event.reply_token, messages=[msg]))


@app.route("/", methods=['GET'])
def home():
    return 'Hello World'


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
