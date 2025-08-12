## OSS20B FastAPI API (Ollama 기반)

FastAPI로 만든 OpenAI 호환 API 래퍼입니다. 로컬의 Ollama 서버에 연결하고, API 키 기반 인증으로 외부 접근을 제한합니다. `uv`로 패키지 관리를 하며 Docker로 배포할 수 있습니다.

### 주요 기능
- **API 키 인증**: `x-api-key` 헤더(기본)로 접근 제어
- **엔드포인트**:
  - `GET /health` 헬스 체크
  - `POST /chat` OpenAI 챗 컴플리션 프록시
  - `POST /analyze-pdf` 업로드한 PDF 텍스트를 분석 프롬프트와 함께 LLM에 전달
- **환경 변수 `.env` 지원** (`python-dotenv`)

---

## 사전 준비
- Python 3.12+
- Docker 및 Docker Compose
- Compose 사용 시 별도 Ollama 설치는 필요 없습니다. 외부 Ollama를 사용할 경우에만 호스트에 설치하세요.
- (참조) NVIDIA GeForce RTX3090를 사용하고 있습니다. (GPU 사용)
---

## 환경 변수 (.env)
프로젝트 루트에 `.env` 파일을 만들어 아래와 같이 설정하세요.

```
APP_API_KEY=your-secret-key
API_KEY_HEADER_NAME=x-api-key
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_API_KEY=ollama
OLLAMA_MODEL=gpt-oss:20b
```

설명:
- `APP_API_KEY` (필수): 서버가 비교 검증하는 고정 API 키
- `API_KEY_HEADER_NAME` (선택, 기본 `x-api-key`)
- `OLLAMA_BASE_URL`: OpenAI 호환 Ollama 엔드포인트
  - 로컬 직접 실행: `http://localhost:11434/v1`
  - Docker 컨테이너에서 호스트로 접속: `http://host.docker.internal:11434/v1`
  - Docker Compose 내부 Ollama 서비스 사용: `http://ollama:11434/v1`
- `OLLAMA_API_KEY`: OpenAI SDK가 요구하는 토큰 값(임의 문자열 OK, 기본 `ollama`)
- `OLLAMA_MODEL`: 기본 모델명 (예: `gpt-oss:20b`)

> 보안상 `.env`는 Git에 커밋하지 마세요.

---

## 로컬 실행 (Docker 미사용)

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

확인:
```bash
curl -H 'x-api-key: your-secret-key' http://localhost:8000/health
```

---

## Docker Compose로 실행 (권장)

1) 프로젝트 루트에 `.env` 준비 (예시)
```
APP_API_KEY=your-secret-key
API_KEY_HEADER_NAME=x-api-key
OLLAMA_API_KEY=ollama
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://ollama:11434/v1
```

2) `docker-compose.yml` (요약)
아래는 현재 저장소의 Compose 서비스 구성과 동일합니다.
```
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    # No host port mapping needed; API uses internal network
    expose:
      - "11434"
    gpus: all
    volumes:
      - C:\Users\jadec\.ollama:/root/.ollama
    restart: unless-stopped

  api:
    build: .
    container_name: oss20b-api
    environment:
      - APP_API_KEY=${APP_API_KEY}
      - API_KEY_HEADER_NAME=${API_KEY_HEADER_NAME:-x-api-key}
      - OLLAMA_BASE_URL=http://ollama:11434/v1
      - OLLAMA_API_KEY=${OLLAMA_API_KEY:-ollama}
      - OLLAMA_MODEL=${OLLAMA_MODEL:-gpt-oss:20b}
    depends_on:
      - ollama
    ports:
      - "8000:8000"
    restart: unless-stopped

```

3) 모델 준비(최초 1회)
컨테이너가 올라온 뒤 Ollama 컨테이너에서 모델을 받아옵니다.
```bash
docker compose up -d
docker exec -it ollama ollama pull gpt-oss:20b
```

4) 애플리케이션 확인
```bash
curl -H 'x-api-key: your-secret-key' http://localhost:8000/health
```

유용한 명령:
- 로그 보기: `docker compose logs -f --tail=200`
- 재빌드: `docker compose up -d --build`

참고:
- Windows에서 로컬 모델 재사용을 위해 `C:/Users/jadec/.ollama:/root/.ollama` 바인드 마운트를 사용합니다. (WSL에서 compose 실행 시 `/mnt/c/Users/jadec/.ollama:/root/.ollama`로 표기)
- API 컨테이너에는 프로젝트 루트의 `.env`가 `/app/.env`로 읽기 전용 마운트됩니다. Compose에서 별도로 환경 변수를 주입하지 않습니다.

