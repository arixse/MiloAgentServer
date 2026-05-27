from langchain_openai import ChatOpenAI
from langchain_nvidia_ai_endpoints import ChatNVIDIA
import os
from dotenv import load_dotenv
load_dotenv()
model = ChatNVIDIA(
    model="nvidia/nemotron-3-super-120b-a12b"
)

deepseek_model = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL_NAME"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    extra_body={"thinking":{"type":"disabled"}}
)