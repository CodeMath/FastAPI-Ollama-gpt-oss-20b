import hmac
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi import Header
from fastapi.responses import JSONResponse
from openai import OpenAI
from PyPDF2 import PdfReader
from pydantic import BaseModel
from dotenv import load_dotenv


# ---------- 설정 ----------
# .env 로부터 환경변수 로드 (이미 설정된 OS env는 유지)
load_dotenv(override=False)
APP_API_KEY = os.getenv("APP_API_KEY")  # 반드시 설정할 것
API_KEY_HEADER_NAME = os.getenv("API_KEY_HEADER_NAME", "x-api-key")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")  # OpenAI 호환 클라에서 필수
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")


def create_ollama_client() -> OpenAI:
    return OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)


# ---------- 인증 ----------
async def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias=API_KEY_HEADER_NAME)):
    if not APP_API_KEY:
        raise HTTPException(status_code=500, detail="Server API key not configured")
    if x_api_key is None or not hmac.compare_digest(x_api_key, APP_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------- 스키마 ----------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.2


class ChatResponse(BaseModel):
    content: str
    model: str


app = FastAPI(title="OSS20B API", version="0.1.0")


@app.get("/health", dependencies=[Depends(verify_api_key)])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(request: ChatRequest) -> ChatResponse:
    client = create_ollama_client()
    model = request.model or DEFAULT_MODEL
    response = client.chat.completions.create(
        model=model,
        messages=[m.model_dump() for m in request.messages],
        temperature=request.temperature,
    )
    content = response.choices[0].message.content
    return ChatResponse(content=content, model=model)


@app.post("/analyze-pdf", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def analyze_pdf(
    file: UploadFile = File(...),
    model: Optional[str] = None,
    system_prompt: Optional[str] = "너는 대본을 분석하는 연출자야. 주인공의 감정선을 분석해줘.",
    temperature: Optional[float] = 0.2,
) -> ChatResponse:
    # PDF 텍스트 추출
    try:
        reader = PdfReader(file.file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {exc}")

    client = create_ollama_client()
    actual_model = model or DEFAULT_MODEL
    response = client.chat.completions.create(
        model=actual_model,
        messages=[
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": text},
        ],
        temperature=temperature,
    )
    content = response.choices[0].message.content
    return ChatResponse(content=content, model=actual_model)

