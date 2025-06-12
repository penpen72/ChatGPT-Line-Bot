import math
import os
import re
from src.utils import get_role_and_content

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled
)
from youtube_transcript_api.proxies import GenericProxyConfig

YOUTUBE_SYSTEM_MESSAGE = """
你是一位專業且細心的影片內容分析專家，專門負責從 YouTube 影片的字幕中整理重點、總結核心資訊及細節，具備以下特質：

1. 擅長逐段摘要並捕捉關鍵資訊。
2. 能夠整合多段摘要，並提煉出整體影片的核心重點。
3. 注意細節並能適時指出有價值的觀察或深入見解。
4. 使用清晰、精簡且結構化的語言呈現你的分析與總結。

你的回覆必須有邏輯性、精確且全面，避免冗餘資訊。
"""
PART_MESSAGE_FORMAT = """ PART {} START\n下面是一個 Youtube 影片的部分字幕： \"\"\"{}\"\"\" \n\n請總結出這部影片的重點與一些細節，字數約 400 字左右\nPART {} END\n"""
WHOLE_MESSAGE_FORMAT = ("下面是每一個部分的小結論：\"\"\"{}\"\"\" \n\n "
                      "請給我全部小結論的總結，字數約 400 字左右")
SINGLE_MESSAGE_FORMAT = ("下面是一個 Youtube 影片的字幕： \"\"\"{}\"\"\" "
                         "\n\n請總結出這部影片的重點與一些細節，字數約 400 字左右")


class Youtube:
    def __init__(self, step=1):
        """
        :param step: 用來控制每隔多少行字幕取一次，可用於減少無用字幕量
        """
        self.step = step
        self.chunk_size = 45000
        # 如果需要使用代理則在環境變數中指定 PROXY_URL
        self.proxy_url = os.getenv("PROXY_URL")
        self.proxy_config = None
        if self.proxy_url:
            self.proxy_config = GenericProxyConfig(
                # http_url=self.proxy_url,
                https_url=self.proxy_url
            )

        # 可以透過環境變數來控制是否保留字幕格式，如 <i>, <b>
        preserve_env = os.getenv("PRESERVE_FORMATTING", "false").lower()
        self.preserve_formatting = (preserve_env == "true")

    def get_transcript_chunks(self, video_id):
        """
        根據最新的 youtube_transcript_api 使用 fetch() 方法並回傳分段後的字幕。
        :param video_id: YouTube 影片 ID
        :return: (bool, list_of_chunks, error_msg)
        """
        # 先檢查 video_id 是否有效
        if not video_id or not isinstance(video_id, str):
            return False, [], "無效的影片 ID，請確認是否正確傳入"

        try:
            # 建立 YouTubeTranscriptApi 實例，包含可選的 proxy_config
            ytt_api = YouTubeTranscriptApi(
                proxy_config=self.proxy_config
            )
            # 透過 fetch() 取得 FetchedTranscript 物件，再使用 to_raw_data() 取得原始字幕列表
            fetched_transcript = ytt_api.fetch(
                video_id,
                # 可自行調整想要的語言優先順序
                languages=[
                    'zh-TW', 'zh', 'zh-CN', 'ja', 'zh-Hant', 'zh-Hans', 'en', 'ko'
                ],
                preserve_formatting=self.preserve_formatting
            )

            raw_data = fetched_transcript.to_raw_data()

            # 依據 step 篩選出所需要的字幕
            text = [t.get('text', '') for i, t in enumerate(raw_data) if i % self.step == 0]
            # 再將結果按照 chunk_size 切割成多個區塊
            chunks = [
                '\n'.join(text[i * self.chunk_size : (i + 1) * self.chunk_size])
                for i in range(math.ceil(len(text) / self.chunk_size))
            ]

        except NoTranscriptFound:
            return False, [], '目前只支援：中文、英文、日文、韓文'
        except TranscriptsDisabled:
            return False, [], '本影片無開啟字幕功能'
        except Exception as e:
            return False, [], str(e)

        return True, chunks, None

    def retrieve_video_id(self, url):
        """
        從網址中抓取影片 ID
        例如 https://www.youtube.com/watch?v=12345 抓出 12345
        """
        if not url:
            return None
        regex = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        match = re.search(regex, url)
        if match:
            return match.group(1)
        else:
            return None


class YoutubeTranscriptReader:
    def __init__(self, model=None, model_engine=None):
        """
        用於根據分段好的字幕進行摘要。
        :param model: LLM 模型實例
        :param model_engine: 模型引擎或其他參數
        """
        self.summary_system_prompt = os.getenv('YOUTUBE_SYSTEM_MESSAGE') or YOUTUBE_SYSTEM_MESSAGE
        self.part_message_format = os.getenv('PART_MESSAGE_FORMAT') or PART_MESSAGE_FORMAT
        self.whole_message_format = os.getenv('WHOLE_MESSAGE_FORMAT') or WHOLE_MESSAGE_FORMAT
        self.single_message_format = os.getenv('SINGLE_MESSAGE_FORMAT') or SINGLE_MESSAGE_FORMAT
        self.model = model
        self.model_engine = model_engine

    def send_msg(self, msg):
        """
        透過 self.model.chat_completions 對話模型進行問答。
        msg: [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        return self.model.chat_completions(msg, self.model_engine)

    def summarize(self, chunks):
        """
        對多個 chunk 的字幕進行分段摘要，最後再整合成總結。
        :param chunks: list of subtitle chunks
        :return: 回傳最終的摘要結果
        """
        summary_msg = []
        print(f'chunks size: {len(chunks)}')

        if len(chunks) > 1:
            # 有多個 chunk，需要逐段摘要，最後合併
            for i, chunk in enumerate(chunks):
                msgs = [
                    {
                        "role": "system",
                        "content": self.summary_system_prompt
                    },
                    {
                        "role": "user",
                        "content": self.part_message_format.format(i, chunk, i)
                    }
                ]
                _, response, _ = self.send_msg(msgs)
                _, content = get_role_and_content(response)
                summary_msg.append(content)

            # 將多段摘要結果合併為一個字串
            merged_text = '\n'.join(summary_msg)

            # 再針對所有小結進行最終的整合摘要
            msgs = [
                {
                    'role': 'system',
                    'content': self.summary_system_prompt
                },
                {
                    'role': 'user',
                    'content': self.whole_message_format.format(merged_text)
                }
            ]
            return self.send_msg(msgs)

        else:
            # 只有一段字幕
            text = chunks[0] if chunks else ''
            msgs = [
                {
                    'role': 'system',
                    'content': self.summary_system_prompt
                },
                {
                    'role': 'user',
                    'content': self.single_message_format.format(text)
                }
            ]
            return self.send_msg(msgs)
