This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## 공개 공고 검색 API 연결

`/search`는 고정 예시 대신 백엔드 `GET /search`를 호출합니다. 실행 명령은 루트 README를 따릅니다.

- `frontend/.env.example`을 참고해 `frontend/.env.local`에 `NEXT_PUBLIC_API_BASE`를 설정합니다. 생략하면 로컬 API 주소를 사용합니다. 설정 변경 뒤 프론트 개발 서버를 다시 시작합니다.
- 이 값은 브라우저에 공개됩니다. API 키·비밀번호를 넣지 않습니다.
- 브라우저는 같은 출처의 `/api/backend`로 요청하고 Next.js rewrites가 `NEXT_PUBLIC_API_BASE`의 백엔드에 전달합니다. 따라서 로컬 프론트가 3001번이어도 브라우저 CORS와 교차 사이트 쿠키 문제 없이 같은 경로를 사용합니다. 백엔드는 별도로 실행해야 하며 인증에는 PostgreSQL과 마이그레이션이 필요합니다.
- 검색어와 대상 필터를 API로 전송합니다. `credentials: "include"`로 로그인 세션 쿠키를 전송합니다. 비로그인 검색도 가능하며, 개인화 대상은 서버가 세션에서 결정합니다. 사용자 ID는 보내지 않고 검색어는 프론트 URL·저장소·콘솔에 남기지 않습니다.
- 결과의 원문 링크·기준일은 서버 값을 사용합니다. 링크가 없으면 미연결로 표시합니다. `judge: fake`의 배지를 확정 자격으로 표시하지 않습니다.

## 실제 서비스 연결 화면

- `/my`: 세션 확인 → 기본 프로필 저장 → 카드·타임라인·단계 넘기기·공고별 질문·원문·실제 공고 투입.
- `/my/alerts`: 주거·소득·청약·부양·이메일 설정, 별도 민감정보 동의.
- `/my/parents`: 부모님 동의와 공식 판정 결과 입력. 민감정보 동의 해제는 본인 정보에도 공통 적용됩니다.
- `/settings`: 로그아웃과 계정 전체 탈퇴. 삭제 실패를 성공으로 표시하지 않습니다.
- `/notifications`: 실제 알림과 읽음 저장. 실제 이메일 발송 완료를 의미하지 않습니다.
- PDF는 `pdfjs-dist`로 렌더링하고 서버 `evidence.page/bbox`만 강조합니다. 좌표 없는 OCR 근거는 텍스트로 표시합니다.
- 자격 질문의 예·아니오는 `has: Y/N`으로 DB에 저장됩니다. 사용 전 `0005_qualification_has.sql`까지 기존 마이그레이션 명령으로 적용해야 합니다. 생년월일은 최신 계약의 `birth_date`를 사용합니다.

# 🟩 Vercel·Render 연결 확인

## 🟢 화면과 API 주소

- Vercel의 Root Directory는 `frontend`입니다. 기존 `NEXT_PUBLIC_API_BASE`에는 Render Web Service의 HTTPS 원점을 설정합니다. DB 주소와 `/api` 경로를 넣지 않습니다.
- 브라우저의 인증·프로필·추천·검색·업로드는 `/api/backend/*`를 사용합니다. Next.js가 같은 출처에서 전달하므로 세션 쿠키를 직접 읽거나 브라우저 저장소에 복사하지 않습니다.
- 공개 별칭 `/api/health`, `/api/search`도 같은 설정에서 각각 백엔드 `/health`, `/search`로 전달합니다. 별도 도메인을 하드코딩한 `vercel.json`은 사용하지 않습니다.
- Vercel 환경변수 변경 후에는 새 배포가 필요합니다. 서버의 첫 연결이 느릴 수 있어 일반 요청은 최대 90초, 공고 투입은 기존 15분 제한을 사용합니다. 이 값은 플랫폼 자체의 제한을 늘리지 않습니다.

## 🟢 Render 시작 설정

레포 루트를 기준으로 사용자가 설정한 Start Command입니다. [Render 포트 바인딩 안내](https://render.com/docs/web-services#port-binding)대로 `0.0.0.0`과 `$PORT`를 사용합니다.

```bash
uv run --project backend python -m backend.db.migrate && uv run --project backend uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

- Render의 `DATABASE_URL`과 마이그레이션이 준비되어야 가입·로그인·저장이 됩니다. DBeaver 연결만으로 테이블 적용까지 확인된 것은 아닙니다.
- HTTPS 배포의 `COOKIE_SECURE=1` 설정을 확인합니다. 키·비밀번호·DB URL은 문서나 화면에 붙이지 않습니다.
- `/health` 성공은 프로세스 응답 확인입니다. DB 저장까지 확인하려면 가상 계정의 가입 → 기본 정보 → 질문 저장 → 설정 재조회가 필요합니다.

## 🟢 클라이언트 오류 처리 회귀 확인

추가 패키지 없이 기존 TypeScript와 Node의 기본 테스트 도구로 실행합니다. 실제 API나 DB에 요청하지 않습니다.

```bash
cd frontend
node --test scripts/check-api-contract.cjs
```
