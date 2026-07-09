import base64
import logging
from typing import Optional

import httpx
from src.config import VLLM_URL, MODEL_NAME, VLLM_TIMEOUT, ENABLE_THINKING

logger = logging.getLogger(__name__)

class VLLMClient:
    def __init__(
        self,
        base_url: str = VLLM_URL,
        model: str = MODEL_NAME,
        timeout: int = VLLM_TIMEOUT,
        enable_thinking: bool = ENABLE_THINKING,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def _encode_image_to_base64(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def recognize(
        self,
        image_bytes: bytes,
        prompt: str = "Извлеки следующие данные в JSON-формате: ",
        max_tokens: int = 512,
        temperature: float = 0.0,
        enable_thinking: bool = None,
    ) -> str:
        thinking = enable_thinking if enable_thinking is not None else self.enable_thinking

        image_base64 = self._encode_image_to_base64(image_bytes)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if thinking:
            payload["mm_processor_kwargs"] = {"enable_thinking": True}

        try:
            response = self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from vLLM: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling vLLM: {e}")
            raise