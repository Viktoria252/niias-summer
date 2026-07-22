import sys
import os
import hashlib
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
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


MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
USE_OCR = os.getenv("USE_OCR", "true").lower() == "true"

if "/app" not in sys.path:
    sys.path.append("/app")

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    #КАСТОМНЫЙ НЕБУФЕРИЗИРОВАННЫЙ СТРИМЕР ДЛЯ ЖИВОГО ВЫВОДА СИМВОЛОВ
    class FlushStreamer(TextStreamer):
        def on_finalized_text(self, text: str, stream_end: bool = False):
            sys.stdout.write(text)
            sys.stdout.flush()


app = FastAPI(title="MiResult OCR Service (Real/Mock Enabled)", version="3.0")

MODEL_PATH = MODEL_NAME  # "baidu/Qianfan-OCR" или локальный путь
DEVICE = os.getenv("DEVICE", "auto").lower()

# Инициализация ИИ-модели СТРОГО в реальном режиме!
if not MOCK_MODE:
    # ---------- Загрузка OCR-модели (если USE_OCR=true) ----------
    if USE_OCR:
        DEVICE_OVERRIDE = os.getenv("DEVICE", "auto").lower()
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
        # Заглушки, чтобы не было ошибок в эндпоинтах при обращении
        model = None
        tokenizer = None
        image_processor = None

    # ---------- Загрузка текстовой модели Qwen ----------
    logger.info("Загрузка текстовой модели Qwen...")
    try:

        TEXT_MODEL_NAME = os.getenv("TEXT_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")

        # Определяем устройство для текстовой модели
        text_dev = os.getenv("TEXT_DEVICE", "auto").lower()
        if text_dev == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("TEXT_DEVICE=cuda but CUDA not available")
            TEXT_DEVICE = "cuda"
        elif text_dev == "cpu":
            TEXT_DEVICE = "cpu"
        else:
            TEXT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

        TEXT_MODEL = AutoModelForCausalLM.from_pretrained(
            TEXT_MODEL_NAME,
            device_map="auto" if TEXT_DEVICE == "cuda" else None,
            trust_remote_code=True,
        )

        if TEXT_DEVICE == "cpu":
            TEXT_MODEL = TEXT_MODEL.to("cpu")

        TEXT_TOKENIZER = AutoTokenizer.from_pretrained(TEXT_MODEL_NAME, trust_remote_code=True)
        if TEXT_TOKENIZER.pad_token is None:
            TEXT_TOKENIZER.pad_token = TEXT_TOKENIZER.eos_token

        logger.info(f"Текстовая модель {TEXT_MODEL_NAME} загружена на {TEXT_DEVICE}")
    except Exception as e:
        logger.error(f"Не удалось загрузить текстовую модель: {e}")
        raise
else:
    logger.info("Мок-режим: модели не загружаются")
