from typing import List, Dict
import requests


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

    def chat_completions(self, messages, model_engine) -> str:
        json_body = {
            'model': model_engine,
            'messages': messages,
            'max_tokens':1024,
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
                                "url": image_data,
                                "detail": "low" # low, high, or auto
                            }
                        },
                        {
                            "type": "text",
                            "text": "詳細觀察這張圖片上面的所有東西，並說明這張圖片上有什麼或是這張圖片再說什麼"
                            
                        }
                    ]
                }
            ],
            "temperature": 1,
            "max_tokens": 1024,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }

        return self._request('POST', '/chat/completions', body=json_body)