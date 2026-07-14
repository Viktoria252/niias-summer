import base64
import logging
from typing import Optional, Union, List

import httpx
from src.config import VLLM_URL, MODEL_NAME, VLLM_TIMEOUT

logger = logging.getLogger(__name__)

class VLLMClient:
    def __init__(
        self,
        base_url: str = VLLM_URL,
        model: str = MODEL_NAME,
        timeout: int = VLLM_TIMEOUT,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def _encode_image_to_base64(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def recognize(
        self,
        images: Union[bytes, List[bytes]],
        prompt: str = """Распознай текст на изображении и извлеки следующие поля в формате JSON:
- Место отказа (дорога, станция, перегон, км, пикеты)
- Дата (год-месяц-день)
- Время начала отказа (часы-минуты)
- Серия локомотива
- Номер секции локомотива
- Договор (номер и наименование)
- Причина отказа
- Вид отказа (производственный, деградационный и т.п.)
- Оборудование локомотива
- Наименование виновной организации (строго название компании в кавычках)

Если какое-то поле отсутствует, оставь его пустым или со значением null.
Ответ дай строго в виде JSON без пояснений.""",
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> str:

        if isinstance(images, bytes):
            images = [images]

        content = []
        for image_bytes in images:
            image_base64 = self._encode_image_to_base64(image_bytes)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        content.append({
            "type": "text",
            "text": prompt
        })

        messages = [{"role": "user", "content": content}]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "mm_processor_kwargs": {"enable_thinking": True},
        }

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