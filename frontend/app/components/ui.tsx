import Link from "next/link"; // 페이지를 새로 불러오지 않고 화면 사이를 이동해요.
import { HeaderSessionActions } from "./header-session-actions"; // 서버 세션에 맞춰 계정 메뉴를 보여줘요.
import { MobileTabBar } from "./mobile-tab-bar"; // 휴대전화 화면 아래에 고정되는 주요 메뉴예요.

const iconPaths: Record<string, string> = { // 외부 아이콘 파일 대신 직접 그린 선 모양을 모아 둬요.
    "arrow-right": "M4 12h15m-6-6 6 6-6 6", // 오른쪽 이동 화살표를 그려요.
    "arrow-up-right": "M6 18 18 6M6 6h12v12", // 새 화면 방향의 화살표를 그려요.
    "chevron-right": "m9 5 7 7-7 7", // 항목을 펼치는 화살표를 그려요.
    "chevron-down": "m5 9 7 7 7-7", // 아래로 펼치는 화살표를 그려요.
    "chevron-left": "m15 5-7 7 7 7", // 이전 항목으로 돌아가는 화살표를 그려요.
    search: "m20 20-5-5M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0", // 검색용 돋보기를 그려요.
    bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4", // 알림 종을 그려요.
    notifications: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4", // 알림 화면에서도 같은 종을 사용해요.
    check: "m5 12 4 4L19 6", // 확인 표시를 그려요.
    "check-circle": "M22 11v1a10 10 0 1 1-6-9M9 11l3 3L22 4", // 원 안의 확인 표시를 그려요.
    shield: "M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4m-4 9 3 3 5-5", // 정보 보호 안내에 사용할 방패를 그려요.
    file: "M14 2H5v20h14V7l-5-5v5h5M8 12h8M8 16h5", // 원문 문서 모양을 그려요.
    document: "M14 2H5v20h14V7l-5-5v5h5M8 12h8M8 16h5", // 문서 안내에서도 같은 모양을 사용해요.
    user: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2", // 나의 프로필을 나타내는 사람을 그려요.
    family: "M10 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0m10 1a3 3 0 1 1-6 0 3 3 0 0 1 6 0M1 21v-3a6 6 0 0 1 11-3m1 6v-2a5 5 0 0 1 10 0v2M9 21v-2a3 3 0 0 1 6 0v2", // 가족과 부모님을 나타내는 사람들을 그려요.
    heart: "M20 4c-3-2-6 0-8 2-2-2-5-4-8-2s-2 6 0 8l8 8 8-8c2-2 3-6 0-8", // 가족을 위한 마음을 하트로 그려요.
    home: "m2 11 10-9 10 9M5 9v12h14V9M9 21v-8h6v8", // 주거와 홈 화면을 나타내요.
    bookmark: "M6 3h12v18l-6-4-6 4V3", // 제도를 보관하는 책갈피를 그려요.
    sparkles: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3M21 2v4m-2-2h4", // 발견과 추천을 별빛으로 나타내요.
    settings: "M4 7h16M4 17h16M8 4v6m8 4v6", // 정보 설정을 조절 막대로 나타내요.
    close: "m6 6 12 12M6 18 18 6", // 열린 창이나 입력을 닫는 표시를 그려요.
    plus: "M12 5v14M5 12h14", // 항목을 더하는 표시를 그려요.
    menu: "M4 6h16M4 12h16M4 18h16", // 작은 화면의 메뉴 표시를 그려요.
    info: "M12 16v-4m0-4v.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0", // 추가 설명을 나타내요.
    clock: "M12 6v6l4 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0", // 단계와 시간을 시계로 나타내요.
    leaf: "M20 3C10 1 2 8 5 15s15 5 15-12M4 21 16 9", // 청년의 시작을 새 잎으로 나타내요.
    baby: "M9 4c-1-3 5-3 4 0M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M8 11v1m8-1v1m-7 4c2 2 4 2 6 0", // 출산과 육아 단계를 아기 얼굴로 나타내요.
    building: "M4 21V3h11v18M15 9h5v12M8 7h3M8 11h3M8 15h3M2 21h20", // 공공기관을 건물로 나타내요.
    layers: "m12 3 10 5-10 5L2 8l10-5M2 12l10 5 10-5M2 16l10 5 10-5", // 여러 단계가 쌓이는 모습을 그려요.
    mail: "M3 5h18v14H3V5m0 1 9 7 9-7", // 이메일 안내를 편지로 나타내요.
    trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7", // 삭제 동작을 휴지통으로 나타내요.
    filter: "M3 5h18l-7 8v6l-4 2v-8L3 5", // 검색 조건을 거름 모양으로 나타내요.
    refresh: "M20 8a8 8 0 1 0 0 8M20 3v5h-5", // 처음 상태로 돌아가는 표시를 그려요.
    lock: "M6 11h12v10H6V11m2 0V7a4 4 0 0 1 8 0v4m-4 4v2", // 비밀번호 입력을 자물쇠로 나타내요.
    eye: "M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12m13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0", // 비밀번호를 보여주는 눈 모양을 그려요.
    "eye-off": "m3 3 18 18M10 5c7-1 12 7 12 7s-2 4-5 6M7 6c-3 2-5 6-5 6s3 7 10 7c1 0 2 0 3-1m-5-8a3 3 0 0 0 4 4", // 비밀번호를 숨기는 눈 모양을 그려요.
    "log-out": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9", // 로그아웃 버튼에 사용하는 문 밖 화살표예요.
}; // 사용할 아이콘 목록을 마쳐요.

