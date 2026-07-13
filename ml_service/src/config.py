import os
from dotenv import load_dotenv

load_dotenv()

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "baidu/Qianfan-OCR")
VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "120"))