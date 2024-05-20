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

    根據上面文章分析，並用簡潔明瞭的方式回答下問題：
    1. 他的主題為何？
    2. 他的重點為何？(至少100字,但不超過350字)
    3. 他獨特的觀點為何？(至少100字,但不超過200字)
    4. 關鍵字有哪些?(至少3個)
    
    
    你需要回傳的格式是：
    - 主題： '...'
    - 重點： '...'
    - 獨特觀點： '...'
    - 關鍵字: '...'
"""
DEFAULT_HEADER={'User-Agent': r'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',}
DEFAULT_SELECTOR=('div', {'class': 'content'})

class Website:
    def __init__(self) -> None:
        self.headers = {
            'default':{'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',},
            'zh-TW':{'Accept-Language':'zh-TW,en-US;q=0.8,en;q=0.5,ja;q=0.3'},
            'space':'',
            'None':None,
            }
        self.sites_info = {
            'eprice.com': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'user-comment-block'})
            },
            'gamer.com.tw': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'GN-lbox3B'})
            },
            'notebookcheck.net': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'ttcl_0 csc-default'})
            },
            'mobile01.com': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'articleBody'})
            },
            'news.ebc': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'raw-style'})
            },
            'toy-people.com': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'card article article-contents'})
            },
            'anandtech.com': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'articleContent'})
            },
            'bnext.com.tw': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'htmlview article-content'})
            },
            'judgment.judicial.gov': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'htmlcontent'})
            },
            'moneyweekly.com.tw': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'col-11 py-3 div_Article_Info'})
            },
            'corp.mediatek.tw': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'news-body'})
            },
            'www.ptt.cc': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'bbs-screen bbs-content'}),
                'cookies':{'over18':'1'}
            },
            'www.businessweekly.com.tw': {
                'headers': DEFAULT_HEADER,
                'selector': ('div', {'class': 'Single-article WebContent'}),
            }
            
        }


    def get_url_from_text(self, text: str):
        url_regex = re.compile(r'^https?://\S+')
        match = re.search(url_regex, text)
        if match:
            return match.group()
        else:
            return None

    def get_soup_from_url(self,url: str,timeout=50,**attrs):
        
        # headers = ''
        hotpage = requests.get(url,timeout=timeout, **attrs)
        soup = BeautifulSoup(hotpage.text, 'html.parser')
        return soup


    def get_content_from_url_user_def(self,url: str):
        sites_info = self.sites_info
        for key, info in sites_info.items():
            if key in url:
                headers = info.get('headers',DEFAULT_HEADER)
                tag ,attrs = info.get('selector',DEFAULT_SELECTOR)
                cookies =  info.get('cookies')
                soup = self.get_soup_from_url(url,headers=headers,cookies=cookies)
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
    
    def get_content_from_url_text(self,url: str):
 
        soup = self.get_soup_from_url(url)    
        chunks= [soup.text]

        return chunks
    
    def get_content_from_url_text_by_ai(self,url: str):
        url_jina = 'https://r.jina.ai/'
        print(f'selectors:jina.ai')
        soup = self.get_soup_from_url(url_jina+url)    
        chunks= [soup.text]

        return chunks        
  
    def get_content_from_url(self, url: str):
        chunks = self.get_content_from_url_user_def(url)
        if chunks:
            return chunks
        chunks = self.get_content_from_url_common(url)
        if chunks:
            return chunks
        chunks = self.get_content_from_url_text_by_ai(url)
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
        self.text_length_limit = 8000
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
