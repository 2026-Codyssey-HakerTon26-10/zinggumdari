import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() { // 브라우저와 API를 같은 출처로 연결해 로컬 포트·배포 도메인 차이를 해결해요.
    const target = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, ""); // 기존 API 주소를 서버의 전달 대상으로 사용해요.
    const address = new URL(target); // 잘못된 주소는 조용히 다른 곳으로 보내지 않아요.
    if (!["http:", "https:"].includes(address.protocol) || address.username || address.password) throw new Error("API 주소 설정을 확인해 주세요."); // 주소에 키·비밀번호를 넣지 않아요.
    return [{ source: "/api/backend/:path*", destination: `${target}/:path*` }]; // 쿠키를 포함한 원래 요청을 백엔드로 전달해요.
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
