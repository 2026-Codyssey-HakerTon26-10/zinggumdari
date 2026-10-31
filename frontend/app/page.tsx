import Link from "next/link"; // 주요 버튼을 서비스 화면과 연결해요.
import { Icon, SiteFooter, SiteHeader } from "./components/ui"; // 공통 아이콘과 상하단 메뉴를 불러와요.
import { JourneyPreview } from "./components/journey-preview"; // 다섯 단계로 이루어진 생애주기 그림을 불러와요.

function Hero() { // 처음 방문한 사람에게 서비스의 목적을 소개해요.
    return <section className="landing-hero"><div className="container hero-grid"><div className="hero-copy"><span className="eyebrow hero-eyebrow"><span className="live-dot" />부모님 것까지, 신고하기 전에</span><h1>물어보기 전에<br /><span>먼저 찾아드려요</span><span className="headline-period">.</span></h1><p className="hero-description">나와 부모님 정보를 고르기만 하면,<br className="desktop-break" /> 받을 수 있는 제도와 거의 해당하는 제도를<br className="desktop-break" /> 공고 원문 근거와 함께 보여드려요.</p><div className="hero-actions"><Link className="button button-primary button-large" href="/my">3분 만에 확인하기<Icon name="arrow-right" /></Link><Link className="button button-secondary button-large" href="/my?subject=parent"><Icon name="family" />부모님 대신 확인하기</Link></div><p className="hero-action-note">로그인 없이 시작해요 · 입력 시간은 개인마다 달라요</p><div className="hero-trust"><span><Icon name="shield" />주민등록번호 입력 없이</span><span><Icon name="file" />공고 원문 근거와 함께</span></div></div><JourneyPreview /></div><div className="hero-bottom-label"><span />오늘의 나를 알고, 내일의 가능성을 잇다<span /></div></section>; // 지정된 히어로 문구와 두 가지 시작 버튼을 하늘색 화면에 담아요.
} // 첫 화면 소개를 마쳐요.

function DiscoveryCards() { // 제공된 디자인의 사례와 지표 세 장을 소개해요.
    return <section className="discover-section"><div className="container"><div className="section-heading"><div><span className="eyebrow">모르면 지나치는 제도, 이제는 먼저</span><h2 className="section-title">놓치고 있던 가능성을 발견해요</h2></div><span className="section-side-note">나의 오늘도, 부모님의 내일도</span></div><div className="discovery-grid"><article className="discovery-card story-card"><div className="card-topline"><span className="soft-icon"><Icon name="family" /></span><span className="pill">시연용 가상 사례</span></div><p className="card-label">예시 · 32세 민지 씨</p><h3>“엄마에게 필요한 제도도<br />함께 챙길 수 있네요.”</h3><p>어머니의 기초연금 확인 항목과<br />몰랐던 돌봄 서비스 2개를 살펴보는 이야기예요.</p><span className="card-footnote">사례의 수치는 가상이며, 실제 자격 판정이 아닙니다.</span></article><article className="discovery-card metric-card"><div className="card-topline"><span className="soft-icon"><Icon name="search" /></span><span className="pill pill-gray">디자인 참고 수치</span></div><p className="card-label">기초연금 기준 이하 노인</p><div className="discovery-metric">175<span>만 명</span><span className="metric-asterisk">*</span></div><p>830만 명 중 받지 않는 사람</p><span className="card-footnote">제공 시안 출처 · 국민연금연구원 (2026.6 보도)<br />* 제공된 참고 수치이며, 출처 원문 확인 전입니다.</span></article><article className="discovery-card possibility-card"><div className="card-topline"><span className="soft-icon"><Icon name="sparkles" /></span><span className="pill">조건 하나의 가능성</span></div><p className="card-label">한 가구당 거의 해당</p><div className="discovery-metric">평균 <span className="unmeasured-number">○</span><span>개</span></div><p>조건 하나만 확인하면 되는 제도</p><span className="card-footnote">가상 인구 1만 가구 기준 · 집계 전<br />실제 집계값이 연결되면 표시됩니다.</span></article></div></div></section>; // 가상 사례와 미확인 통계, 미집계 수치를 사실과 구분해서 표시해요.
} // 발견 사례 영역을 마쳐요.

const processSteps = [ // 입력부터 확인까지의 서비스 흐름을 정리해요.
    { number: "01", icon: "user", title: "나의 지금을 알려주세요", description: "현재 생애 단계와 기본 정보를 골라요.\n꼭 필요한 정보부터 차근차근 여쭤봐요." }, // 최소한의 정보로 시작하는 방법을 알려줘요.
    { number: "02", icon: "layers", title: "다음 단계도 미리 살펴봐요", description: "청년부터 다자녀까지 다섯 단계.\n변화하는 일상에 맞는 제도를 찾아봐요." }, // 예정 날짜 없이 단계를 넘겨보는 방법을 알려줘요.
    { number: "03", icon: "file", title: "근거를 보고, 함께 준비해요", description: "확정 · 확인 필요 · 질문을 구분하고,\n공고 원문과 필요한 서류를 확인해요." }, // 판정 근거와 추가 확인을 함께 보는 방법을 알려줘요.
]; // 서비스 흐름 목록을 마쳐요.

