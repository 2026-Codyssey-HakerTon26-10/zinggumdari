# 징검

생애주기에 맞춰, 다음 단계에서 열리는 제도를 그 단계가 오기 전에 먼저 보여줍니다. 그 전에 해둘 일과 공고문 원문의 근거까지 보여주고, 원하면 부모님 것도 같이 봅니다.
코디세이 AI 해커톤 2026, 주제 ① AI 기반 추천 서비스.

- 왜 만드는가(문제, 근거, 결정과 이유): [Background.md](Background.md)
- 무엇을 만드는가(기능별 동작과 확인 기준): [SPEC.md](SPEC.md)
- 데이터 형식(백엔드, AI, 프론트가 주고받는 모양): [docs/api.md](docs/api.md)
- 외부 자원(빠지면 실격): [docs/external-resources.md](docs/external-resources.md)
- AI 코딩 도구 공통 규칙: [AGENTS.md.example](AGENTS.md.example)
- 역할 분담(누가 어느 폴더를 맡나): [docs/roles.md](docs/roles.md)

## 폴더

```
.
├── backend/      FastAPI (uv 프로젝트, Python 3.11)
├── frontend/     Next.js
├── rules/        조건 JSON (manual: 손 조건표, compiled: AI 추출)
├── data/         API 덤프(raw), 원문과 줄 목록(notices), 가상 인구(population, 커밋 안 함)
├── eval/         페르소나, 손 조건표 개발·시험 분할, 표본 채점, 결과
└── docs/
```

## 준비물

- Python 3.11, [uv](https://docs.astral.sh/uv/)
- Node.js 20 이상, npm
- (선택) 스캔 PDF의 줄 좌표가 필요하면 tesseract: `brew install tesseract tesseract-lang`. 없으면 네이토 API가 글자를 읽고 좌표 없이 쪽만 칠한다.

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
| `CODYSSEY_API_KEY`, `CODYSSEY_BASE_URL`, `LLM_MODEL`, `LLM_MODEL_BULK`, `LLM_MODEL_OCR`(선택), `ZINGGUM_OCR`(선택) | 대회 지급 네이토 API(usr.codyssey.kr API 콘솔). Anthropic 방식 키라 Claude 모델만 쓴다 |
| `DATA_GO_KR_KEY` | data.go.kr 마이페이지의 인증키. 쓰는 API마다 활용신청 |
| `YOUTHCENTER_API_KEY` | 온통청년 마이페이지 > OPEN API 신청(심의 뒤 발급) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | 이메일 알림 발송 계정 |
| `NEXT_PUBLIC_API_BASE` | 화면이 부를 API 주소. `frontend/.env.local`에 같은 이름으로 둔다 |
| `DATABASE_URL`, `TEST_DATABASE_URL` | 로컬 PostgreSQL 주소(아래 「실행」의 DB 준비). 회원가입과 로그인, 검색 개인화에 필요하다 |
| `COOKIE_SECURE` | 세션 쿠키 `Secure`. HTTPS 배포에서 `1`, 로컬 http 개발에서는 비운다 |
| `DEV_STUB_API` | `1`이면 `/profiles`, `/judge`가 열린다(시연 프리셋). `/profiles`와 `/judge`가 세션으로 바뀌기 전까지 시연에 필요하다 |
| `AI_ELIGIBLE` | 검수 전 AI 조건표도 `eligible`을 낼지. 이번 제출은 비운다(SPEC §5.2) |

## 실행

명령은 전부 **레포 루트에서** 실행합니다. uv 프로젝트는 `backend/` 안에 있어서 `--project backend`를 붙입니다. 그래야 `backend.engine` 같은 모듈 경로가 잡힙니다.

DB 준비 (PostgreSQL, 처음 한 번과 `backend/db/migrations/`에 새 파일이 생겼을 때). `.env`의 `DATABASE_URL`에 적용한다:

```bash
createdb zinggumdari
uv run --project backend python -m backend.db.migrate
```

DB 테스트까지 돌리려면 테스트용 DB를 하나 더 만들고(`createdb zinggumdari_test`) `.env`에 `TEST_DATABASE_URL`을 넣는다. 없으면 DB 테스트는 건너뛴다. 테스트는 그 DB 안에 무작위 스키마(`test_…`)를 만들어 쓰고 끝나면 그 스키마만 지운다(`public`은 건드리지 않는다). CI는 PostgreSQL 서비스를 띄워 DB 테스트까지 돌린다.

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
uv add --project backend httpx pdfplumber scikit-learn numpy pandas pyarrow python-dotenv
```

```bash
uv add --project backend --dev pytest
```

모듈 경로가 잡히도록 패키지 표시 파일을 만듭니다. `uv init`이 만든 `backend/main.py`는 지웁니다.

```bash
touch backend/__init__.py && mkdir -p backend/app && touch backend/app/__init__.py && rm -f backend/main.py
```

마지막으로 [docs/external-resources.md](docs/external-resources.md)에 설치한 것을 적었는지 확인하고 첫 커밋을 합니다. 첫 커밋 시각은 외부 자원 표에 적습니다.