export function Icon({ name, className = "" }: { name: string; className?: string }) { // 이름을 받아 같은 크기의 아이콘을 만들어요.
    return <svg className={`icon ${className}`} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name] ?? iconPaths.file} /></svg>; // 장식 아이콘을 보조기기가 중복해서 읽지 않게 해요.
} // 아이콘 함수를 마쳐요.

export function Brand() { // 모든 화면에 사용할 징검다리 로고를 만들어요.
    return <Link href="/" className="brand" aria-label="징검다리 홈"><span className="brand-mark" aria-hidden="true"><span /><span /><span /></span><span className="brand-name">징검다리<span className="brand-caption">당신의 다음 걸음을 함께</span></span></Link>; // 크기가 다른 세 돌과 한글 서비스 이름을 배치해요.
} // 로고 함수를 마쳐요.

export function SiteHeader({ active = "home" }: { active?: "home" | "search" | "my" | "notifications" }) { // 현재 화면을 표시하는 공통 메뉴를 만들어요.
    const links = [{ href: "/my", label: "내 징검다리", key: "my", icon: "layers" }, { href: "/search", label: "공고 검색", key: "search", icon: "search" }, { href: "/notifications", label: "알림함", key: "notifications", icon: "bell" }]; // 메뉴와 연결될 화면을 정해요.
    const tabs = [{ href: "/", label: "홈", icon: <Icon name="home" /> }, ...links.map((link) => ({ href: link.href, label: link.key === "my" ? "내 추천" : link.key === "search" ? "검색" : "알림", icon: <Icon name={link.icon} /> })), { href: "/settings", label: "설정", icon: <Icon name="settings" /> }]; // 하단 탭은 좁은 폭에 맞춰 짧은 이름을 써요.
    return <><header className="site-header"><div className="container header-inner"><Brand /><nav className="desktop-nav" aria-label="주요 메뉴">{links.map((link) => <Link key={link.key} href={link.href} className={active === link.key ? "nav-link is-active" : "nav-link"} aria-current={active === link.key ? "page" : undefined}><Icon name={link.icon} />{link.label}</Link>)}</nav><HeaderSessionActions navigation={[{ href: "/", label: "홈", icon: "home" }, ...links].map((link) => <Link key={link.href} href={link.href} aria-current={active === ("key" in link ? link.key : "home") ? "page" : undefined}><Icon name={link.icon} />{link.label}</Link>)} menuIcon={<Icon name="menu" />} closeIcon={<Icon name="close" />} arrowIcon={<Icon name="arrow-right" />} /></div></header><MobileTabBar tabs={tabs} /></>; // 헤더 밖에 하단 탭을 둬야 헤더의 흐림 효과가 고정 위치를 가두지 않아요.
} // 공통 헤더를 마쳐요.

export function SiteFooter() { // 서비스의 성격을 분명히 알리는 하단을 만들어요.
    return (
        <footer className="site-footer"> {/* 하단 전체 영역이에요. */}
            <div className="container footer-main"> {/* 브랜드 소개와 링크를 양쪽에 배치해요. */}
                <div>
                    <Brand /> {/* 하단 로고예요. */}
                    <p>오늘을 챙기고, 다음을 준비하는 작은 징검다리.<br />나의 생애주기부터 부모님의 일상까지 함께 살펴봐요.</p> {/* 서비스 소개 한 줄이에요. */}
                </div>
                <div className="footer-links"> {/* 주요 바로가기 링크 목록이에요. */}
                    <Link href="/#how-it-works">서비스 소개</Link> {/* 사용 방법으로 이동해요. */}
                    <Link href="/search">공고 검색</Link> {/* 검색 화면으로 이동해요. */}
                    <Link href="/my?subject=parent">부모님 챙김</Link> {/* 부모님 진단 화면으로 이동해요. */}
                    <Link href="/privacy">개인정보처리방침</Link> {/* 개인정보 수집과 삭제 방법을 공개 안내로 연결해요. */}
                    <a href="mailto:chobolimkyu@gmail.com">chobolimkyu@gmail.com</a> {/* 사용자가 요청한 문의 이메일을 표시해요. */}
                </div>
            </div>
            <div className="container footer-bottom"> {/* 저작권과 안내를 하단에 표시해요. */}
                <span>© 2026 징검다리팀 · 코디세이 AI 해커톤 프로젝트</span> {/* 팀 이름과 프로젝트 이름이에요. */}
                <span>공공기관이 운영하는 서비스가 아닙니다.</span> {/* 공공기관 사칭 방지 안내예요. */}
            </div>
        </footer>
    );
} // 공통 푸터를 마쳐요.
