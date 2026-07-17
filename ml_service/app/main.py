import logging
import json
import tempfile
import traceback
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request  # Request добавлен сюда!
from src.config import MODEL_NAME
from src.models import OCRResponse
import uvicorn

# Работа с документами и изображениями
from pdf2image import convert_from_bytes
from PIL import Image
import io

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Читаем переключатель режима из переменной окружения
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

# Импорты PyTorch и Transformers (нужны только в реальном режиме)
if not MOCK_MODE:
    import torch
    from transformers import AutoModel, AutoTokenizer, AutoImageProcessor, AutoConfig
    import torch.nn.functional as F

    # ХАК-ПАТЧ ДЛЯ DTENSOR
    try:
        import torch.distributed.tensor
    except ImportError:
        import types
        sys.modules['torch.distributed.tensor'] = types.ModuleType('torch.distributed.tensor')

    try:
        from torch.distributed.tensor import DTensor
    except ImportError:
        try:
            from torch.distributed._tensor import DTensor
            import torch.distributed.tensor as dt_tensor
            dt_tensor.DTensor = DTensor
            sys.modules['torch.distributed.tensor'] = dt_tensor
            logger.info("Успешно применен хак-патч для оригинального DTensor.")
        except Exception:
            import torch.distributed.tensor as dt_tensor
            class DummyDTensor:
                pass
            dt_tensor.DummyDTensor = DummyDTensor
            sys.modules['torch.distributed.tensor'] = dt_tensor
            logger.warning("DTensor отсутствует в CPU-сборке PyTorch. Создана заглушка.")

    # РЕГИСТРАЦИЯ АРХИТЕКТУРЫ МОДЕЛИ
    try:
        from configuration_qianfan_ocr import QianfanOCRConfig
        from modeling_qianfan_ocr import QianfanOCRForConditionalGeneration

        AutoConfig.register("qianfan_ocr", QianfanOCRConfig)
        AutoModel.register(QianfanOCRConfig, QianfanOCRForConditionalGeneration)
        logger.info("Архитектура qianfan_ocr успешно зарегистрирована в AutoModel!")
    except Exception as e:
        logger.error(f"Не удалось зарегистрировать архитектуру qianfan_ocr: {e}")


app = FastAPI(title="MiResult OCR Service (Robust Mock Enabled)", version="3.0")

MODEL_PATH = MODEL_NAME  # "baidu/Qianfan-OCR" или локальный путь

# Инициализация ИИ-модели (только в реальном режиме)
if not MOCK_MODE:
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Используем устройство: {DEVICE}")
    try:
        model = AutoModel.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
            trust_remote_code=True,
            device_map="auto" if DEVICE == "cuda" else None,
            low_cpu_mem_usage=True
        )
        if DEVICE == "cpu":
            model = model.to(DEVICE)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        image_processor = AutoImageProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        logger.info("Реальная ИИ-модель успешно загружена!")
    except Exception as e:
        logger.error(f"Не удалось загрузить реальную модель: {e}")
        raise
else:
    logger.info("ЗАПУЩЕН ДИАГНОСТИЧЕСКИЙ MOCK-РЕЖИМ")


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
        doc_path.write_bytes(doc_bytes)

        cmd = [
            "libreoffice",
            "--headless",
            "-env:UserInstallation=file:///tmp/LibreOffice_Conversion_Profile",
            "--convert-to", "pdf",
            "--outdir", str(pdf_path.parent),
            str(doc_path)
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
        pixel_values = pixel_values.to(DEVICE)

    text_input = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
    if DEVICE == "cuda":
        text_input = {k: v.to(DEVICE) for k, v in text_input.items()}

    inputs = {
        "pixel_values": pixel_values,
        "input_ids": text_input["input_ids"],
        "attention_mask": text_input["attention_mask"],
    }

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=0.0,
            pad_token_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else tokenizer.pad_token_id,
        )

    generated_ids = outputs[0][len(text_input["input_ids"][0]):]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)


# Общая логика обработки

