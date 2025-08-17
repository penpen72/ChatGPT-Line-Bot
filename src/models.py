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
        """Search the web via Jina Search (Bing deprecated).

        NOTE: `market` param kept for backward compatibility but ignored.

        Reference:
            curl "https://s.jina.ai/?q=penguin" \\
              -H "Accept: application/json" \\
              -H "Authorization: Bearer <JINA_API_KEY>" \\
              -H "X-Respond-With: no-content"

        Normalized return shape: list[{'name': str, 'snippet': str, 'url': str}].
        This matches expectations in chat_with_ext_second_response().
        """
        jina_key = os.getenv('JINA_API_KEY', ).strip()
        # print(f'Jina API Key: {jina_key[:4]}...{jina_key[-4:]}')  # Debugging only, do not log full key
        base_url = "https://s.jina.ai/"
        headers = {
            # Use the key exactly as provided in env (do NOT append or trim characters)
            "Authorization": f"Bearer {jina_key}" if jina_key else None,
            # Ensure JSON response
            "Accept": "application/json",
            # Request minimal/no extra content (can remove if full content desired)
            "X-Respond-With": "no-content",
        }
        # Drop None headers
        headers = {k: v for k, v in headers.items() if v is not None}
        params = {"q": query}
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            # Return a single synthetic result on failure
            return [{
                'name': query,
                'snippet': f'Jina search failed: {e}',
                'url': ''
            }]

        # Parse documented JSON format first; fallback to plain text
        results = []
        try:
            data = resp.json()
            candidates = []
            # Primary key in documented response
            if isinstance(data, dict):
                if isinstance(data.get('data'), list):
                    candidates = data['data']
                else:
                    # Fallback alternative keys
                    for key in ('results', 'items'):
                        if isinstance(data.get(key), list):
                            candidates = data[key]
                            break
                    if not candidates and any(k in data for k in ('title', 'url', 'description', 'snippet')):
                        candidates = [data]
            elif isinstance(data, list):
                candidates = data

            for item in candidates[:count]:
                if not isinstance(item, dict):
                    continue
                title = item.get('title') or item.get('name') or item.get('url') or 'result'
                snippet = item.get('description') or item.get('snippet') or ''
                url = item.get('url') or ''
                results.append({'name': title, 'snippet': snippet, 'url': url})
        except ValueError:
            # Non-JSON response fallback
            text = resp.text.strip()
            if text:
                preview_lines = [l for l in text.splitlines() if l.strip()] or [text]
                first = preview_lines[0][:80]
                snippet = text[:200].replace('\n', ' ')
                results.append({'name': first, 'snippet': snippet, 'url': ''})

        if not results:
            # Final safety fallback
            body_preview = (resp.text or '')[:200].replace('\n', ' ')
            results = [{'name': query, 'snippet': body_preview, 'url': ''}]

        print(f'Jina search params={params} results_count={len(results)}')
        return results

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
           



