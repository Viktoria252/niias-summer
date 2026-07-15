import logging
import hashlib
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.exceptions import RequestValidationError
from src.ocr_client import VLLMClient
from src.config import VLLM_URL, MODEL_NAME
from src.models import OCRResponse
import uvicorn

# Для работы с PDF и изображениями
from pdf2image import convert_from_bytes
from PIL import Image
import io
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MiResult OCR Service", version="2.0")

client = VLLMClient(base_url=VLLM_URL, model=MODEL_NAME)

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
    """
    Конвертирует DOCX в PDF с помощью LibreOffice (требуется установленный libreoffice).
    Возвращает байты PDF-файла.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "input.docx"
        pdf_path = Path(tmpdir) / "output.pdf"
        docx_path.write_bytes(docx_bytes)
        # Вызов libreoffice headless
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(pdf_path.parent),
            str(docx_path)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            pdf_bytes = pdf_path.read_bytes()
            return pdf_bytes
        except subprocess.CalledProcessError as e:
            logger.error(f"LibreOffice conversion failed: {e.stderr.decode()}")
            raise HTTPException(500, "Не удалось конвертировать DOCX в PDF")

def doc_to_pdf_bytes(doc_bytes: bytes) -> bytes:
    """
    Конвертирует старый .doc в PDF через LibreOffice (аналогично).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "input.doc"
        pdf_path = Path(tmpdir) / "output.pdf"
        doc_path.write_bytes(doc_bytes)
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(pdf_path.parent),
            str(doc_path)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            pdf_bytes = pdf_path.read_bytes()
            return pdf_bytes
        except subprocess.CalledProcessError as e:
            logger.error(f"LibreOffice conversion failed: {e.stderr.decode()}")
            raise HTTPException(500, "Не удалось конвертировать DOC в PDF")

def pdf_bytes_to_images(pdf_bytes: bytes) -> List[bytes]:
    """
    Разбивает PDF на страницы и возвращает список байтов каждого изображения (PNG).
    """
    try:
        images = convert_from_bytes(pdf_bytes, dpi=200, fmt='png')
    except Exception as e:
        logger.error(f"PDF to image conversion failed: {e}")
        raise HTTPException(500, "Не удалось конвертировать PDF в изображения")
    image_bytes_list = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        image_bytes_list.append(buf.getvalue())
    return image_bytes_list

def merge_json_responses(json_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Объединяет JSON-объекты со всех страниц.
    Стратегия: берём поля с первой страницы, на остальных добавляем только те ключи,
    которых ещё нет, или если значение является списком – объединяем списки.
    В нашем случае все поля строковые, поэтому просто дополняем недостающими ключами.
    """
    if not json_list:
        return {}
    merged = json_list[0].copy()
    for other in json_list[1:]:
        for key, value in other.items():
            if key not in merged:
                merged[key] = value
            else:
                # если оба значения списки – объединяем
                if isinstance(merged[key], list) and isinstance(value, list):
                    merged[key].extend(value)
                # иначе оставляем как есть (первое значение)
    return merged

@app.post("/process", response_model=OCRResponse)
async def ocr_endpoint(
    file: UploadFile = File(...),
    max_tokens: int = Form(512),
):
    try:
        # 1. Читаем байты файла
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(400, "Файл пуст")

        # 2. Определяем тип
        file_type = detect_file_type(file.content_type or "", file.filename or "")
        logger.info(f"Обработка файла типа: {file_type}")

        # 3. Приводим к PDF-байтам
        if file_type == "pdf":
            pdf_bytes = file_bytes
        elif file_type == "docx":
            pdf_bytes = convert_docx_to_pdf_bytes(file_bytes)
        elif file_type == "doc":
            pdf_bytes = doc_to_pdf_bytes(file_bytes)
        else:
            raise HTTPException(400, "Неподдерживаемый формат файла. Ожидается PDF, DOC или DOCX.")

        # 4. Разбиваем PDF на страницы (изображения)
        page_images = pdf_bytes_to_images(pdf_bytes)
        if not page_images:
            raise HTTPException(400, "Не удалось извлечь страницы из документа")

        # 5. Отправляем все страницы одновременно в модель для получения Markdown и JSON
        try:
            extracted_text = await client.recognize_markdown(page_images, max_tokens)
            json_str = await client.recognize_json(page_images, max_tokens)
        except Exception as e:
            logger.error(f"Ошибка при вызове модели: {e}")
            raise HTTPException(500, f"Ошибка при обработке документа моделью: {str(e)}")

        # 6. Парсим JSON-строку
        try:
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Невалидный JSON от модели: {json_str[:500]}...")
            parsed_json = {"error": "Модель вернула невалидный JSON", "raw": json_str}

        # 7. Вычисляем p_hash для первой страницы (SHA-256)
        p_hash = hashlib.sha256(page_images[0]).hexdigest()

        # 8. Формируем ответ
        return OCRResponse(
            extracted_text=extracted_text,
            parsed_json=parsed_json,
            p_hash=p_hash,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Неожиданная ошибка")
        raise HTTPException(500, f"Внутренняя ошибка сервера: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)