def calculate_visual_phash(pil_image: Image.Image) -> str:
    """
    Быстрый чистый расчет перцептивного хэша (pHash) изображения на базе Pillow.
    """
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
    
    # Приводим пиксели к нативному для процессора float32
    pixel_values = image_processor(pil_images, return_tensors="pt").pixel_values

    if DEVICE == "cuda":
        pixel_values = pixel_values.to(dtype=torch.float16).to(DEVICE)
        logger.info(f"Шаг 3: Пиксели подготовлены для GPU. Форма тензора: {pixel_values.shape}")
    else:
        pixel_values = pixel_values.to(dtype=torch.float32).to(DEVICE)
        logger.info(f"Шаг 3: Пиксели подготовлены для CPU. Форма тензора: {pixel_values.shape}")
    pixel_values = pixel_values.to(dtype=torch.float32)

    # Токенизируем текст промпта на CPU
    text_input = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
    input_ids = text_input["input_ids"]
    attention_mask = text_input["attention_mask"]
    
    # Считываем точный ID токена картинки из конфига
    image_token_id = getattr(model.config, "image_token_id", 151671)
    
    # ДИНАМИЧЕСКИЙ РАСЧЕТ НЕОБХОДИМОГО КОЛИЧЕСТВА ТОКЕНОВ КАРТИНКИ
    num_image_tokens = pixel_values.shape[0] * 256
    logger.info(f"Шаг 5: Обнаружено {pixel_values.shape[0]} плиток изображения. Требуется ровно {num_image_tokens} токенов в input_ids.")

    existing_tokens_count = (input_ids == image_token_id).sum().item()
    
    if existing_tokens_count < num_image_tokens:
        needed_tokens = num_image_tokens - existing_tokens_count
        logger.info(f"Шаг 6: Вставляем {needed_tokens} токенов изображения в начало тензора...")
        
        # Создаем тензор токенов изображения на CPU
        image_token_tensor = torch.tensor([[image_token_id] * needed_tokens], dtype=torch.long)
        input_ids = torch.cat([image_token_tensor, input_ids], dim=1)
        
        # Создаем attention_mask на CPU
        ones_tensor = torch.ones((1, needed_tokens), dtype=torch.long)
        attention_mask = torch.cat([ones_tensor, attention_mask], dim=1)

    # Кастомный небуферизируемый стример
    from transformers import TextStreamer
    class FlushStreamer(TextStreamer):
        def on_finalized_text(self, text: str, stream_end: bool = False):
            sys.stdout.write(text)
            sys.stdout.flush()

    streamer = FlushStreamer(tokenizer, skip_prompt=True)

    inputs = {
        "pixel_values": pixel_values,
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    }

    # Запускаем генерацию
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
        file_bytes = file.file.read()
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

    #  РЕАЛЬНЫЙ РЕЖИМ НЕЙРОСЕТИ (Qianfan-OCR) на CPU 
    if MOCK_MODE:
        text_output = f"# Результаты анализа документа: {filename} (MOCK MODE)\n\n"
        
        if diagnostic_error:
            text_output += (
                f"❌ **ОШИБКА РАСЧЕТА РЕАЛЬНОГО ХЭША:**\n"
                f"```text\n{diagnostic_error}\n```\n\n"
                f"⚠️ *Используется дефолтный хэш-заглушка: `{real_p_hash}`*\n\n"
            )
        else:
            text_output += f"✅ **Реальный визуальный хэш успешно рассчитан:** `{real_p_hash}`\n\n"
            
        text_output += (
            "--- \n"
            "Комиссия в составе представителей железной дороги и сервисного депо провела расследование.\n\n"
            "**Установлено:** случай отказа локомотива ТЭМ18Д №1111 на перегоне Хижина-Магазин "
            "произошел из-за неисправности турбины ТК-30. Виновная организация — «ЛокоТех Сервис»."
        )

        return {
            "extracted_text": text_output,
            "parsed_json": {
                # Для Java DTO
                "failureLocation": "перегон Хижина-Магазин (MOCK)",
                "failureDate": "2026-07-15",
                "failureTime": "22:56",
                "locomotiveSeries": "ТЭМ18Д",
                "locomotiveSectionNumber": "№1111",
                "contract": "№999 от 01.01.2014",
                "failureReason": "неисправность турбины ТК-30 (посторонний шум при работе)",
                "failureType": "производственный",
                "locomotiveEquipment": "локомотив ТЭМ18Д №1111",
                "responsibleOrganization": "«ЛокоТех Сервис»",
                
                # Для фронтенда
                "Место отказа": "перегон Хижина-Магазин (MOCK)",
                "Дата": "2026-07-15",
                "Время начала отказа": "22:56",
                "Серия локомотива": "ТЭМ18Д",
                "Номер секции локомотива": "№1111",
                "Договор": "№999 от 01.01.2014",
                "Причина отказа": "неисправность турбины ТК-30 (посторонний шум при работе)",
                "Вид отказа": "производственный",
                "Оборудование локомотива": "локомотив ТЭМ18Д №1111",
                "Наименование виновной организации": "«ЛокоТех Сервис»"
            },
            "p_hash": real_p_hash
        }

    # ==================== РЕАЛЬНЫЙ РЕЖИМ НЕЙРОСЕТИ (Qianfan-OCR) на CPU ====================
    # 1. Извлекаем Markdown-текст
    prompt_md = (
        "Распознай текст на изображениях и верни его в формате Markdown. "
        "Сохрани структуру (заголовки, списки, таблицы), если они есть."
    )
    logger.info("Отправляем запрос в нейросеть для получения Markdown-текста...")
    extracted_text = generate_response(page_images, prompt_md, max_tokens)

    # 2. Извлекаем JSON-данные
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
    
    logger.info("Отправляем запрос в нейросеть для получения JSON-полей...")
    json_str = generate_response(page_images, prompt_json, max_tokens)
    
    # Парсим полученный от ИИ JSON
    try:
        clean_json_str = json_str.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()
        
        parsed_json = json.loads(clean_json_str)
    except Exception as e:
        logger.warning(f"Не удалось распарсить JSON нейросети ({json_str[:150]}): {e}")
        parsed_json = {}

    return {
        "extracted_text": extracted_text,
        "parsed_json": parsed_json,
        "p_hash": real_p_hash
    }

