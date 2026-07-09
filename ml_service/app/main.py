import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from src.ocr_client import VLLMClient
from src.config import VLLM_URL, MODEL_NAME
from src.models import OCRResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Qianfan-OCR Service", version="1.0")

client = VLLMClient(base_url=VLLM_URL, model=MODEL_NAME)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/process", response_model=OCRResponse)
async def ocr_endpoint(
    file: UploadFile = File(...),
    prompt: str = Form("Извлеки следующие данные в JSON-формате:"),
    max_tokens: int = Form(512),
):

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        result = client.recognize(
            image_bytes=image_bytes,
            prompt=prompt,
            max_tokens=max_tokens,
        )
        return OCRResponse(text=result, model=MODEL_NAME)
    except Exception as e:
        logger.exception("Ошибка при обработке запроса")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)