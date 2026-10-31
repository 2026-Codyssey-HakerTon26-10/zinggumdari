import type { Metadata } from "next"; // 검색과 브라우저에 표시할 페이지 정보 형식을 가져와요.
import type { ReactNode } from "react"; // 레이아웃에 들어갈 화면의 형식을 가져와요.
import "./globals.css"; // 모든 화면이 함께 사용하는 색상과 기본 스타일을 불러와요.

export const metadata: Metadata = { // 서비스 이름과 소개를 브라우저에 알려줘요.
    title: { default: "징검다리 | 다음 단계의 혜택을 먼저", template: "%s | 징검다리" }, // 기본 제목과 하위 화면 제목 모양을 정해요.
    description: "물어보기 전에 먼저 찾아드려요. 나의 다섯 단계부터 부모님까지, 생애주기에 맞는 제도를 공고 원문 근거와 함께 살펴보세요.", // 서비스의 목적을 짧게 설명해요.
}; // 페이지 정보 설정을 마쳐요.

export default function RootLayout({ children }: { children: ReactNode }) { // 모든 페이지를 감싸는 공통 틀을 만들어요.
    return <html lang="ko"><body><a className="skip-link" href="#main-content">본문으로 바로가기</a>{children}</body></html>; // 한국어 설정과 키보드 사용자를 위한 본문 이동 링크를 제공해요.
} // 공통 레이아웃을 마쳐요.
