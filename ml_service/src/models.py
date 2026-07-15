from pydantic import BaseModel
from typing import Dict, Any, Optional

class OCRResponse(BaseModel):
    extracted_text: str                 # склеенный Markdown со всех страниц
    parsed_json: Dict[str, Any]         # итоговый структурированный JSON
    p_hash: str                         # хэш первой страницы (SHA‑256 hex)