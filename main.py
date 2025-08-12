import hmac
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi import Header
from fastapi.responses import JSONResponse, StreamingResponse
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


def generate_chat_response(messages: List[dict], model: str, temperature: Optional[float]) -> str:
    """Single-shot chat completion; returns content string."""
    client = create_ollama_client()
    # Prefer Responses API (OpenAI Quickstart). Fallback to Chat Completions if unsupported.
    try:  # Try unified Responses API
        response = client.responses.create(
            model=model,
            input=messages,
            temperature=temperature,
        )
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text
    except Exception:  # noqa: BLE001
        pass

    # Fallback: OpenAI-compatible Chat Completions
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content  # type: ignore[return-value]


def stream_chat_chunks(messages: List[dict], model: str, temperature: Optional[float]):
    """Yield content chunks as they arrive."""
    client = create_ollama_client()

    # Prefer Responses streaming (OpenAI Quickstart). If unsupported, fallback to Chat Completions streaming.
    try:
        with client.responses.stream(
            model=model,
            input=messages,
            temperature=temperature,
        ) as stream:
            for event in stream:
                # Stream only text deltas for simplicity
                if getattr(event, "type", None) == "response.output_text.delta":
                    delta_text = getattr(event, "delta", None)
                    if delta_text:
                        yield delta_text
            return
    except Exception:  # noqa: BLE001
        pass

    # Fallback to Chat Completions streaming
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                yield delta.content
        except Exception:  # noqa: BLE001
            continue


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
    model = request.model or DEFAULT_MODEL
    messages = [m.model_dump() for m in request.messages]
    content = generate_chat_response(messages=messages, model=model, temperature=request.temperature)
    return ChatResponse(content=content, model=model)


@app.post("/chat-stream", dependencies=[Depends(verify_api_key)])
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    model = request.model or DEFAULT_MODEL
    messages = [m.model_dump() for m in request.messages]

    def generate():
        for piece in stream_chat_chunks(messages=messages, model=model, temperature=request.temperature):
            yield piece

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


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

    actual_model = model or DEFAULT_MODEL
    messages = [
        {"role": "system", "content": system_prompt or ""},
        {"role": "user", "content": text},
    ]
    content = generate_chat_response(messages=messages, model=actual_model, temperature=temperature)
    return ChatResponse(content=content, model=actual_model)


@app.post("/analyze-pdf-stream", dependencies=[Depends(verify_api_key)])
async def analyze_pdf_stream(
    file: UploadFile = File(...),
    model: Optional[str] = None,
    system_prompt: Optional[str] = "너는 대본을 분석하는 연출자야. 주인공의 감정선을 분석해줘.",
    temperature: Optional[float] = 0.2,
) -> StreamingResponse:
    try:
        reader = PdfReader(file.file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {exc}")

    actual_model = model or DEFAULT_MODEL

    def generate():
        messages = [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": text},
        ]
        for piece in stream_chat_chunks(messages=messages, model=actual_model, temperature=temperature):
            yield piece

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

