"use client"; // 검색 요청과 결과 상태를 사용자의 조작에 맞춰 바꿔요.
import { useEffect, useRef, useState, type FormEvent } from "react"; // 요청 취소·입력·화면 상태를 관리해요.
import Link from "next/link"; // 사이트 안의 이동에는 Next 링크를 사용해요.
import { Icon, SiteHeader, SiteFooter } from "../components/ui"; // 기존 공통 디자인을 유지해요.
import { safeSourceUrl, formatSourceDate, searchPolicies, type SearchHit, type SearchResponse, type SearchSubject } from "./search-api"; // 실제 공개 검색 API와 원문 날짜 표시 계약을 가져와요.
import "./search.css"; // 흰색 검색 화면 스타일을 사용해요.
type View = { status: "idle" | "loading" | "error"; data: null; message: string } | { status: "ready"; data: SearchResponse; message: string }; // 실패와 결과 없음이 섞이지 않게 구분해요.
const subjects: { value: SearchSubject; label: string }[] = [{ value: "all", label: "전체" }, { value: "self", label: "본인" }, { value: "parent", label: "부모님" }]; // 실제 API가 지원하는 필터만 표시해요.
function PolicyCard({ hit, judge }: { hit: SearchHit; judge: SearchResponse["judge"] }) { // 서버가 반환한 공고 한 장을 그려요.
    const region = typeof hit.region === "string" ? hit.region : hit.region?.unknown ? "지역 미상" : [hit.region?.sido, hit.region?.sigungu].filter(Boolean).join(" "); // 서버의 지역 객체를 읽되 미상을 전국으로 바꾸지 않아요.
    const source = safeSourceUrl(hit.detail_url); // 외부 링크에 스크립트 주소가 들어오지 않게 확인해요.
    const badge = !hit.rule_id || hit.badge === "no_rule" ? "조건표 없음 · 자격 판정 불가" : judge === "fake" && hit.badge !== null ? "판정 연결 전 · 확인 필요" : hit.badge === null ? "개인화 판정 없음" : ({ eligible: "신청할 수 있어요", similar: "비슷한 가구 · 자격 확정 아님", needs_check: "확인 필요", ineligible: "현재 조건에 맞지 않음" }[hit.badge]); // 가짜 판정이나 조건표 없는 결과는 신청 가능으로 표시하지 않아요.
    return ( // 일반 텍스트만 출력하고 원문 HTML은 실행하지 않아요.
        <article className="search-policy"> {/* 실제 공고 결과 카드예요. */}
            <p className="search-policy-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 모든 카드 머리에 필수 고지를 표시해요. */}
            <div className="search-policy-top"><span className="search-policy-icon"><Icon name={hit.subject === "parent" ? "family" : "file"} /></span><span className="search-status">{badge}</span></div> {/* 대상과 상태를 글자로도 알려줘요. */}
            <p className="search-policy-category">{hit.subject === "parent" ? "부모님" : "본인"} · {hit.org || "기관 정보 없음"} · {region || "지역 미상"}</p> {/* 알 수 없는 지역을 전국으로 바꾸지 않아요. */}
            <h2>{hit.name}</h2><p className="search-policy-description">{hit.snippet || "요약 정보가 없습니다. 공식 원문을 확인해 주세요."}</p> {/* 검색 요약은 서버 문자열 그대로 안전하게 표시해요. */}
            <div className="search-policy-evidence"><p>기준일: {formatSourceDate(hit.updated)}</p>{source ? <a href={source} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">공식 원문 보기 ↗</a> : <p>공식 원문 링크 없음 · 접수 기관에서 확인해 주세요.</p>}</div> {/* 원문 날짜의 표시만 정리하고 없는 기준일은 만들지 않아요. */}
        </article> // 공고 카드 표시를 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 카드 컴포넌트를 마쳐요.
export default function SearchPage() { // 목업 대신 실제 공개 검색 결과를 보여줘요.
    const [query, setQuery] = useState(""); // 입력 중인 검색어는 현재 화면에만 둬요.
    const [subject, setSubject] = useState<SearchSubject>("all"); // 입력 중인 대상 필터를 기억해요.
    const [view, setView] = useState<View>({ status: "idle", data: null, message: "" }); // 첫 방문에는 자동 검색을 하지 않아요.
    const [lastRequest, setLastRequest] = useState({ query: "", subject: "all" as SearchSubject }); // 재시도는 실패했던 조건을 그대로 사용해요.
    const controller = useRef<AbortController | null>(null); // 이전 요청이 늦게 도착해 새 결과를 덮지 못하게 해요.
    useEffect(() => () => controller.current?.abort(), []); // 화면을 떠나면 진행 중인 요청을 취소해요.
    async function runSearch(value: string, target: SearchSubject) { // 검색 버튼·추천어·재시도가 같은 요청 함수를 사용해요.
        const trimmed = value.trim(); // 공백만 있는 입력은 요청하지 않아요.
        if (!trimmed || trimmed.length > 100) { controller.current?.abort(); setView({ status: "error", data: null, message: "검색어를 1~100자로 입력해 주세요." }); return; } // 이전 결과를 현재 검색의 결과처럼 남기지 않아요.
        controller.current?.abort(); // 기존 요청을 먼저 취소해요.
        const current = new AbortController(); controller.current = current; // 이번 요청을 식별할 취소 객체예요.
        setLastRequest({ query: trimmed, subject: target }); // 재시도할 조건을 기억해요.
        setView({ status: "loading", data: null, message: "" }); // 검색 중에는 이전 결과를 지워요.
        const timeout = window.setTimeout(() => current.abort("timeout"), 90000); // 배포 서버가 처음 깨어나는 시간도 기다리되 무한 요청은 막아요.
        try { // 연결 오류와 취소를 구분해요.
            const data = await searchPolicies(trimmed, target, current.signal); // 로그인 상태에서는 세션 쿠키를 포함해 검색 API에 요청해요.
            if (controller.current === current && !current.signal.aborted) setView({ status: "ready", data, message: "" }); // 가장 최근 요청만 표시해요.
        } catch { // 내부 오류·주소·검색어는 콘솔이나 화면에 그대로 출력하지 않아요.
            if (controller.current === current && (!current.signal.aborted || current.signal.reason === "timeout")) setView({ status: "error", data: null, message: current.signal.reason === "timeout" ? "검색 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요." : "공고를 불러오지 못했어요. 잠시 후 다시 시도해 주세요." }); // 서버 설정 용어 대신 사용자가 취할 수 있는 다음 행동을 알려줘요.
        } finally { window.clearTimeout(timeout); } // 완료되거나 취소되면 시간 제한 예약을 해제해요.
    } // 검색 요청 처리를 마쳐요.
    function submit(event: FormEvent<HTMLFormElement>) { // Enter나 검색 버튼 제출을 처리해요.
        event.preventDefault(); void runSearch(query, subject); // 검색어를 프론트 URL과 방문 기록에 남기지 않아요.
    } // 제출 처리를 마쳐요.
    function reset() { // 요청과 입력·결과를 함께 초기화해요.
        controller.current?.abort(); controller.current = null; setQuery(""); setSubject("all"); setLastRequest({ query: "", subject: "all" }); setView({ status: "idle", data: null, message: "" }); // 늦은 응답이 초기화를 되돌리지 못하게 해요.
    } // 초기화 처리를 마쳐요.
    return ( // 기존 검색 디자인 안에 실제 데이터를 연결해요.
        <><SiteHeader active="search" /><main id="main-content" className="search-page"> {/* 공개 검색은 로그인 없이 사용할 수 있어요. */}
            <section className="search-hero"><div className="container"> {/* 검색 입력 영역이에요. */}
                <Link href="/" className="search-breadcrumb">홈 <Icon name="chevron-right" /> 공고 검색</Link><p className="eyebrow">공개 공고 검색</p><h1>지금 필요한 제도,<br />직접 찾아보세요<span>.</span></h1><p className="search-hero-description">나와 부모님에게 관련된 공고를 검색하고 공식 원문을 확인해 보세요.</p> {/* 소개에서 시연 문구를 제거해요. */}
                <form className="search-form" onSubmit={submit} role="search"><Icon name="search" /><label className="search-sr-only" htmlFor="policy-search">정책명 또는 관심 분야</label><input id="policy-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={100} autoComplete="off" placeholder="정책명이나 관심 분야를 입력해 주세요" /><button type="submit" className="button button-primary">검색</button></form> {/* 검색 중에도 새 검색으로 이전 요청을 대체할 수 있어요. */}
                <div className="search-suggestions"><span>추천 검색어</span>{["버팀목", "신혼 특공", "기초연금"].map((keyword) => <button type="button" key={keyword} onClick={() => { setQuery(keyword); void runSearch(keyword, subject); }}>#{keyword}</button>)}</div> {/* 추천어도 실제 검색 API를 호출해요. */}
            </div></section> {/* 검색 입력 영역을 마쳐요. */}
            <section className="container search-results" aria-busy={view.status === "loading"}> {/* 요청 진행 상태를 보조기기에 전달해요. */}
                <div className="search-notice"><Icon name="file" /><p><strong>로그인 없이 공개 공고를 검색합니다.</strong> 검색어는 검색 처리를 위해 API로 전송하며 화면 저장소에는 저장하지 않습니다. 개인화 배지가 없으면 자격을 판정한 결과가 아닙니다.</p></div> {/* 실제 네트워크 동작을 정확히 설명해요. */}
                <div className="search-results-toolbar"><fieldset className="search-subject"><legend>검색 대상 · 검색 시 적용</legend><div className="search-category-list">{subjects.map((item) => <button key={item.value} type="button" className={subject === item.value ? "is-active" : ""} aria-pressed={subject === item.value} onClick={() => setSubject(item.value)}>{item.label}</button>)}</div></fieldset><button className="search-reset" type="button" onClick={reset}><Icon name="refresh" />초기화</button></div> {/* API에 없는 분야 필터 대신 대상 필터를 사용해요. */}
                <div className="search-result-heading" role="status"><p>{view.status === "idle" ? "검색어를 입력해 주세요." : view.status === "loading" ? "공고를 검색하고 있습니다." : view.status === "ready" ? `‘${view.data.q}’ · ${subjects.find((item) => item.value === lastRequest.subject)?.label} · 검색 결과 ${view.data.results.length}개 (최대 20개)` : "검색에 실패했습니다."}</p></div> {/* 결과 개수는 서버가 반환한 목록 기준이에요. */}
                {view.status === "error" && <div className="search-empty" role="alert"><h2>검색을 완료하지 못했습니다</h2><p>{view.message}</p>{lastRequest.query && <button type="button" className="button button-secondary" onClick={() => { setQuery(lastRequest.query); setSubject(lastRequest.subject); void runSearch(lastRequest.query, lastRequest.subject); }}>다시 시도</button>}</div>} {/* 이전 조건으로 명시적으로 재시도할 수 있어요. */}
                {view.status === "ready" && view.data.results.length === 0 && <div className="search-empty"><h2>검색 결과가 없습니다</h2><p>다른 검색어나 검색 대상을 선택해 다시 검색해 주세요.</p></div>} {/* 통신 실패와 빈 목록을 구분해요. */}
                {view.status === "ready" && <div className="search-policy-grid">{view.data.results.map((hit) => <PolicyCard key={hit.service_id} hit={hit} judge={view.data.judge} />)}</div>} {/* 로컬 샘플 대신 API 결과만 표시해요. */}
                <aside className="search-bottom-cta"><div><h2>나의 다음 단계도 살펴보세요</h2><p>내 정보를 입력하고 지금과 다음 생활에 맞는 제도를 살펴보세요.</p></div><Link href="/my" className="button button-secondary">내 징검다리 보기<Icon name="arrow-right" /></Link></aside> {/* 실제 프로필로 연결되는 버튼의 목적을 정확하게 안내해요. */}
            </section> {/* 결과 영역을 마쳐요. */}
        </main><SiteFooter /></> // 공통 하단을 유지해요.
    ); // 화면 반환을 마쳐요.
} // 실제 공개 검색 페이지를 마쳐요.
