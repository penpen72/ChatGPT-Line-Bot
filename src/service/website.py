import os
import re
import requests
from bs4 import BeautifulSoup

WEBSITE_SYSTEM_MESSAGE = "你現在非常擅於做資料的整理、總結、歸納、統整，並能專注於細節、且能提出觀點"
WEBSITE_MESSAGE_FORMAT = """
    針對這個連結的內容：
    \"\"\"
    {}
    \"\"\"

    請關注幾個點：
    1. 他的主題為何？
    2. 他的重點為何？(至少200字)
    3. 他獨特的觀點為何？(至少200字)
    4. 關鍵字有哪些?(至少3個)
    

    你需要回傳的格式是：
    - 主題： '...'
    - 重點： '...'
    - 獨特觀點： '...'
    - 關鍵字: '...'
"""


class Website:

    def get_url_from_text(self, text: str):
        url_regex = re.compile(r'^https?://\S+')
        match = re.search(url_regex, text)
        if match:
            return match.group()
        else:
            return None

    def get_content_from_url(self, url: str):
        hotpage = requests.get(url)
        soup = BeautifulSoup(hotpage.text, 'html.parser')

        selectors = {
            'default': ('article', {}),
            'site_1': ('div', {'class': 'content'}),
            'site_2': ('div', {'class': 'ttcl_0 csc-default'})
        }

        hotpage = requests.get(url)
        soup = BeautifulSoup(hotpage.text, 'html.parser')

        for key, (tag, attrs) in selectors.items():
            chunks = [article.text.strip() for article in soup.find_all(tag, **attrs)]
            if chunks:
                # print(f'selectors:{key}')
                return chunks
                # break
        # print('no support')
        return soup


class WebsiteReader:

    def __init__(self, model=None, model_engine=None):
        self.system_message = os.getenv(
            'WEBSITE_SYSTEM_MESSAGE') or WEBSITE_SYSTEM_MESSAGE
        self.message_format = os.getenv(
            'WEBSITE_MESSAGE_FORMAT') or WEBSITE_MESSAGE_FORMAT
        self.model = model
        self.text_length_limit = 4800
        self.model_engine = model_engine

    def send_msg(self, msg):
        return self.model.chat_completions(msg, self.model_engine)

    def summarize(self, chunks):
        text = '\n'.join(chunks)[:self.text_length_limit]
        msgs = [{
            "role": "system",
            "content": self.system_message
        }, {
            "role": "user",
            "content": self.message_format.format(text)
        }]
        return self.send_msg(msgs)
