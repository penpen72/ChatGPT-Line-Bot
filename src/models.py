from typing import List, Dict
import requests
import os
import json

class ModelInterface:
    def check_token_valid(self) -> bool:
        pass

    def chat_completions(self, messages: List[Dict], model_engine: str) -> str:
        pass

    def audio_transcriptions(self, file, model_engine: str) -> str:
        pass

    def image_generations(self, prompt: str) -> str:
        pass


class OpenAIModel(ModelInterface):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.openai.com/v1'
        self.available_functions = {
            "search_web": self.search_web,
        }

    def _request(self, method, endpoint, body=None, files=None):
        self.headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        try:
            if method == 'GET':
                r = requests.get(f'{self.base_url}{endpoint}', headers=self.headers)
            elif method == 'POST':
                if body:
                    self.headers['Content-Type'] = 'application/json'
                r = requests.post(f'{self.base_url}{endpoint}', headers=self.headers, json=body, files=files)
            r = r.json()
            if r.get('error'):
                return False, None, r.get('error', {}).get('message')
        except Exception:
            return False, None, 'OpenAI API 系統不穩定，請稍後再試'
        return True, r, None

    def check_token_valid(self):
        return self._request('GET', '/models')

    def chat_completions(self, messages, model_engine,**kargs) -> str:
        json_body = {
            'model': model_engine,
            'messages': messages,
            'max_completion_tokens':4096,
            'verbosity': 'low',
            **kargs
        }
        return self._request('POST', '/chat/completions', body=json_body)

    def audio_transcriptions(self, file_path, model_engine) -> str:
        files = {
            'file': open(file_path, 'rb'),
            'model': (None, model_engine),
        }
        return self._request('POST', '/audio/transcriptions', files=files)

    def image_generations(self, prompt: str) -> str:
        json_body = {
            "model":"dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            'quality':"standard"
        }
        return self._request('POST', '/images/generations', body=json_body)
    
    def image_recognition(self, image_data: str, model_engine: str = "gpt-4o") -> str:
        json_body = {
            "model": model_engine,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f'data:image/jpeg;base64,{image_data}',
                                # "detail": "low" # low, high, or auto
                            }
                        },
                        {
                            "type": "text",
                            "text": "仔細觀察圖片上面的所有細節包含文字。詳細描述圖片上的內容並說明；如果你覺得他是個meme，說明他想傳達的情境，如果不是就不用特別說明"
                            
                        }
                    ]
                }
            ],
            "temperature": 1,
            # "max_tokens": 1024,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }

        return self._request('POST', '/chat/completions', body=json_body)

    def search_web(self, query, market="zh-TW", count=5):
        subscription_key = os.getenv('BING_SEARCH_V7_SUBSCRIPTION_KEY')
        search_url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": subscription_key}
        params = {
            "q": query,
            "textDecorations": True,
            "textFormat": "HTML",
            "mkt": market,  # 指定語言/市場
            "count": count  # 指定搜尋結果數量
        }
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()
        print(f'{params=}')
        # print(f'{search_results=}')
        return search_results["webPages"]["value"]

    def chat_with_ext(self, messages, model_engine,**karg):
 
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        
        return self.chat_completions(messages=messages, model_engine=model_engine,tools=tools,tool_choice="auto")

    def chat_with_ext_second_response(self,messages,response,tool_calls,model_engine):

        response_message = response['choices'][0]['message']
        messages.append(response_message)
        
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            print(f"using {function_name}")
            function_to_call = self.available_functions[function_name]
            # print(f'{function_to_call=}')
            function_args = json.loads(tool_call['function']['arguments'])
            # print(f'{function_args=}')
            function_response = function_to_call(query=function_args.get("query"))
            # print(f'{function_response=}')
            search_summary = ""
            for result in function_response:
                search_summary += f"- {result['name']}: {result['snippet']} (URL: {result['url']})\n"
            # print(f'{messages=}')
            messages.append(
                {
                    "tool_call_id": tool_call['id'],
                    "role": "tool",
                    "name": function_name,
                    "content": search_summary,
                }
            )
        
        
        return self.chat_completions(messages=messages, model_engine=model_engine)
           