function HowItWorks() { // 서비스 사용 과정을 세 단계로 안내해요.
    return <section className="how-section" id="how-it-works"><div className="container"><div className="section-heading centered"><span className="eyebrow">복잡한 제도 앞에서, 더 간단한 시작</span><h2 className="section-title">하나씩 고르면, 다음이 보여요</h2><p>모든 걸 알고 시작할 필요는 없어요. 지금 아는 정보부터 함께 살펴봐요.</p></div><div className="process-grid">{processSteps.map((step) => <article className="process-step" key={step.number}><div className="process-top"><span className="process-icon"><Icon name={step.icon} /></span><span className="process-number">{step.number}</span></div><h3>{step.title}</h3><p>{step.description}</p></article>)}</div><div className="process-note"><Icon name="shield" /><span>소득·건강 등 민감정보는 별도 동의가 있을 때만 저장해요.</span></div></div></section>; // 단계별 목적과 민감정보 동의 원칙을 함께 안내해요.
} // 사용 방법 소개를 마쳐요.

const comparisons = [ // 다른 서비스와의 비교를 단정적인 비판 대신 이용 방식으로 정리해요.
    { name: "정부24 · 복지멤버십", caption: "공공서비스 안내", icon: "building", title: "공공서비스를 찾아볼 때", points: ["공식 제도와 신청 정보를 확인하는 출발점", "서비스마다 제공 범위와 이용 방법이 달라요"], highlight: false }, // 공공 포털의 일반적인 이용 목적을 설명해요.
    { name: "ChatGPT", caption: "대화형 정보 탐색", icon: "sparkles", title: "궁금한 것을 물어볼 때", points: ["질문을 통해 관련 정보를 탐색해요", "개별 제도의 공고 원문과 자격을 따로 확인해요"], highlight: false }, // 다른 제품의 출처 제공 여부를 단정하지 않아요.
    { name: "징검다리", caption: "생애주기 맞춤 추천", icon: "layers", title: "묻기 전에, 부모님 것까지", points: ["다음 생애 단계의 제도까지 미리 살펴봐요", "확인할 조건과 공고 원문 근거를 함께 봐요"], highlight: true }, // 징검다리의 서비스 방향을 구체적으로 설명해요.
]; // 비교 목록을 마쳐요.

function Comparison() { // 제공 시안의 정부24와 ChatGPT 비교 영역을 구성해요.
    return <section className="comparison-section"><div className="container"><div className="section-heading centered"><span className="eyebrow">필요한 정보를 넘어, 다음의 가능성으로</span><h2 className="section-title">정부24, ChatGPT와 무엇이 다른가요</h2><p>징검다리는 나의 생애주기와 공고 원문 사이에 징검다리를 놓아요.</p></div><div className="comparison-grid">{comparisons.map((item) => <article className={`comparison-card ${item.highlight ? "comparison-featured" : ""}`} key={item.name}>{item.highlight && <span className="comparison-ribbon">나의 다음 걸음과 함께</span>}<div className="comparison-icon"><Icon name={item.icon} /></div><span className="comparison-caption">{item.caption}</span><h3>{item.name}</h3><p className="comparison-title">{item.title}</p><ul>{item.points.map((point) => <li key={point}><Icon name={item.highlight ? "check-circle" : "check"} /><span>{point}</span></li>)}</ul>{item.highlight && <p className="comparison-closing">원문 근거와 함께, 차근차근.</p>}</article>)}</div></div></section>; // 비교 영역을 동일한 정보 밀도로 정리하고 징검다리를 강조해요.
} // 서비스 비교 영역을 마쳐요.

function StartSection() { // 자신과 부모님 중 어디서 시작할지 안내해요.
    return <section className="start-section"><div className="container start-panel"><div className="start-copy"><span className="eyebrow">당신의 다음 걸음, 여기에서</span><h2>어떤 정보를<br />확인하고 싶으신가요?</h2><p>오늘 필요한 제도부터 앞으로 열릴 제도까지.<br />나에게 맞는 징검다리를 찾아보세요.</p></div><div className="start-choices"><Link href="/my" className="start-choice"><span className="start-choice-icon"><Icon name="user" /></span><span><strong>내 혜택 진단하기</strong><small>나의 다섯 단계에 맞는 제도를 살펴봐요</small></span><Icon name="arrow-right" /></Link><Link href="/my?subject=parent" className="start-choice"><span className="start-choice-icon"><Icon name="family" /></span><span><strong>부모님 혜택 진단하기</strong><small>부모님을 위한 제도도 따로 챙겨봐요</small></span><Icon name="arrow-right" /></Link><span className="start-demo-note">현재는 시연용 화면입니다. 실제 프로필을 저장하지 않습니다.</span></div></div></section>; // 두 시작 버튼을 실제 디자인 화면에 연결하고 시연임을 알려줘요.
} // 시작 안내 영역을 마쳐요.

export default function Home() { // 소개부터 사용 방법까지 이어지는 랜딩페이지를 만들어요.
    return <><SiteHeader active="home" /><main id="main-content"><Hero /><DiscoveryCards /><HowItWorks /><Comparison /><StartSection /></main><SiteFooter /></>; // 모든 랜딩 영역을 공통 메뉴와 하단 사이에 배치해요.
} // 랜딩페이지 구성을 마쳐요.
