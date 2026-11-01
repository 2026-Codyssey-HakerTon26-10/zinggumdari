# 징검다리 화면 (frontend)

Next.js 16(App Router)으로 만든 화면입니다. 설치·환경설정·백엔드 실행을 포함한 전체 실행 방법은 [루트 README](../README.md)가 정본입니다.

## 준비물

- Node.js 20 이상, npm
- 같은 컴퓨터에서 도는 API 서버(루트 README의 「실행」). 화면만 띄우면 로그인·추천은 API 연결 오류로 나온다

## 설치와 환경설정

레포 루트에서 실행합니다.

```bash
cd frontend && npm install && cp -n .env.example .env.local && cd ..
```

| 변수 | 뜻 |
|---|---|
| `NEXT_PUBLIC_API_BASE` | API 서버 주소. 로컬은 `http://localhost:8000`. 화면은 이 주소로 직접 부르지 않고 `next.config.ts`의 rewrites로 `/api/backend/*`, `/api/search`, `/api/health`를 같은 출처 프록시로 넘긴다(세션 쿠키 때문) |

## 실행

```bash
cd frontend && npm run dev
```

http://localhost:3000 에서 엽니다.

## 검사와 빌드

```bash
cd frontend && npx tsc --noEmit && npm run lint && node --test scripts/check-api-contract.cjs scripts/check-auth-validation.cjs && npm run build
```

- `scripts/check-api-contract.cjs`: 화면이 부르는 API 경로·요청 모양, 검색 응답 검사, 날짜 표시 규칙
- `scripts/check-auth-validation.cjs`: 가입 이메일·비밀번호 규칙과 로그인 뒤 이동 주소 제한

## 폴더

```
app/
├── page.tsx              랜딩
├── (auth)/               로그인·회원가입
├── my/                   내 추천(카드·질문·단계·타임라인·공고 투입), 알림 설정, 부모님
├── search/               공개 공고 검색(서버 실패 때 저장해 둔 추천 검색어 결과)
├── notifications/        알림함
├── settings/  privacy/   설정, 개인정보처리방침
├── components/           공통 머리말·하단 탭·로딩·아이콘
└── lib/                  API 호출(service-api.ts), 인증, 입력 검사
```

## 화면 원칙

- 휴대전화 기본(모바일 퍼스트): 기본 스타일은 휴대전화, `min-width` 미디어 쿼리로 넓은 화면을 덧씌운다. 누르는 영역 44px, 입력칸 글씨 16px
- 자격 판정·질문·근거는 서버가 준 값만 보여주고 화면에서 만들지 않는다
- 새 패키지는 같은 커밋에서 [docs/external-resources.md](../docs/external-resources.md)에 적는다
