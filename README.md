# 징검

내 다음 단계에서 열리는 제도를 미리 추천합니다. 원하면 부모님 것도 같이 봅니다.
코디세이 AI 해커톤 2026, 주제 ① AI 기반 추천 서비스.

- 데이터 형식(백엔드, AI, 프론트가 주고받는 모양): [docs/api.md](docs/api.md)
- 외부 자원(빠지면 실격): [docs/external-resources.md](docs/external-resources.md)
- AI 코딩 도구 공통 규칙: [AGENTS.md.example](AGENTS.md.example)

## 폴더

```
.
├── backend/      FastAPI (uv 프로젝트, Python 3.11)
├── frontend/     Next.js
├── rules/        조건 JSON (manual: 손 조건표, compiled: AI 추출)
├── data/         API 덤프(raw), 공고문 PDF(notices), 가상 인구(population, 커밋 안 함)
├── eval/         페르소나, 손 라벨, 채점
└── docs/
```

## 준비물

- Python 3.11, [uv](https://docs.astral.sh/uv/)
- Node.js 20 이상, npm

uv가 없으면 먼저 설치합니다(macOS).

```bash
brew install uv
```

## 클론한 뒤 설치

**레포 루트에서** 실행합니다.

```bash
cp .env.example .env
```

```bash
uv sync --project backend
```

```bash
cd frontend && npm install && cd ..
```

`.env`에 키를 채웁니다. 키는 커밋하지 않습니다.

| 변수 | 어디서 받나 |
|---|---|
| `NAITO_API_KEY`, `NAITO_BASE_URL`, `NAITO_MODEL` | 대회 지급 네이토 API |
| `DATA_GO_KR_KEY` | data.go.kr 마이페이지의 인증키. 쓰는 API마다 활용신청 |
| `YOUTHCENTER_API_KEY` | 온통청년 마이페이지 > OPEN API 신청(심의 뒤 발급) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | 이메일 알림 발송 계정 |
| `NEXT_PUBLIC_API_BASE` | 화면이 부를 API 주소. `frontend/.env.local`에 같은 이름으로 둔다 |

## 실행

명령은 전부 **레포 루트에서** 실행합니다. uv 프로젝트는 `backend/` 안에 있어서 `--project backend`를 붙입니다. 그래야 `backend.engine` 같은 모듈 경로가 잡힙니다.

API 서버 (http://localhost:8000, 문서는 /docs):

```bash
uv run --project backend uvicorn backend.app.main:app --reload --port 8000
```

화면 (http://localhost:3000):

```bash
cd frontend && npm run dev
```

공공데이터 덤프 (시연 중에는 API를 부르지 않는다):

```bash
uv run --project backend python -m backend.data.dump --source gov24
```

가상 인구와 비슷한 가구 표 만들기:

```bash
uv run --project backend python -m backend.population.build --n 10000 --holdout 1000 --seed 42
```

테스트:

```bash
uv run --project backend pytest -q
```

나머지 명령(공고 읽기 배치, 판정만, 채점)도 같은 방식으로 `uv run --project backend python -m backend.<모듈>`로 실행한다.

## 의존성 추가

같은 커밋에서 [docs/external-resources.md](docs/external-resources.md)에 한 줄 추가합니다. 안 하면 CI가 실패합니다.

```bash
uv add --project backend <패키지>
```

```bash
cd frontend && npm install <패키지> && cd ..
```

## 처음 한 번만 (레포를 새로 만들 때)

레포에 `backend/`와 `frontend/`가 이미 있으면 건너뜁니다.

프런트엔드는 **레포 루트에서** 만듭니다. `frontend` 폴더에 들어가서 실행하면 `frontend/frontend`가 생깁니다.

```bash
npx create-next-app@latest frontend --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm
```

```bash
cd frontend && npm install react-pdf && cd ..
```

백엔드는 `backend` 폴더를 만들고 그 안에서 uv 프로젝트를 초기화합니다. `--no-package`를 빼면 최신 uv는 `src/` 구조로 만들어 아래 실행 명령과 맞지 않습니다.

```bash
mkdir -p backend && cd backend && uv init --python 3.11 --no-package && cd ..
```

FastAPI와 개발 서버 등 표준 의존성, 그리고 우리가 쓰는 라이브러리를 설치합니다.

```bash
cd backend && uv add "fastapi[standard]" && cd ..
```

```bash
uv add --project backend httpx pdfplumber rank-bm25 scikit-learn numpy pandas pyarrow python-dotenv
```

```bash
uv add --project backend --dev pytest
```

모듈 경로가 잡히도록 패키지 표시 파일을 만듭니다. `uv init`이 만든 `backend/main.py`는 지웁니다.

```bash
touch backend/__init__.py && mkdir -p backend/app && touch backend/app/__init__.py && rm -f backend/main.py
```

마지막으로 [docs/external-resources.md](docs/external-resources.md)에 설치한 것을 적었는지 확인하고 첫 커밋을 합니다. 첫 커밋 시각은 외부 자원 표에 적습니다.
