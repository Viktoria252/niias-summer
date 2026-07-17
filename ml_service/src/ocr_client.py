# Клиент в случае, если мы испольщуем vLLM (требует видеокарту NVIDIA). Сейчас это НЕ НУЖНО!!!

# import base64
# import logging
# from typing import List, Optional
#
# import httpx
# from src.config import VLLM_URL, MODEL_NAME, VLLM_TIMEOUT
#
# logger = logging.getLogger(__name__)
#
# class VLLMClient:
#     def __init__(
#         self,
#         base_url: str = VLLM_URL,
#         model: str = MODEL_NAME,
#         timeout: int = VLLM_TIMEOUT,
#     ):
#         self.base_url = base_url
#         self.model = model
#         self.timeout = timeout
#
#     def _encode_image_to_base64(self, image_bytes: bytes) -> str:
#         """Кодирует байты изображения в строку base64."""
#         return base64.b64encode(image_bytes).decode("utf-8")
#
#     async def _call_model(
#         self,
#         images: List[bytes],
#         prompt: str,
#         max_tokens: int = 512,
#         temperature: float = 0.0,
#     ) -> str:
#         """
#         Отправляет запрос  с несколькими изображениями и текстовым промптом.
#         Возвращает сгенерированный текст.
#         """
#         # Формируем content: сначала все изображения, затем текст
#         content = []
#         for img_bytes in images:
#             b64 = self._encode_image_to_base64(img_bytes)
#             content.append({
#                 "type": "image_url",
#                 "image_url": {"url": f"data:image/png;base64,{b64}"}
#             })
#         content.append({"type": "text", "text": prompt})
#
#         messages = [{"role": "user", "content": content}]
#         payload = {
#             "model": self.model,
#             "messages": messages,
#             "max_tokens": max_tokens,
#             "temperature": temperature,
#         }
#
#         # Используем асинхронный клиент внутри контекстного менеджера
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             try:
#                 response = await client.post(
#                     f"{self.base_url}/v1/chat/completions",
#                     json=payload,
#                 )
#                 response.raise_for_status()
#                 result = response.json()
#                 return result["choices"][0]["message"]["content"]
#             except httpx.HTTPStatusError as e:
#                 logger.error(f"HTTP error from vLLM: {e.response.text}")
#                 raise
#             except Exception as e:
#                 logger.error(f"Error calling vLLM: {e}")
#                 raise
#
#     async def recognize_markdown(self, images: List[bytes], max_tokens: int = 512) -> str:
#         """Распознаёт текст с изображений и возвращает его в формате Markdown."""
#         prompt = (
#             "Распознай текст на изображениях и верни его в формате Markdown. "
#             "Сохрани структуру (заголовки, списки, таблицы), если они есть."
#         )
#         return await self._call_model(images, prompt, max_tokens)
#
#     async def recognize_json(self, images: List[bytes], max_tokens: int = 512) -> str:
#         """Извлекает структурированные данные с изображений и возвращает JSON."""
#         prompt = """Распознай текст на изображении и извлеки следующие поля в формате JSON:
# - Место отказа (дорога, станция, перегон, км, пикеты)
# - Дата (год-месяц-день)
# - Время начала отказа (часы-минуты)
# - Серия локомотива
# - Номер секции локомотива
# - Договор (номер и наименование)
# - Причина отказа
# - Вид отказа (производственный, деградационный и т.п.)
# - Оборудование локомотива
# - Наименование виновной организации (строго название компании в кавычках)
#
# Если какое-то поле отсутствует, оставь его пустым или со значением null.
# Ответ дай строго в виде JSON без пояснений."""
#         return await self._call_model(images, prompt, max_tokens)