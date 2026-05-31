from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

deepseek_model = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL_NAME"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    extra_body={"thinking":{"type":"disabled"}}
)