### GPU 사용 (Docker Desktop / NVIDIA)
- Docker Desktop Settings → Resources → WSL integration에서 현재 WSL 배포본 통합 활성화
- Docker Desktop Settings → Resources → GPU support 활성화
- NVIDIA 드라이버 설치 및 WSL2용 GPU 지원 구성
- 테스트: `docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu nvidia-smi`

---

## Docker로 단독 실행

이미지 빌드:
```bash
docker build -t oss20b:latest .
```

### Mac/Windows (Docker Desktop)
```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  oss20b:latest
```

### Linux (호스트의 Ollama에 접근)
`host.docker.internal`을 게이트웨이에 매핑:
```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --add-host=host.docker.internal:host-gateway \
  oss20b:latest
```

대안으로 호스트 네트워크 사용(보안상 주의):
```bash
docker run --rm --network=host \
  --env-file .env \
  oss20b:latest
```

### WSL2
- Docker Desktop 백엔드라면 Mac/Windows와 동일하게 동작합니다.
- Ollama가 WSL2 내부에서만 접근 가능한 경우, API 컨테이너도 같은 네트워크 네임스페이스에서 실행하거나 `--network=host`를 사용하세요.

---

## API 사용법

### 인증
- 기본 헤더: `x-api-key: <APP_API_KEY>`
- 변경 시: `.env`의 `API_KEY_HEADER_NAME` 값으로 헤더 이름 수정

### 문서화 UI
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 엔드포인트

1) 헬스 체크
```bash
curl -H 'x-api-key: your-secret-key' http://localhost:8000/health
```

2) Chat Completions 프록시 (`POST /chat`)
Request (JSON):
```json
{
  "model": "gpt-oss:20b",
  "temperature": 0.2,
  "messages": [
    {"role": "system", "content": "너는 대본을 분석하는 연출자야."},
    {"role": "user", "content": "주인공 감정선 핵심만 요약해줘"}
  ]
}
```

curl 예시:
```bash
curl -X POST 'http://localhost:8000/chat' \
  -H 'content-type: application/json' \
  -H 'x-api-key: your-secret-key' \
  -d '{
    "model": "gpt-oss:20b",
    "temperature": 0.2,
    "messages": [
      {"role": "system", "content": "너는 대본을 분석하는 연출자야."},
      {"role": "user", "content": "주인공 감정선 핵심만 요약해줘"}
    ]
  }'
```

3) PDF 분석 (`POST /analyze-pdf`)
파일 업로드(FormData) + 쿼리 파라미터

4) 스트리밍 엔드포인트
- `POST /chat-stream`: chunked 텍스트(`text/plain`)로 응답 스트림
- `POST /analyze-pdf-stream`: 업로드한 PDF 분석 결과를 스트리밍으로 반환

```bash
curl -X POST 'http://localhost:8000/analyze-pdf?model=gpt-oss:20b' \
  -H 'x-api-key: your-secret-key' \
  -F 'file=@script.pdf'
```

---

## 트러블슈팅
- 컨테이너에서 호스트의 `localhost`는 통하지 않습니다. Mac/Windows는 `host.docker.internal`, Linux는 `--add-host=host.docker.internal:host-gateway`를 사용하세요.
- Ollama가 응답하지 않으면 포트(기본 `11434`)와 모델 준비 상태를 확인하세요.
- 401 Unauthorized가 나오면 `APP_API_KEY` 값과 헤더 이름(`API_KEY_HEADER_NAME`)을 확인하세요.

---

## 프로젝트 구조

```
oss20b/
├─ Dockerfile
├─ docker-compose.yml
├─ main.py
├─ pyproject.toml
├─ uv.lock
├─ README.md
└─ __pycache__/
```

- **Dockerfile**: FastAPI 앱 도커 이미지 정의
- **docker-compose.yml**: API + Ollama 서비스 오케스트레이션
- **main.py**: FastAPI 애플리케이션 엔트리포인트(엔드포인트 정의)
- **pyproject.toml**: `uv` 기반 Python 의존성/메타데이터
- **uv.lock**: 잠금 파일(재현 가능한 설치)
- **README.md**: 사용법 및 문서
- **__pycache__/**: Python 바이트코드 캐시(무시 가능)

---

## 개발 참고
- 의존성: `pyproject.toml` (`uv` 기반)
- 로컬 개발 서버: `uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000`

