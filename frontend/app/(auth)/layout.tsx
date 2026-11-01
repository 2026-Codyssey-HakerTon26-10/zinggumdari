import type { ReactNode } from "react"; // 로그인과 회원가입 화면을 담을 자식 요소의 형식을 가져옵니다.
import Link from "next/link"; // 홈페이지로 이동하는 링크를 가져옵니다.
import { Brand, Icon } from "../components/ui"; // 기존 브랜드와 아이콘을 함께 사용합니다.
import "./auth.css"; // 두 인증 화면의 공통 디자인을 불러옵니다.

const previewCards = [ // 실제 자격을 단정하지 않고 화면 구성을 소개하는 예시예요.
    { name: "청년전용 버팀목전세자금", verdict: "needs-check", verdictLabel: "확인 필요", condition: "소득·자산 등 공고별 조건을 확인해 주세요.", quote: "공식 공고 원문 연결 전 · 화면 예시" }, // 접수가 끝난 함정 제도 대신 시연 세트의 제도를 소개해요.
    { name: "신혼부부전용 전세자금", verdict: "needs-check", verdictLabel: "확인 필요", condition: "혼인 상태와 소득 등 필요한 정보를 확인해 주세요.", quote: "공식 공고 원문 연결 전 · 화면 예시" }, // 다른 제도의 지침을 출처로 붙이지 않아요.
    { name: "기초연금 (부모님)", verdict: "needs-check", verdictLabel: "확인 필요", condition: "소득인정액 확인 필요 · 재산 환산 필요", quote: "공식 공고 원문 연결 전 · 화면 예시" }, // 연결되지 않은 금액과 실제 수급 자격을 단정하지 않아요.
]; // 가상 화면 예시 목록을 마쳐요.

function AuthIntro() { // 로그인과 회원가입에 공통으로 보일 시연용 화면 미리보기예요.
    return (
        <aside className="auth-intro" aria-label="징검다리 필터링 미리보기"> {/* 서비스 화면을 미리 보여주는 영역이에요. */}
            <span className="auth-intro-eyebrow"><span />가입하면 이런 결과를 볼 수 있어요</span> {/* 상단 안내 문구예요. */}
            <h2 className="auth-intro-title">나에게 맞는 제도를<br /><span>이렇게 알려줘요</span></h2> {/* 소개 제목이에요. */}
            <div className="auth-preview-profile"> {/* 가상 프로필 표시줄이에요. */}
                <span className="auth-preview-profile-icon"><Icon name="user" /></span> {/* 사람 아이콘이에요. */}
                <span>가상 사용자 · 32세 · 청년 단계</span> {/* 시연용 가상 프로필이에요. */}
                <span className="auth-preview-badge">시연용 가상 사례</span> {/* 가상 사례임을 명확히 표시해요. */}
            </div>
            <div className="auth-preview-cards"> {/* 필터링 결과 카드 목록이에요. */}
                {previewCards.map((card) => (
                    <div className={`auth-preview-card auth-preview-card--${card.verdict}`} key={card.name}> {/* 판정 등급별로 색을 구분해요. */}
                        <p className="auth-preview-card-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 카드마다 모의 판정 고지를 먼저 보여줘요. */}
                        <div className="auth-preview-card-top"> {/* 카드 상단 행이에요. */}
                            <span className={`auth-preview-verdict auth-preview-verdict--${card.verdict}`}>{card.verdictLabel}</span> {/* 판정 등급 배지예요. */}
                            <strong className="auth-preview-card-name">{card.name}</strong> {/* 제도 이름이에요. */}
                        </div>
                        <p className="auth-preview-card-condition"><Icon name="info" />{card.condition}</p> {/* 주요 조건이에요. */}
                        <p className="auth-preview-card-quote"><Icon name="file" />{card.quote}</p> {/* 원문 출처를 표시해요. */}
                    </div>
                ))}
            </div>
            <p className="auth-preview-disclaimer"> {/* 가상 판정임을 명시해요. */}
                참고용 모의 판정 · 실제 자격은 접수 기관 심사로 결정됩니다
            </p>
        </aside>
    );
} // 공통 소개 영역을 마칩니다.
export default function AuthLayout({ children }: { children: ReactNode }) { // 인증 화면을 공통 레이아웃 안에 배치합니다.
    return <div className="auth-page"><header className="auth-header"><div className="auth-header-inner"><Brand /><Link href="/" className="auth-home-link">홈으로 돌아가기<Icon name="arrow-right" /></Link></div></header><main id="main-content" className="auth-main"><AuthIntro />{children}</main><footer className="auth-footer"><span>© 2026 징검다리 · 코디세이 AI 해커톤 프로젝트</span><span>공공기관이 운영하는 서비스가 아닙니다.</span><nav aria-label="개인정보와 문의"><Link href="/privacy">개인정보처리방침</Link><a href="mailto:chobolimkyu@gmail.com">chobolimkyu@gmail.com</a></nav></footer></div>; // 상단 브랜드와 본문, 프로젝트 안내를 흰색 화면에 배치합니다.
} // 공통 인증 레이아웃을 마칩니다.
