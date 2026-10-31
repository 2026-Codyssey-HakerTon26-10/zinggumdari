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
- 로컬에서는 프론트를 `http://localhost:3000`, API를 `http://localhost:8000`으로 사용합니다. 다른 프론트 주소는 백엔드 CORS 담당자와 허용 주소를 맞춰야 합니다.
- 검색어와 대상 필터를 API로 전송합니다. `credentials: "include"`로 로그인 세션 쿠키를 전송합니다. 비로그인 검색도 가능하며, 개인화 대상은 서버가 세션에서 결정합니다. 사용자 ID는 보내지 않고 검색어는 프론트 URL·저장소·콘솔에 남기지 않습니다.
- 결과의 원문 링크·기준일은 서버 값을 사용합니다. 링크가 없으면 미연결로 표시합니다. `judge: fake`의 배지를 확정 자격으로 표시하지 않습니다.
