import type { Metadata, Viewport } from "next"; // 검색과 브라우저에 표시할 페이지 정보와 화면 크기 설정 형식을 가져와요.
import type { ReactNode } from "react"; // 레이아웃에 들어갈 화면의 형식을 가져와요.
import "./globals.css"; // 모든 화면이 함께 사용하는 색상과 기본 스타일을 불러와요.
import { ScrollReset } from "./components/scroll-reset"; // 다른 화면으로 이동하면 맨 위부터 보여줘요.

export const metadata: Metadata = { // 서비스 이름과 소개를 브라우저에 알려줘요.
    title: { default: "징검다리 | 다음 단계의 혜택을 먼저", template: "%s | 징검다리" }, // 기본 제목과 하위 화면 제목 모양을 정해요.
    description: "물어보기 전에 먼저 찾아드려요. 나의 다섯 단계부터 부모님까지, 생애주기에 맞는 제도를 공고 원문 근거와 함께 살펴보세요.", // 서비스의 목적을 짧게 설명해요.
}; // 페이지 정보 설정을 마쳐요.

export const viewport: Viewport = { // 휴대전화 화면을 기준으로 처음 보이는 크기를 정해요.
    width: "device-width", // 기기 폭에 맞춰 그려요.
    initialScale: 1, // 처음에 확대하지 않아요. 사용자의 확대는 막지 않아요.
    viewportFit: "cover", // 노치가 있는 화면에서도 하단 탭이 안전 영역까지 이어지게 해요.
    themeColor: "#ffffff", // 휴대전화 브라우저 주소창 색을 흰 화면과 맞춰요.
}; // 화면 크기 설정을 마쳐요.

export default function RootLayout({ children }: { children: ReactNode }) { // 모든 페이지를 감싸는 공통 틀을 만들어요.
    return <html lang="ko"><body><a className="skip-link" href="#main-content">본문으로 바로가기</a><ScrollReset />{children}</body></html>; // 한국어 설정, 본문 이동 링크, 화면 이동 시 맨 위부터 보여주기를 제공해요.
} // 공통 레이아웃을 마쳐요.
