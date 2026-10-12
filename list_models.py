import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("대화에 쓸 수 있는 Flash 계열 모델:")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if "generateContent" in actions and "flash" in m.name:
        print(" -", m.name.replace("models/", ""))