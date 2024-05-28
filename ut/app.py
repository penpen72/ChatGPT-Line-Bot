from flask import Flask, request, render_template, redirect, url_for
import os
import uuid
from PIL import Image
from dotenv import load_dotenv

from src.models import OpenAIModel
from src.memory import Memory
from src.utils import get_role_and_content

# 載入環境變數
load_dotenv('.env')

app = Flask(__name__)

# 配置圖片上傳路徑
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 初始化模型和記憶體
memory = Memory(system_message=os.getenv('SYSTEM_MESSAGE'),
                memory_message_count=2)
model_management = {}
TARGET_RESOLUTION = (512, 512)  # 目標解析度

# 初始化OpenAI模型
api_key = os.getenv('OPENAI_API_KEY')
model = OpenAIModel(api_key=api_key)

@app.route('/')
def home():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{uuid.uuid4()}.jpg')
        file.save(file_path)

        # 縮放圖片到目標解析度
        with Image.open(file_path) as img:
            img = img.resize(TARGET_RESOLUTION)
            img.save(file_path)

        # 將圖片傳送給OpenAI進行處理
        is_successful, response, error_message = model.process_image(file_path)
        if not is_successful:
            return f"Error: {error_message}"

        os.remove(file_path)
        return f"Processed Result: {response}"

    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)
