import os
import re
import requests
from bs4 import BeautifulSoup

WEBSITE_SYSTEM_MESSAGE = """
你是一名專業的資料分析與摘要專家，擅長深入理解文章或網頁內容，快速識別核心主題與關鍵資訊。你具備以下能力：

1. 清晰精準地總結資料內容與重點。
2. 辨識並列出關鍵的數據、事實、觀點與建議。
3. 提供有洞察力且客觀的觀察或見解。
4. 不遺漏重要細節，同時能簡化複雜內容並以結構化的形式呈現。

你的回答應該簡潔明確，重點清晰，不包含多餘資訊。

"""

WEBSITE_MESSAGE_FORMAT = """
\"\"\"
{}
\"\"\"

以上內容為網頁或文章原文，請你依據以下步驟回答：

【摘要】：清楚說明該文章或網頁的核心主題。
【重點】：整理出文中提及的重要觀點、事實或數據（至少3點，至多5點）。
【分析】：提出你認為值得注意的觀察或見解（至少一句）。

請以條列、結構化方式回答，總字數介於100至450字之間。
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
            },
            'tw.nextapple.com':{
                'selector': ('div', {'class': 'post-content'})
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
        self.text_length_limit = 45000
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
