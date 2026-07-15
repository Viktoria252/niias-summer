import logging
import hashlib
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from src.config import MODEL_NAME
from src.models import OCRResponse
import uvicorn

# Работа с документами и изображениями
from pdf2image import convert_from_bytes
from PIL import Image
import io
import os

# Transformers и PyTorch
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoImageProcessor
import torch.nn.functional as F

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MiResult OCR Service (PyTorch)", version="3.0")

MODEL_PATH = MODEL_NAME  # "baidu/Qianfan-OCR" или локальный путь
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Используем устройство: {DEVICE}")

# Загружаем модель, токенизатор и процессор изображений
try:
    # Qianfan-OCR базируется на InternVL, используем AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
        trust_remote_code=True,
        device_map="auto" if DEVICE == "cuda" else None,  # для CPU можно оставить None
        low_cpu_mem_usage=True
    )
    if DEVICE == "cpu":
        model = model.to(DEVICE)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    # Используем процессор для изображений (InternVLImageProcessor)
    image_processor = AutoImageProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
    logger.info("Модель успешно загружена")
except Exception as e:
    logger.error(f"Не удалось загрузить модель: {e}")
    raise


def detect_file_type(content_type: str, filename: str) -> str:
    if content_type:
        if "pdf" in content_type:
            return "pdf"
        if "word" in content_type or "docx" in content_type:
            return "docx"
        if "msword" in content_type:
            return "doc"
    ext = filename.lower().split('.')[-1]
    if ext in ("pdf",):
        return "pdf"
    if ext in ("docx",):
        return "docx"
    if ext in ("doc",):
        return "doc"
    return "unknown"


def convert_docx_to_pdf_bytes(docx_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "input.docx"
        pdf_path = Path(tmpdir) / "output.pdf"
        docx_path.write_bytes(docx_bytes)
        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(pdf_path.parent), str(docx_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        return pdf_path.read_bytes()


def doc_to_pdf_bytes(doc_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "input.doc"
        pdf_path = Path(tmpdir) / "output.pdf"
        doc_path.write_bytes(doc_bytes)
        cmd = ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(pdf_path.parent), str(doc_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        return pdf_path.read_bytes()


def pdf_bytes_to_images(pdf_bytes: bytes) -> List[bytes]:
    images = convert_from_bytes(pdf_bytes, dpi=200, fmt='png')
    image_bytes_list = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        image_bytes_list.append(buf.getvalue())
    return image_bytes_list

def generate_response(images: List[bytes], prompt: str, max_new_tokens: int = 512) -> str:
    """
    Принимает список байтов изображений (PNG) и текстовый промпт,
    возвращает сгенерированный текст.
    """
    # Конвертируем байты в PIL Image
    pil_images = [Image.open(io.BytesIO(img)) for img in images]

    # Подготавливаем входные данные: изображения + текст
    # Для InternVL используется формат: text + изображения
    # Сначала обрабатываем изображения через процессор
    pixel_values = image_processor(pil_images, return_tensors="pt").pixel_values
    if DEVICE == "cuda":
        pixel_values = pixel_values.to(DEVICE)

    # Токенизируем промпт
    text_input = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
    if DEVICE == "cuda":
        text_input = {k: v.to(DEVICE) for k, v in text_input.items()}

    # Формируем входные данные для модели (InternVL ожидает словарь)
    inputs = {
        "pixel_values": pixel_values,
        "input_ids": text_input["input_ids"],
        "attention_mask": text_input["attention_mask"],
    }

    # Генерация
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # детерминированный вывод
            temperature=0.0,
            pad_token_id=tokenizer.eos_token_id,  # чтобы избежать предупреждений
        )

    # Декодируем ответ (только новые токены, без промпта)
    generated_ids = outputs[0][len(text_input["input_ids"][0]):]  # отсекаем промпт
    response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return response_text


# ---------- Эндпоинт ----------

@app.post("/process", response_model=OCRResponse)
async def ocr_endpoint(
        file: UploadFile = File(...),
        max_tokens: int = Form(512),
):
    try:
        # 1. Читаем файл
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(400, "Файл пуст")
        file_type = detect_file_type(file.content_type or "", file.filename or "")
        logger.info(f"Обработка {file_type}")

        # 2. Приводим к PDF
        if file_type == "pdf":
            pdf_bytes = file_bytes
        elif file_type == "docx":
            pdf_bytes = convert_docx_to_pdf_bytes(file_bytes)
        elif file_type == "doc":
            pdf_bytes = doc_to_pdf_bytes(file_bytes)
        else:
            raise HTTPException(400, "Поддерживаются только PDF, DOC, DOCX")

        # 3. Разбиваем на страницы (изображения)
        page_images = pdf_bytes_to_images(pdf_bytes)
        if not page_images:
            raise HTTPException(400, "Не удалось извлечь страницы")

        # 4. Генерируем Markdown (один запрос со всеми страницами)
        prompt_md = (
            "Распознай текст на изображениях и верни его в формате Markdown. "
            "Сохрани структуру (заголовки, списки, таблицы), если они есть."
        )
        extracted_text = generate_response(page_images, prompt_md, max_tokens)

        # 5. Генерируем JSON
        prompt_json = """Распознай текст на изображении и извлеки следующие поля в формате JSON:
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
Ответ дай строго в виде JSON без пояснений."""
        json_str = generate_response(page_images, prompt_json, max_tokens)

        # 6. Парсим JSON
        try:
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"Некорректный JSON: {json_str[:200]}...")
            parsed_json = {}

        # 7. Хеш первой страницы
        p_hash = hashlib.sha256(page_images[0]).hexdigest()

        # 8. Ответ
        return OCRResponse(
            extracted_text=extracted_text,
            parsed_json=parsed_json,
            p_hash=p_hash,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка")
        raise HTTPException(500, f"Внутренняя ошибка: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)