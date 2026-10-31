import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() { // 브라우저와 API를 같은 출처로 연결해 로컬 포트·배포 도메인 차이를 해결해요.
    const target = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, ""); // 기존 API 주소를 서버의 전달 대상으로 사용해요.
    const address = new URL(target); // 잘못된 주소는 조용히 다른 곳으로 보내지 않아요.
    if (!["http:", "https:"].includes(address.protocol) || address.username || address.password) throw new Error("API 주소 설정을 확인해 주세요."); // 주소에 키·비밀번호를 넣지 않아요.
    return [{ source: "/api/backend/:path*", destination: `${target}/:path*` }]; // 쿠키를 포함한 원래 요청을 백엔드로 전달해요.
  },
  experimental: {
    proxyTimeout: 900_000, // 공고 투입은 캐시 재생도 40초 넘게 걸려요. 기본 30초면 프록시가 먼저 끊어 500이 나서 화면 요청 시간(15분)과 맞춰요.
    proxyClientMaxBodySize: 31 * 1024 * 1024, // 투입 파일 30MB(백엔드 MAX_BYTES) + 폼 여유. 기본 10MB면 큰 공고가 프록시에서 잘려요.
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