# Текстовая модель (новый подход)
# Глобальные переменные для текстовой модели
_text_model = None
_text_tokenizer = None
TEXT_DEVICE = None
TEXT_MODEL_NAME = os.getenv("TEXT_MODEL_NAME", "Qwen/Qwen2.5-Coder-7B-Instruct")


def get_text_model():
    global _text_model, _text_tokenizer, TEXT_DEVICE
    if _text_model is not None:
        return _text_model, _text_tokenizer

    # Определяем устройство
    TEXT_DEVICE = os.getenv("DEVICE", "auto").lower()
    if TEXT_DEVICE == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("TEXT_DEVICE=cuda but CUDA not available")
    else:
        TEXT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(f"Загрузка текстовой модели {TEXT_MODEL_NAME} на устройство {TEXT_DEVICE}")

    _text_model = AutoModelForCausalLM.from_pretrained(
        TEXT_MODEL_NAME,
        device_map="auto" if TEXT_DEVICE == "cuda" else None,
        trust_remote_code=True,
    )
    if TEXT_DEVICE == "cpu":
        _text_model = _text_model.to("cpu")

    _text_tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL_NAME, trust_remote_code=True)
    # Устанавливаем pad_token, если его нет
    if _text_tokenizer.pad_token is None:
        _text_tokenizer.pad_token = _text_tokenizer.eos_token

    logger.info("Текстовая модель успешно загружена!")
    return _text_model, _text_tokenizer


def extract_json_from_markdown(markdown_text: str, max_tokens: int = 512) -> dict:
    """
    Использует текстовую LLM для извлечения структурированных полей из Markdown-текста.
    Возвращает словарь с извлечёнными полями.
    """

    def extract_json_from_markdown(markdown_text: str, max_tokens: int = 512) -> dict:
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

        # Парсинг JSON
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
    if not USE_OCR:
        raise HTTPException(503, "OCR-модель отключена. Установите USE_OCR=true в окружении.")
    # Распечатываем всё, что прислал Spring Boot во внутреннюю сеть Docker
    headers = dict(request.headers)
    logger.info("=== ДИАГНОСТИКА ЗАПРОСА /ocr ===")
    logger.info(f"Заголовки запроса:\n{json.dumps(headers, indent=2)}")
    try:
        form = await request.form()
        logger.info(f"Все ключи в теле формы: {list(form.keys())}")
        for k, v in form.items():
            if isinstance(v, UploadFile):
                logger.info(f"  - Найдено поле файла '{k}': имя файла = '{v.filename}', Content-Type = '{v.content_type}'")
            else:
                logger.info(f"  - Найдено текстовое поле '{k}': размер = {len(str(v))} симв.")
    except Exception as e:
        logger.error(f"Не удалось прочитать входящую форму: {e}")
    logger.info("=================================")
    
    return run_file_processing(file, max_tokens)


@app.post("/process", response_model=OCRResponse)
async def process_endpoint(request: Request, file: Optional[UploadFile] = File(None), max_tokens: int = Form(default=512)):
    if not USE_OCR:
        raise HTTPException(503, "OCR-модель отключена. Установите USE_OCR=true в окружении.")
    headers = dict(request.headers)
    logger.info("=== ДИАГНОСТИКА ЗАПРОСА /process ===")
    logger.info(f"Заголовки запроса:\n{json.dumps(headers, indent=2)}")
    try:
        form = await request.form()
        logger.info(f"Все ключи в теле формы: {list(form.keys())}")
    except Exception as e:
        pass
    logger.info("====================================")
    
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
        pdf_bytes = (doc_to_pdf_bytes(file_bytes))
    elif file.filename.lower().endswith('.docx'):
        pdf_bytes = convert_docx_to_pdf_bytes(file_bytes)
    else:
        raise HTTPException(400, "Только PDF-файлы поддерживаются")

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

        # pHash вычисляем через pdf2image (как в других эндпоинтах)
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
    return {"status": "healthy", "mode": "real"}


if __name__ == "__main__":
    # Считываем порт из переменной окружения FASTAPI_PORT (по умолчанию 8001)
    port_env = int(os.getenv("FASTAPI_PORT", "8041"))
    uvicorn.run(app, host="0.0.0.0", port=port_env)