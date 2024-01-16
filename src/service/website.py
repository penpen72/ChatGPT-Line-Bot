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
    2. 他的重點為何？(最多250字)
    3. 他獨特的觀點為何？(最多100字)
    4. 關鍵字有哪些?(至少3個)
    

    你需要回傳的格式是：
    - 主題： '...'
    - 重點： '...'
    - 獨特觀點： '...'
    - 關鍵字: '...'
"""


class Website:
    def __init__(self) -> None:
        self.headers = {
            'default':{'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',},
            'zh-TW':{'Accept-Language':'zh-TW,en-US;q=0.8,en;q=0.5,ja;q=0.3'},
            'space':'',
            'None':None,
            }
        self.selectors = {
            'eprice.com': (
                'default',
                'div', {'class': 'user-comment-block'}
                ),
            'gamer.com.tw': (
                'default',
                'div', {'class': 'GN-lbox3B'}
                ),
            'notebookcheck.net': (
                'default',
                'div', {'class': 'ttcl_0 csc-default'}
                ),
            'mobile01.com': (
                'default',
                'div', {'class': 'u-gapNextV--lg'}
                ),
            'news.ebc': (
                'default',
                'div', {'class': 'raw-style'}
                ),
            'chinatimes.com': (
                'None',
                'div', {'class': 'article-body'}
                ), 
            'toy-people.com': (
                'default',
                'div', {'class': 'card article article-contents'}
                ),
            'anandtech.com': (
                'default',
                'div', {'class': 'articleContent'}
                ),
            'bnext.com.tw': (
                'default',
                'div',{'class': 'htmlview article-content'}
                ),
            'judgment.judicial.gov': (
                'default','div', {'class': 'htmlcontent'}
                ),
            'moneyweekly.com.tw': (
                'default',
                'div',{'class': 'col-11 py-3 div_Article_Info'}
            )
        }
        
    def get_url_from_text(self, text: str):
        url_regex = re.compile(r'^https?://\S+')
        match = re.search(url_regex, text)
        if match:
            return match.group()
        else:
            return None

    def get_soup_from_url(self,url: str,headers=None):
   
        # headers = ''
        hotpage = requests.get(url, headers=headers,timeout=5)
        soup = BeautifulSoup(hotpage.text, 'html.parser')
        return soup


    def get_content_from_url_user_def(self,url: str):
        headers = self.headers
        selectors = self.selectors
        for key, (head,tag, attrs) in selectors.items():
            if key in url:
                soup = self.get_soup_from_url(url,headers=headers[head])
                chunks = [article.text.strip() for article in soup.find_all(tag, **attrs)]
                print(f'selectors:{key}')
                return chunks

        return []

    def get_content_from_url_common(self,url: str):
        selectors={
            'default': ('article', {}),
            'content': ('div', {'class': 'content'}),
        }

        soup = self.get_soup_from_url(url)    
        for key, (tag, attrs) in selectors.items():    
            chunks = [article.text.strip() for article in soup.find_all(tag, **attrs)]
            if chunks:
                print(f'selectors:{key}')
                return chunks
            
        return chunks    

    def get_content_from_url(self, url: str):
        chunks = self.get_content_from_url_user_def(url)
        if chunks:
            return chunks
        chunks = self.get_content_from_url_common(url)
        if chunks:
            return chunks
        
        print(f'No support! {url}')
        return chunks


class WebsiteReader:

    def __init__(self, model=None, model_engine=None):
        self.system_message = os.getenv(
            'WEBSITE_SYSTEM_MESSAGE') or WEBSITE_SYSTEM_MESSAGE
        self.message_format = os.getenv(
            'WEBSITE_MESSAGE_FORMAT') or WEBSITE_MESSAGE_FORMAT
        self.model = model
        self.text_length_limit = 5000
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
