import type { ReactNode } from "react"; // 로그인과 회원가입 화면을 담을 자식 요소의 형식을 가져옵니다.
import Link from "next/link"; // 홈페이지로 이동하는 링크를 가져옵니다.
import { Brand, Icon } from "../components/ui"; // 기존 브랜드와 아이콘을 함께 사용합니다.
import "./auth.css"; // 두 인증 화면의 공통 디자인을 불러옵니다.
const stages = ["청년", "신혼", "출산", "육아", "다자녀"]; // 징검다리의 다섯 단계를 소개하는 순서입니다.
const points = [ // 인증 화면 옆에서 서비스의 핵심을 간단히 소개합니다.
    { icon: "file", title: "공고 원문으로 확인해요", description: "제도마다 어떤 근거인지 함께 살펴봐요." }, // 자격을 확정하는 대신 원문 확인을 안내합니다.
    { icon: "family", title: "나와 부모님을 따로 챙겨요", description: "각자의 상황에 맞는 제도를 구분해서 봐요." }, // 본인과 부모님의 제도를 혼합하지 않습니다.
    { icon: "shield", title: "필요한 정보부터 차근차근", description: "민감한 정보는 별도 동의 후에만 받아요." }, // 민감정보 수집 원칙을 쉬운 말로 설명합니다.
]; // 소개할 핵심 항목을 마칩니다.
function AuthIntro() { // 로그인과 회원가입에 공통으로 보일 서비스 소개입니다.
    return <aside className="auth-intro" aria-label="징검다리 서비스 소개"><span className="auth-intro-eyebrow"><span />나와 가족의 다음을 잇는 서비스</span><h2 className="auth-intro-title">당신의 다음 걸음에,<br /><span>징검다리</span>가 함께할게요.</h2><p className="auth-intro-description">오늘의 혜택부터 앞으로 열릴 제도까지,<br />공고 원문을 바탕으로 차근차근 살펴보세요.</p><ol className="auth-stages" aria-label="생애주기의 다섯 단계">{stages.map((stage, index) => <li className="auth-stage" key={stage}><span>{String(index + 1).padStart(2, "0")}</span>{stage}</li>)}</ol><div className="auth-intro-points">{points.map((point) => <div className="auth-intro-point" key={point.title}><span className="auth-intro-icon"><Icon name={point.icon} /></span><div><p className="auth-intro-point-title">{point.title}</p><p className="auth-intro-point-description">{point.description}</p></div></div>)}</div></aside>; // 흰 배경 안에서 소개 문구와 다섯 단계, 핵심 안내를 표시합니다.
} // 공통 소개 영역을 마칩니다.
export default function AuthLayout({ children }: { children: ReactNode }) { // 인증 화면을 공통 레이아웃 안에 배치합니다.
    return <div className="auth-page"><header className="auth-header"><div className="auth-header-inner"><Brand /><Link href="/" className="auth-home-link">홈으로 돌아가기<Icon name="arrow-right" /></Link></div></header><main id="main-content" className="auth-main"><AuthIntro />{children}</main><footer className="auth-footer"><span>© 2026 징검다리 · 코디세이 AI 해커톤 프로젝트</span><span>공공기관이 운영하는 서비스가 아닙니다.</span></footer></div>; // 상단 브랜드와 본문, 프로젝트 안내를 흰색 화면에 배치합니다.
} // 공통 인증 레이아웃을 마칩니다.
