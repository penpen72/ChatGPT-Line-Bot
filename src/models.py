from typing import List, Dict
import requests
import os
import json
from .utils import get_role_and_content, get_tool_calls

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
                if files:
                    # For file uploads, don't set Content-Type (let requests handle it)
                    r = requests.post(f'{self.base_url}{endpoint}', headers=self.headers, files=files)
                else:
                    # For JSON data
                    self.headers['Content-Type'] = 'application/json'
                    r = requests.post(f'{self.base_url}{endpoint}', headers=self.headers, json=body)
            r = r.json()
            if r.get('error'):
                return False, None, r.get('error', {}).get('message')
        except Exception:
            return False, None, 'OpenAI API 系統不穩定，請稍後再試'
        return True, r, None

    def check_token_valid(self):
        return self._request('GET', '/models')

    def chat_completions(self, messages, model_engine, **kwargs) -> str:
        json_body = {
            'model': model_engine,
            'messages': messages,
            'max_completion_tokens': 4096,
            'verbosity': 'low',
            **kwargs
        }
        return self._request('POST', '/chat/completions', body=json_body)

    def audio_transcriptions(self, file_path, model_engine) -> str:
        try:
            with open(file_path, 'rb') as audio_file:
                files = {
                    'file': audio_file,
                    'model': (None, model_engine),
                }
                return self._request('POST', '/audio/transcriptions', files=files)
        except FileNotFoundError:
            return False, None, f'找不到檔案: {file_path}'
        except Exception as e:
            return False, None, f'讀取音訊檔案時發生錯誤: {str(e)}'

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

    def search_web(self, query):
        """Search the web via Jina Search (Bing deprecated).

        Reference:
            curl "https://s.jina.ai/?q=penguin" \\
              -H "Accept: application/json" \\
              -H "Authorization: Bearer <JINA_API_KEY>" \\
              -H "X-Respond-With: no-content"

        Normalized return shape: list[{'name': str, 'snippet': str, 'url': str}].
        This matches expectations in chat_with_ext_second_response().
        """
        jina_key = os.getenv('JINA_API_KEY', '').strip()
        if not jina_key:
            return [{
                'name': query,
                'snippet': 'Jina API key not found in environment variables',
                'url': ''
            }]
            
        # print(f'Jina API Key: {jina_key[:4]}...{jina_key[-4:]}')  # Debugging only, do not log full key
        base_url = "https://s.jina.ai/"
        headers = {
            # Use the key exactly as provided in env (do NOT append or trim characters)
            "Authorization": f"Bearer {jina_key}",
            # Ensure JSON response
            "Accept": "application/json",
            # Request minimal/no extra content (can remove if full content desired)
            "X-Respond-With": "no-content",
        }
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

            for item in candidates:
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

    def chat_with_ext(self, messages, model_engine, **kwargs):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web for current information. Use this tool sparingly and only when you need up-to-date information that's not in your training data. Limit to 1-2 searches per conversation unless absolutely necessary. Think carefully before each search - can you answer with existing knowledge first?",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query - be specific and focused to get the most relevant results"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        return self.chat_completions(messages=messages, model_engine=model_engine, tools=tools, tool_choice="auto", parallel_tool_calls=False, **kwargs)


    def chat_with_ext_second_response(self, messages, response, tool_calls, model_engine):
        # 建立臨時 messages 副本，確保原始對話不會被意外修改
        updated_messages = list(messages)

        response_message = response['choices'][0]['message']
        updated_messages.append(response_message)

        print(f"🔧 Processing {len(tool_calls)} tool call(s):")

        for i, tool_call in enumerate(tool_calls):
            function_name = tool_call['function']['name']
            function_args = json.loads(tool_call['function']['arguments'])
            query = function_args.get("query", "")

            print(f"   {i+1}. Function: {function_name}")
            print(f"      Query: {query}")

            function_to_call = self.available_functions[function_name]
            function_response = function_to_call(query=query)

            # 整理查詢結果摘要供模型閱讀
            search_summary = ""
            result_count = len(function_response) if function_response else 0

            for result in function_response:
                search_summary += f"- {result['name']}: {result['snippet']} (URL: {result['url']})\n"

            if not search_summary.strip():
                search_summary = "（查無相關搜尋結果）"

            print(f"      Results: {result_count} items found")
            if result_count > 0:
                print(f"      First result: {function_response[0]['name'][:50]}...")

            # 回傳工具結果給模型
            updated_messages.append(
                {
                    "tool_call_id": tool_call['id'],
                    "role": "tool",
                    "name": function_name,
                    "content": search_summary,
                }
            )

        print(f"📤 Sending final request with {len(updated_messages)} messages")
        is_successful, final_response, error_message = self.chat_completions(messages=updated_messages, model_engine=model_engine)
        if not is_successful:
            return False, None, error_message, updated_messages

        final_message = final_response['choices'][0]['message']
        updated_messages.append(final_message)

        return True, final_response, None, updated_messages


    def _finalize_with_tool_limit(self, current_messages, model_engine, max_tool_calls):
        """Guide the model to answer with existing information once the tool limit is reached."""
        current_messages.append({
            "role": "system",
            "content": f"已達到搜尋工具次數上限（{max_tool_calls} 次）。請改用目前掌握的資訊整理回答，並向使用者說明無法再搜尋。"
        })

        is_successful, response, error_message = self.chat_completions(current_messages, model_engine)
        if not is_successful:
            return False, None, error_message, current_messages

        final_message = response['choices'][0]['message']
        current_messages.append(final_message)

        final_role = final_message.get('role', 'assistant')
        final_content = final_message.get('content', '')

        return True, {'role': final_role, 'content': final_content}, None, current_messages

    def chat_with_ext_multi_turn(self, messages, model_engine, max_iterations=15, max_tool_calls=10, **kwargs):
        """
        處理多輪 tool calling，支援 AI 進行多次工具調用直到獲得最終回應
        
        Args:
            messages: 對話訊息列表
            model_engine: 模型引擎名稱
            max_iterations: 最大迭代次數，避免無限循環
            max_tool_calls: 最大工具調用總次數，避免過度使用
            **kwargs: 其他傳遞給 chat_completions 的參數
            
        Returns:
            tuple: (is_successful, final_response, error_message)
        """
        print(f"🚀 Starting multi-turn tool calling (max iterations: {max_iterations}, max tool calls: {max_tool_calls})")
        
        iteration_count = 0
        total_tool_calls = 0
        current_messages = list(messages)
        
        while iteration_count < max_iterations:
            iteration_count += 1
            print(f"🔄 Tool calling iteration {iteration_count}/{max_iterations}")
            
            # 發送帶有工具的請求
            is_successful, response, error_message = self.chat_with_ext(current_messages, model_engine, **kwargs)
            if not is_successful:
                return False, None, error_message
            
            # 檢查是否有工具調用
            tool_calls = get_tool_calls(response)
            if not tool_calls:
                print(f"✅ No tool calls needed. Completed in {iteration_count} iteration(s)")
                role, response_content = get_role_and_content(response)
                return True, {'role': role, 'content': response_content}, None
            
            # 檢查工具調用次數限制
            remaining_tool_calls = max_tool_calls - total_tool_calls
            if remaining_tool_calls <= 0:
                print(f"⚠️ Tool call limit reached ({total_tool_calls}/{max_tool_calls}). Forcing response with existing information.")
                is_successful, result, error_message, _ = self._finalize_with_tool_limit(current_messages, model_engine, max_tool_calls)
                return is_successful, result, error_message

            tool_calls_to_process = tool_calls[:remaining_tool_calls]
            limit_reached_this_round = len(tool_calls_to_process) < len(tool_calls)

            total_tool_calls += len(tool_calls_to_process)
            print(f"🔧 Found {len(tool_calls_to_process)} tool call(s) in iteration {iteration_count} (total: {total_tool_calls}/{max_tool_calls}):")
            for i, tool_call in enumerate(tool_calls_to_process):
                function_name = tool_call.get('function', {}).get('name', 'unknown')
                function_args = tool_call.get('function', {}).get('arguments', '{}')
                try:
                    args_dict = json.loads(function_args)
                    query = args_dict.get('query', '')
                    display_query = query[:50] + '...' if len(query) > 50 else query
                    print(f"   {i+1}. {function_name}(query='{display_query}')")
                except:
                    print(f"   {i+1}. {function_name}")

            # 處理工具調用
            is_successful, response, error_message, updated_messages = self.chat_with_ext_second_response(current_messages, response, tool_calls_to_process, model_engine)
            if not is_successful:
                return False, None, error_message

            current_messages = updated_messages

            if limit_reached_this_round or total_tool_calls >= max_tool_calls:
                print(f"⚠️ Tool call limit reached ({total_tool_calls}/{max_tool_calls}). Responding with gathered information.")
                is_successful, result, error_message, _ = self._finalize_with_tool_limit(current_messages, model_engine, max_tool_calls)
                return is_successful, result, error_message

            print(f"📝 Tool call results processed for iteration {iteration_count}")

            # 檢查新的回應是否還包含 tool calls
            new_tool_calls = get_tool_calls(response)
            if not new_tool_calls:
                print(f"✅ Final response received. Total iterations: {iteration_count}, Total tool calls: {total_tool_calls}")
                role, response_content = get_role_and_content(response)
                print(f"🏁 Tool calling completed. Total iterations: {iteration_count}, Total tool calls: {total_tool_calls}")
                return True, {'role': role, 'content': response_content}, None
            else:
                print(f"🔄 Response contains {len(new_tool_calls)} more tool call(s), continuing...")
                # 更新 current_messages，注意這裡 chat_with_ext_second_response 已經更新了對話
                # 我們需要重新構建 messages 包含所有的工具調用歷史
                # 但由於 memory 管理在外部，這裡我們暫時使用原始 messages
                pass
        
        # 達到最大迭代次數
        print(f"⚠️ Reached maximum iterations ({max_iterations}). Stopping tool calling.")
        role, response_content = get_role_and_content(response)
        final_content = f"處理完成（達到最大迭代次數 {max_iterations}）：\n{response_content}"
        print(f"🏁 Tool calling completed with max iterations. Total iterations: {iteration_count}, Total tool calls: {total_tool_calls}")
        return True, {'role': role, 'content': final_content}, None
           



