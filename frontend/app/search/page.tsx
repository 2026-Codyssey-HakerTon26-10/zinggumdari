"use client"; // 검색어와 분야를 현재 화면에서 바꿀 수 있게 합니다.
import { useState, type FormEvent } from "react"; // 검색 상태와 폼 제출에 필요한 기능을 가져옵니다.
import Link from "next/link"; // 사이트 안의 화면을 이동하는 링크를 가져옵니다.
import { Icon, SiteHeader, SiteFooter } from "../components/ui"; // 사이트의 공통 머리말과 아이콘을 사용합니다.
import "./search.css"; // 검색 화면에만 쓰는 스타일을 불러옵니다.
type Category = "전체" | "주거" | "생활" | "가족·돌봄"; // 선택 가능한 분야를 제한합니다.
type PolicyExample = { id: string; title: string; category: Category; icon: string; description: string; question: string }; // 검색 예시 한 장의 모양을 정합니다.
const categories: Category[] = ["전체", "주거", "생활", "가족·돌봄"]; // 검색 분야 버튼의 순서를 정합니다.
const examples: PolicyExample[] = [ // 실제 판정과 구분되는 정책명 검색 예시를 준비합니다.
    { id: "youth-housing", title: "청년전용 버팀목 전세자금", category: "주거", icon: "home", description: "독립을 준비할 때 함께 살펴볼 주거 제도예요.", question: "주거 형태와 소득 등 공고별 조건을 확인해야 해요." }, // 지원 금액이나 신청 가능 여부를 단정하지 않습니다.
    { id: "newlywed-housing", title: "신혼부부전용 전세자금", category: "주거", icon: "home", description: "새로운 출발을 앞둔 가구를 위한 주거 제도예요.", question: "혼인 상태와 가구 소득 등 공고별 조건을 확인해야 해요." }, // 혼인 예정일을 받거나 자동으로 자격을 판단하지 않습니다.
    { id: "newborn-housing", title: "신생아 특례 디딤돌대출", category: "주거", icon: "home", description: "가족의 변화와 함께 알아볼 주택 구입 관련 제도예요.", question: "가구 정보와 공고의 적용 기준을 함께 확인해야 해요." }, // 금융사 상품이나 금리와 신청 링크를 넣지 않습니다.
    { id: "transport", title: "K-패스", category: "생활", icon: "bookmark", description: "매일의 이동과 관련된 생활 지원을 살펴보세요.", question: "이용 지역과 공식 안내의 적용 조건을 확인해야 해요." }, // 교통 이용량이나 환급 금액을 만들어내지 않습니다.
    { id: "pension", title: "기초연금", category: "가족·돌봄", icon: "family", description: "부모님의 다음 단계를 함께 챙길 때 살펴볼 제도예요.", question: "소득인정액은 재산 환산이 필요하므로 확인 필요해요." }, // 부모님의 소득인정액을 임의로 계산하지 않습니다.
    { id: "care", title: "돌봄 서비스", category: "가족·돌봄", icon: "heart", description: "가족에게 필요한 돌봄 지원의 종류를 알아보세요.", question: "거주 지역과 돌봄 관련 공식 판정 결과를 확인해야 해요." }, // 건강 정보나 자격 정보를 수집하지 않습니다.
]; // 모든 항목은 실제 공고 검색 결과가 아닌 화면 예시입니다.
function PolicyCard({ policy }: { policy: PolicyExample }) { // 예시 한 장의 표시 방법을 정합니다.
    return <article className="search-policy"><p className="search-policy-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p><div className="search-policy-top"><span className="search-policy-icon"><Icon name={policy.icon} /></span><span className="search-status">확인 필요</span></div><p className="search-policy-category">{policy.category} · 시연용 정책명 예시</p><h2>{policy.title}</h2><p className="search-policy-description">{policy.description}</p><details className="search-policy-details"><summary>확인할 내용 보기<Icon name="chevron-right" /></summary><div className="search-policy-evidence"><p>{policy.question}</p><p><strong>조건표 없음 · 자격 판정 불가</strong></p><p>원문 링크 · 연결 전<br />기준일 · 원문 연결 후 표시</p></div></details></article>; // 원문이 없을 때 자격을 확정하지 않고 연결 상태를 보여줍니다.
} // 예시 카드 표시를 마칩니다.
export default function SearchPage() { // 공고 검색 디자인 화면을 만듭니다.
    const [query, setQuery] = useState(""); // 입력 중인 검색어를 기억합니다.
    const [activeQuery, setActiveQuery] = useState(""); // 검색 버튼으로 확정한 검색어를 기억합니다.
    const [category, setCategory] = useState<Category>("전체"); // 현재 선택한 분야를 기억합니다.
    const normalizedQuery = activeQuery.toLocaleLowerCase("ko-KR").replace(/\s+/g, ""); // 띄어쓰기가 달라도 정책명을 찾을 수 있게 합니다.
    const filtered = examples.filter((policy) => (category === "전체" || policy.category === category) && `${policy.title}${policy.description}${policy.category}`.toLocaleLowerCase("ko-KR").replace(/\s+/g, "").includes(normalizedQuery)); // 분야와 검색어에 맞는 화면 예시만 골라냅니다.
    function search(event: FormEvent<HTMLFormElement>) { // 검색 폼을 제출했을 때 처리합니다.
        event.preventDefault(); // 페이지 새로고침과 서버 전송을 막습니다.
        setActiveQuery(query.trim()); // 검색어는 현재 화면 안에서만 사용합니다.
    } // 검색 처리를 마칩니다.
    function reset() { // 검색 조건을 처음 상태로 되돌립니다.
        setQuery(""); // 검색 입력을 비웁니다.
        setActiveQuery(""); // 적용한 검색어도 비웁니다.
        setCategory("전체"); // 모든 분야를 다시 보여줍니다.
    } // 초기화 처리를 마칩니다.
    return <><SiteHeader active="search" /><main id="main-content" className="search-page"><section className="search-hero"><div className="container"><Link href="/" className="search-breadcrumb">홈 <Icon name="chevron-right" /> 공고 원문 검색</Link><p className="eyebrow">공고 원문 검색</p><h1>지금 필요한 제도,<br />직접 찾아보세요<span>.</span></h1><p className="search-hero-description">나에게 필요한 지원부터 부모님을 위한 제도까지.<br className="search-desktop-break" /> 어떤 제도가 있는지 먼저 둘러보세요.</p><form className="search-form" onSubmit={search} role="search"><Icon name="search" /><label className="search-sr-only" htmlFor="policy-search">정책명 또는 관심 분야</label><input id="policy-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="정책명이나 관심 있는 분야를 입력해 주세요" maxLength={100} autoComplete="off" /><button type="submit" className="button button-primary">검색</button></form><div className="search-suggestions"><span>이런 제도는 어때요?</span>{["버팀목", "기초연금", "돌봄"].map((keyword) => <button type="button" key={keyword} onClick={() => { setQuery(keyword); setActiveQuery(keyword); }}>#{keyword}</button>)}</div></div></section><section className="container search-results"><div className="search-notice"><Icon name="file" /><p><strong>정책명 검색을 경험하는 디자인 시연이에요.</strong> 실제 공고·조건표는 연결 전이며, 검색어를 서버로 전송하거나 저장하지 않아요.</p></div><div className="search-results-toolbar"><div className="search-category-list" aria-label="정책 분야">{categories.map((item) => <button key={item} type="button" className={category === item ? "is-active" : ""} aria-pressed={category === item} onClick={() => setCategory(item)}>{item}</button>)}</div><button className="search-reset" type="button" onClick={reset}><Icon name="refresh" />초기화</button></div><div className="search-result-heading" aria-live="polite"><p>{activeQuery ? <><strong>‘{activeQuery}’</strong> 검색 예시</> : "둘러볼 정책명 예시"} <span>{filtered.length}개</span></p><span>실제 공고 결과가 아니에요</span></div>{filtered.length > 0 ? <div className="search-policy-grid">{filtered.map((policy) => <PolicyCard key={policy.id} policy={policy} />)}</div> : <div className="search-empty"><span><Icon name="search" /></span><h2>일치하는 예시가 없어요</h2><p>다른 검색어를 입력하거나 분야를 바꿔보세요.</p><button className="button button-secondary" type="button" onClick={reset}>전체 예시 보기</button></div>}<aside className="search-bottom-cta"><div><span className="eyebrow">찾는 데서 한 걸음 더</span><h2>나의 다음 단계도 미리 살펴보세요.</h2><p>다섯 단계의 징검다리에서 어떤 지원을 살펴볼지 알아보세요.</p></div><Link href="/my" className="button button-secondary">내 징검다리 보기<Icon name="arrow-right" /></Link></aside></section></main><SiteFooter /></>; // 검색과 분야 선택을 갖춘 반응형 화면을 표시합니다.
} // 검색 화면을 마칩니다.
