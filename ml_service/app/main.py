import sys
import os
import hashlib
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware  # Импорт CORS-плагина
from pydantic import BaseModel
from src.config import MODEL_NAME
from src.models import OCRResponse
import uvicorn
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# Работа с документами и изображениями
from pdf2image import convert_from_bytes
from PIL import Image
import io
import fitz
import pymupdf4llm

import logging

# Настраиваем логирование с временными метками (формат аналогичен Spring Boot)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d INFO %(process)d --- [%(threadName)s] %(name)s : %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
USE_OCR = os.getenv("USE_OCR", "true").lower() == "true"

if "/app" not in sys.path:
    sys.path.append("/app")

# Глобальные переменные для моделей
model = None
tokenizer = None
image_processor = None

TEXT_MODEL = None
TEXT_TOKENIZER = None
TEXT_DEVICE = None
TEXT_MODEL_NAME = os.getenv("TEXT_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
DEVICE = os.getenv("DEVICE", "cpu").lower()

# Импорты PyTorch и Transformers (нужны только в реальном режиме)
if not MOCK_MODE:
    import torch
    from transformers import AutoTokenizer, AutoImageProcessor, AutoConfig, TextStreamer
    import torch.nn.functional as F

    try:
        from transformers.models.qianfan_ocr.modeling_qianfan_ocr import QianfanOCRForConditionalGeneration
        from transformers.models.qianfan_ocr.configuration_qianfan_ocr import QianfanOCRConfig
        logger.info("Архитектура qianfan_ocr успешно импортирована из пакета Transformers!")
    except Exception as e:
        logger.error(f"Не удалось импортировать классы архитектуры модели: {e}")
        raise

    # КАСТОМНЫЙ НЕБУФЕРИЗИРОВАННЫЙ СТРИМЕР ДЛЯ ЖИВОГО ВЫВОДА СИМВОЛОВ
    class FlushStreamer(TextStreamer):
        def on_finalized_text(self, text: str, stream_end: bool = False):
            sys.stdout.write(text)
            sys.stdout.flush()


app = FastAPI(title="MiResult OCR Service (Real/Mock Enabled)", version="3.0")

# РАЗРЕШАЕМ CORS ДЛЯ ПРЯМОГО ОБРАЩЕНИЯ С ФРОНТЕНДА:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешает запросы с любых хостов (включая localhost:80)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = MODEL_NAME  # "baidu/Qianfan-OCR" или локальный путь

# Инициализация ИИ-моделей СТРОГО в реальном режиме!
if not MOCK_MODE:
    # ---------- Загрузка OCR-модели (если USE_OCR=true) ----------
    if USE_OCR:
        DEVICE_OVERRIDE = os.getenv("DEVICE", "cpu").lower()
        if DEVICE_OVERRIDE == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but not available")
            DEVICE = "cuda"
            DTYPE = torch.float16
            DEVICE_MAP = "auto"
        elif DEVICE_OVERRIDE == "cpu":
            DEVICE = "cpu"
            DTYPE = torch.float32
            DEVICE_MAP = None
        else:
            DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
            DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
            DEVICE_MAP = "auto" if DEVICE == "cuda" else None

        logger.info(f"Загрузка OCR-модели на {DEVICE} с dtype {DTYPE}")
        model = QianfanOCRForConditionalGeneration.from_pretrained(
            MODEL_PATH,
            torch_dtype=DTYPE,
            device_map=DEVICE_MAP,
            low_cpu_mem_usage=True,
        )
        if DEVICE == "cpu":
            model = model.to(DEVICE)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        image_processor = AutoImageProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        logger.info("OCR-модель загружена")
    else:
        logger.info("OCR-модель отключена (USE_OCR=false)")

    # ---------- Загрузка текстовой модели Qwen ----------
    logger.info("Загрузка текстовой модели Qwen...")
    try:
        # Определяем устройство для текстовой модели
        text_dev = os.getenv("TEXT_DEVICE", "cpu").lower()
        if text_dev == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("TEXT_DEVICE=cuda but CUDA not available")
            TEXT_DEVICE = "cuda"
            TEXT_DTYPE = torch.float16
        else:
            TEXT_DEVICE = "cpu"
            TEXT_DTYPE = torch.float32  # СТРОГО float32 для процессора, чтобы избежать медленной эмуляции bfloat16

        # Оптимизация потоков для CPU: ограничиваем до 4 физических ядер, чтобы избежать взаимной блокировки процессора
        if TEXT_DEVICE == "cpu":
            torch.set_num_threads(4)
            logger.info("Установлено ограничение PyTorch: 4 потока для CPU-вычислений.")

        TEXT_MODEL = AutoModelForCausalLM.from_pretrained(
            TEXT_MODEL_NAME,
            torch_dtype=TEXT_DTYPE,
            device_map="auto" if TEXT_DEVICE == "cuda" else None,
            trust_remote_code=True,
        )

        if TEXT_DEVICE == "cpu":
            TEXT_MODEL = TEXT_MODEL.to("cpu")

        TEXT_TOKENIZER = AutoTokenizer.from_pretrained(TEXT_MODEL_NAME, trust_remote_code=True)
        if TEXT_TOKENIZER.pad_token is None:
            TEXT_TOKENIZER.pad_token = TEXT_TOKENIZER.eos_token

        logger.info(f"Текстовая модель {TEXT_MODEL_NAME} загружена на {TEXT_DEVICE} в формате {TEXT_DTYPE}")
    except Exception as e:
        logger.error(f"Не удалось загрузить текстовую модель: {e}")
        raise
else:
    logger.info("=== ЗАПУЩЕН ДИАГНОСТИЧЕСКИЙ MOCK-РЕЖИМ ===")


def calculate_visual_phash(pil_image: Image.Image) -> str:
    img = pil_image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / 64
    bits = "".join(["1" if p > avg else "0" for p in pixels])
    return f"{int(bits, 2):016x}"


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
        pdf_path = Path(tmpdir) / "input.pdf" 
        docx_path.write_bytes(docx_bytes)
        
        cmd = [
            "libreoffice", 
            "--headless", 
            "-env:UserInstallation=file:///tmp/LibreOffice_Conversion_Profile",
            "--convert-to", "pdf", 
            "--outdir", str(pdf_path.parent), 
            str(docx_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return pdf_path.read_bytes()


def doc_to_pdf_bytes(doc_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "input.doc"
        pdf_path = Path(tmpdir) / "input.pdf" 
        doc_bytes_path = Path(tmpdir) / "input.doc"
        doc_bytes_path.write_bytes(doc_bytes)
        
        cmd = [
            "libreoffice", 
            "--headless", 
            "-env:UserInstallation=file:///tmp/LibreOffice_Conversion_Profile",
            "--convert-to", "pdf", 
            "--outdir", str(pdf_path.parent), 
            str(doc_bytes_path)
        ]
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
    pil_images = [Image.open(io.BytesIO(img)) for img in images]
    pixel_values = image_processor(pil_images, return_tensors="pt").pixel_values

    if DEVICE == "cuda":
        pixel_values = pixel_values.to(dtype=torch.float16).to(DEVICE)
        logger.info(f"Шаг 3: Пиксели подготовлены для GPU. Форма тензора: {pixel_values.shape}")
    else:
        pixel_values = pixel_values.to(dtype=torch.float32).to(DEVICE)
        logger.info(f"Шаг 3: Пиксели подготовлены для CPU. Форма тензора: {pixel_values.shape}")

    text_input = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
    input_ids = text_input["input_ids"]
    attention_mask = text_input["attention_mask"]
    
    image_token_id = getattr(model.config, "image_token_id", 151671)
    num_image_tokens = pixel_values.shape[0] * 256
    logger.info(f"Шаг 5: Обнаружено {pixel_values.shape[0]} плиток изображения. Требуется ровно {num_image_tokens} токенов в input_ids.")

    existing_tokens_count = (input_ids == image_token_id).sum().item()
    
    if existing_tokens_count < num_image_tokens:
        needed_tokens = num_image_tokens - existing_tokens_count
        logger.info(f"Шаг 6: Вставляем {needed_tokens} токенов изображения в начало тензора...")
        
        image_token_tensor = torch.tensor([[image_token_id] * needed_tokens], dtype=torch.long)
        input_ids = torch.cat([image_token_tensor, input_ids], dim=1)
        
        ones_tensor = torch.ones((1, needed_tokens), dtype=torch.long)
        attention_mask = torch.cat([ones_tensor, attention_mask], dim=1)

    streamer = FlushStreamer(tokenizer, skip_prompt=True)

    inputs = {
        "pixel_values": pixel_values.to(DEVICE),
        "input_ids": input_ids.to(DEVICE),
        "attention_mask": attention_mask.to(DEVICE),
    }

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=0.0,
            pad_token_id=tokenizer.eos_token_id,
            streamer=streamer  
        )

    generated_ids = outputs[0][len(input_ids[0]):]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)


# ---------- Общая логика обработки ----------

def run_file_processing(file: Optional[UploadFile], max_tokens: int) -> dict:
    filename = file.filename if file else "Пример протокола.docx"
    real_p_hash = "8f3c3c3c1c1c1c1c"
    diagnostic_error = None

    try:
        file_bytes = file.file.read() if file else b""
        if not file_bytes:
            raise ValueError("Полученный файл пуст (0 байт)")
            
        file_type = detect_file_type(file.content_type or "", file.filename or "")

        if file_type == "pdf":
            pdf_bytes = file_bytes
        elif file_type == "docx":
            pdf_bytes = convert_docx_to_pdf_bytes(file_bytes)
        elif file_type == "doc":
            pdf_bytes = doc_to_pdf_bytes(file_bytes)
        else:
            raise ValueError(f"Неподдерживаемый тип файла: {file_type}")

        if pdf_bytes:
            page_images = pdf_bytes_to_images(pdf_bytes)
            if page_images:
                first_page_pil = Image.open(io.BytesIO(page_images[0]))
                real_p_hash = calculate_visual_phash(first_page_pil)
                logger.info(f"Успешно рассчитан реальный pHash для {filename}: {real_p_hash}")
            else:
                raise ValueError("Не удалось нарезать PDF-файл на изображения страниц")
        else:
            raise ValueError("Не удалось сконвертировать документ в PDF")
            
    except Exception as e:
        import traceback
        diagnostic_error = traceback.format_exc()
        logger.error(f"Ошибка при расчете реального хэша для {filename}: {diagnostic_error}")
        raise HTTPException(500, f"Ошибка обработки файла: {e}")

    if MOCK_MODE:
        text_output = f"# Результаты анализа документа: {filename} (MOCK MODE)\n\n"
        if diagnostic_error:
            text_output += f"❌ **ОШИБКА РАСЧЕТА РЕАЛЬНОГО ХЭША:**\n```text\n{diagnostic_error}\n```\n\n"
        else:
            text_output += f"✅ **Реальный визуальный хэш успешно рассчитан:** `{real_p_hash}`\n\n"
            
        text_output += "Комиссия установила: случай отказа локомотива ТЭМ18Д №1111..."
        return {
            "extracted_text": text_output,
            "parsed_json": {
                "failureLocation": "перегон Хижина-Магазин (MOCK)",
                "failureDate": "2026-07-15",
                "failureTime": "22:56",
                "locomotiveSeries": "ТЭМ18Д",
                "locomotiveSectionNumber": "№1111",
                "contract": "№999 от 01.01.2014",
                "failureReason": "неисправность турбины (MOCK)",
                "failureType": "производственный",
                "locomotiveEquipment": "локомотив ТЭМ18Д №1111",
                "responsibleOrganization": "«ЛокоТех Сервис»"
            },
            "p_hash": real_p_hash
        }

    # ==================== РЕАЛЬНЫЙ РЕЖИМ РАБОТЫ ИИ ====================

    # Умный Фолбэк: если OCR отключен, перехватываем файлы и парсим их через быстрый PyMuPDF
    if not USE_OCR:
        logger.info("USE_OCR=false. Автоматически перенаправляем запрос на быстрый парсинг PyMuPDF + Qwen...")
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            md_text = pymupdf4llm.to_markdown(doc)
            if not md_text:
                raise ValueError("Не удалось программно извлечь текст из PDF")

            # Отправляем полученный Markdown-текст в модель Qwen
            parsed_json = extract_json_from_markdown(md_text, max_tokens)
            return {
                "extracted_text": md_text,
                "parsed_json": parsed_json,
                "p_hash": real_p_hash
            }
        except Exception as e:
            logger.error(f"Ошибка умного фолбэка без OCR: {e}")
            raise HTTPException(500, f"Ошибка фолбэк-обработки: {str(e)}")

    # Если OCR включен (Тяжелый визуальный ИИ)
    prompt_md = "Распознай текст на изображениях и верни его в формате Markdown."
    extracted_text = generate_response(page_images, prompt_md, max_tokens)

    prompt_json = "Распознай текст на изображении и извлеки поля в формате JSON..."
    json_str = generate_response(page_images, prompt_json, max_tokens)
    
    try:
        clean_json_str = json_str.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        parsed_json = json.loads(clean_json_str.strip())
    except Exception as e:
        logger.warning(f"Не удалось распарсить JSON: {e}")
        parsed_json = {}

    return {
        "extracted_text": extracted_text,
        "parsed_json": parsed_json,
        "p_hash": real_p_hash
    }


def extract_json_from_markdown(markdown_text: str, max_tokens: int = 512) -> dict:
    """
    Использует текстовую LLM Qwen для извлечения структурированных полей из Markdown-текста.
    """
    if MOCK_MODE:
        return {
            "failureLocation": "перегон Хижина-Магазин (MOCK-TEXT)",
            "failureDate": "2026-07-15",
            "failureTime": "22:56",
            "locomotiveSeries": "ТЭМ18Д",
            "locomotiveSectionNumber": "№1111",
            "contract": "№999 от 01.01.2014",
            "failureReason": "неисправность турбины (MOCK-TEXT)",
            "failureType": "производственный",
            "locomotiveEquipment": "локомотив ТЭМ18Д №1111",
            "responsibleOrganization": "«ЛокоТех Сервис»"
        }

    if TEXT_MODEL is None or TEXT_TOKENIZER is None:
        raise RuntimeError("Текстовая модель не загружена")

    messages = [
        {"role": "system", "content": "Ты — ассистент, который извлекает структурированные данные из текста."},
        {"role": "user", "content": f"""
Извлеки из следующего текста поля в формате JSON:
- Место отказа (дорога, станция, перегон, км, пикеты)
- Дата (год-месяц-день)
- Время начала отказа (часы-минуты)
- Серия локомотива
- Номер секции локомотива
- Договор (номер и наименование)
- Причина отказа
- Вид отказа (производственный, деградационный и т.п.)
- Оборудование локомотива
- Наименование виновной организации

Если поле отсутствует, используй null. Ответ дай строго в виде JSON без пояснений.

Текст:
{markdown_text}
"""}
    ]

    prompt = TEXT_TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = TEXT_TOKENIZER(prompt, return_tensors="pt", truncation=True, max_length=4096)
    if TEXT_DEVICE == "cuda":
        inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = TEXT_MODEL.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            temperature=0.0,
            pad_token_id=TEXT_TOKENIZER.pad_token_id,
        )

    generated = TEXT_TOKENIZER.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    try:
        start = generated.find('{')
        end = generated.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(generated[start:end])
        else:
            logger.warning("Не удалось найти JSON в ответе модели")
            return {"raw_output": generated}
    except Exception as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return {"error": "Ошибка парсинга JSON", "raw_output": generated}


# ---------- Эндпоинты ----------

@app.post("/ocr", response_model=OCRResponse)
async def ocr_endpoint(request: Request, file: Optional[UploadFile] = File(None), max_tokens: int = Form(default=512)):
    # Блокировка 503 убрана. Эндпоинт автоматически выберет быстрый PyMuPDF-режим, если USE_OCR=false
    return run_file_processing(file, max_tokens)


@app.post("/process", response_model=OCRResponse)
async def process_endpoint(request: Request, file: Optional[UploadFile] = File(None), max_tokens: int = Form(default=512)):
    # Блокировка 503 убрана. Эндпоинт автоматически выберет быстрый PyMuPDF-режим, если USE_OCR=false
    return run_file_processing(file, max_tokens)


@app.post("/extract_from_markdown", response_model=OCRResponse)
async def extract_from_markdown_endpoint(
    request: Request,
    file: UploadFile = File(...),
    max_tokens: int = Form(default=512)
):
    file_bytes = await file.read()
    if file.filename.lower().endswith('.pdf'):
        pdf_bytes = file_bytes
    elif file.filename.lower().endswith('.doc'):
        pdf_bytes = doc_to_pdf_bytes(file_bytes)
    elif file.filename.lower().endswith('.docx'):
        pdf_bytes = convert_docx_to_pdf_bytes(file_bytes)
    else:
        raise HTTPException(400, "Только PDF/DOC/DOCX файлы поддерживаются")

    if not pdf_bytes:
        raise HTTPException(400, "Файл пуст")

    try:
        # Открываем PDF из байтов
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        md_text = pymupdf4llm.to_markdown(doc)
        if not md_text:
            raise HTTPException(400, "Не удалось извлечь текст из PDF")

        parsed_json = extract_json_from_markdown(md_text, max_tokens)
        extracted_text = md_text

        images = convert_from_bytes(pdf_bytes, dpi=200, first_page=1, last_page=1)
        real_p_hash = calculate_visual_phash(images[0]) if images else "0000000000000000"

        return {
            "extracted_text": extracted_text,
            "parsed_json": parsed_json,
            "p_hash": real_p_hash
        }
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
        raise HTTPException(500, f"Ошибка: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "real" if not MOCK_MODE else "mock"}


if __name__ == "__main__":
    port_env = int(os.getenv("FASTAPI_PORT", "8041"))
    uvicorn.run(app, host="0.0.0.0", port=port_env)