def run_file_processing(file: Optional[UploadFile], max_tokens: int) -> dict:
    filename = file.filename if file else "Пример протокола.docx"
    real_p_hash = "8f3c3c3c1c1c1c1c" # Дефолтный хэш на случай сбоев
    diagnostic_error = None
    page_images = None

    # Если файл передан, пробуем выполнить реальную конвертацию и хэширование
    if file is not None:
        logger.info(f"Файл успешно получен в FastAPI: {filename}, тип: {file.content_type}")
        try:
            file_bytes = file.file.read()
            if not file_bytes:
                raise ValueError("Полученный файл пуст (0 байт)")

            file_type = detect_file_type(file.content_type or "", file.filename or "")
            logger.info(f"Определен тип файла: {file_type}")

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
            diagnostic_error = traceback.format_exc()
            logger.error(f"Ошибка при расчете реального хэша для {filename}: {diagnostic_error}")
    else:
        logger.warning("Предупреждение: FastAPI получил NULL (None) вместо файла!")
        diagnostic_error = "Файл не был получен сервером (file is None). Бэкенд Spring Boot передал пустой multipart-запрос."

    # Формирование ответа
    if MOCK_MODE:
        text_output = f"# Результаты анализа документа: {filename} (MOCK MODE)\n\n"

        if diagnostic_error:
            text_output += (
                f"ОШИБКА РАСЧЕТА РЕАЛЬНОГО ХЭША:\n"
                f"```text\n{diagnostic_error}\n```\n\n"
                f"Используется дефолтный хэш-заглушка: `{real_p_hash}`\n\n"
            )
        else:
            text_output += f"Реальный визуальный хэш успешно рассчитан: `{real_p_hash}`\n\n"

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
    else:
        # РЕАЛЬНЫЙ РЕЖИМ
        if not page_images or len(page_images) == 0:
            raise HTTPException(400, "Файл обязателен для реального режима ИИ")
        prompt = """Распознай текст на изображении и извлеки текст и следующие поля в формате JSON:
- Извлеченный текст
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

        try:
            # Вызываем модель
            raw_output = generate_response(page_images, prompt, max_tokens)
            # Извлекаем JSON из ответа (ищем { ... })
            start = raw_output.find('{')
            end = raw_output.rfind('}') + 1
            if start != -1 and end > start:
                json_str = raw_output[start:end]
                full_parsed = json.loads(json_str)  # весь JSON

                # Извлекаем поле "Извлеченный текст"
                extracted_text = full_parsed.pop("Извлеченный текст", "")

                # Остальные поля становятся parsed_json
                parsed_json = full_parsed  # без "Извлеченный текст"

            else:
                # JSON не найден – сохраняем сырой вывод как текст, а в parsed_json – ошибку
                extracted_text = raw_output
                parsed_json = {"error": "Модель не вернула JSON", "raw_output": raw_output}
                logger.warning("Не удалось найти JSON в ответе модели")
        except json.JSONDecodeError as e:
            logger.error(f"Модель вернула невалидный JSON: {raw_output}")
            extracted_text = raw_output
            parsed_json = {"error": "Не удалось распарсить JSON", "raw_output": raw_output}
        except Exception as e:
            logger.error(f"Ошибка при генерации: {e}")
            raise HTTPException(500, f"Ошибка модели: {str(e)}")

        return {
            "extracted_text": extracted_text,
            "parsed_json": parsed_json,
            "p_hash": real_p_hash
        }


# Эндпоинты (С параметром file: Optional)

@app.post("/ocr", response_model=OCRResponse)
async def ocr_endpoint(request: Request, file: Optional[UploadFile] = File(None), max_tokens: int = Form(default=512)):
    # Распечатываем всё, что прислал Spring Boot во внутреннюю сеть Docker
    headers = dict(request.headers)
    logger.info("ДИАГНОСТИКА ЗАПРОСА /ocr")
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
    headers = dict(request.headers)
    logger.info("ДИАГНОСТИКА ЗАПРОСА /process")
    logger.info(f"Заголовки запроса:\n{json.dumps(headers, indent=2)}")
    try:
        form = await request.form()
        logger.info(f"Все ключи в теле формы: {list(form.keys())}")
    except Exception as e:
        pass
    logger.info("====================================")

    return run_file_processing(file, max_tokens)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "smart_mock" if MOCK_MODE else "real"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)