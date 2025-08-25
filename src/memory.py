from typing import Dict, List, Union, Any
from collections import defaultdict
from datetime import datetime, timedelta


class MemoryInterface:
    def append(self, user_id: str, message: Dict) -> None:
        pass

    def get(self, user_id: str) -> List[Dict]:
        return []

    def remove(self, user_id: str) -> None:
        pass


class Memory(MemoryInterface):
    def __init__(self, system_message, memory_message_count):
        self.storage = defaultdict(list)
        self.system_messages = defaultdict(str)
        self.default_system_message = system_message
        self.memory_message_count = memory_message_count

    def _get_current_time_prefix(self):
        """獲取當前時間前綴"""
        return (datetime.now() + timedelta(hours=8)).strftime("[current_time:%Y-%m-%d %Hh%Mm%Ss]")

    def _get_system_message_with_time(self, user_id: str):
        """獲取包含時間的系統訊息"""
        base_message = self.system_messages.get(user_id) or self.default_system_message
        current_time = self._get_current_time_prefix()
        return f'{current_time} {base_message}'

    def _initialize(self, user_id: str):
        self.storage[user_id] = [{
            'role': 'system', 
            'content': self._get_system_message_with_time(user_id)
        }]

    def _drop_message(self, user_id: str):
        if len(self.storage.get(user_id)) >= (self.memory_message_count + 1) * 2 + 1:
            self.storage[user_id] = [self.storage[user_id][0]] + self.storage[user_id][-(self.memory_message_count * 2):]

    def change_system_message(self, user_id, system_message):
        self.system_messages[user_id] = system_message
        # 如果用戶已經有對話歷史，更新系統訊息
        if len(self.storage[user_id]) > 0:
            self.storage[user_id][0]['content'] = self._get_system_message_with_time(user_id)
        # self.remove(user_id)
   
            

    def append(self, user_id: str, role: str, content: Union[str, List[Dict[str, Any]]]) -> None:
        if len(self.storage[user_id]) == 0:
            self._initialize(user_id)
        else:
            # 在每次 append 時更新系統訊息的時間
            self.storage[user_id][0]['content'] = self._get_system_message_with_time(user_id)
        
        self.storage[user_id].append({
            'role': role,
            'content': content
        })
        self._drop_message(user_id)

    def get(self, user_id: str) -> List[Dict]:
        return self.storage[user_id]

    def remove(self, user_id: str) -> None:
        self.storage[user_id] = []
