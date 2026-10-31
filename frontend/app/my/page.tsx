"use client"; // 버튼과 탭을 누를 때 현재 화면의 상태를 바꿔요.
import Link from "next/link"; // 페이지를 새로 불러오지 않고 다른 화면으로 이동해요.
import { useEffect, useRef, useState } from "react"; // 화면 상태와 대화상자 참조를 관리해요.
import { Icon, SiteFooter, SiteHeader } from "../components/ui"; // 모든 화면이 공유하는 아이콘과 머리말을 가져와요.
import "./my.css"; // 내 징검다리 화면에만 쓰는 디자인을 불러와요.
type Subject = "self" | "parent"; // 본인과 부모님 화면을 구분해요.
type Stage = "youth" | "newlywed" | "birth" | "childcare" | "multi"; // 다섯 가지 생애 단계의 이름을 정해요.
type Policy = { id: string; title: string; category: string; icon: string; description: string; checks: string[] }; // 정책 미리보기에서 보여줄 정보의 모양을 정해요.
const stages: { id: Stage; title: string; subtitle: string; icon: string }[] = [ // 타임라인에 표시할 다섯 단계를 준비해요.
    { id: "youth", title: "청년", subtitle: "첫 독립을 준비할 때", icon: "user" }, // 첫 번째 단계예요.
    { id: "newlywed", title: "신혼", subtitle: "함께 시작할 때", icon: "heart" }, // 두 번째 단계예요.
    { id: "birth", title: "출산", subtitle: "새 가족을 맞이할 때", icon: "sparkles" }, // 세 번째 단계예요.
    { id: "childcare", title: "육아", subtitle: "아이와 자라갈 때", icon: "family" }, // 네 번째 단계예요.
    { id: "multi", title: "다자녀", subtitle: "가족이 더 커질 때", icon: "home" }, // 다섯 번째 단계예요.
]; // 단계 목록을 마쳐요.
const catalog: Record<Stage, Policy[]> = { // 단계에 따라 화면에 보여줄 예시 제도를 묶어요.
    youth: [ // 청년 단계의 제도 이름을 준비해요.
        { id: "youth-housing", title: "청년전용 버팀목 전세자금", category: "주거 · 기금 제도", icon: "home", description: "첫 독립을 준비한다면, 주거 지원 조건을 먼저 살펴보세요.", checks: ["소득·자산 기준 확인", "주택·세대주 조건 확인", "해당 공고의 기준일 확인"] }, // 자격이나 금액은 단정하지 않아요.
        { id: "youth-notice", title: "청년 주거 지원 공고", category: "청년 · 공고 예시", icon: "file", description: "내 지역의 청년 지원 공고를 한곳에서 살펴보는 자리예요.", checks: ["거주 지역 확인", "공고별 신청 조건 확인", "공고 원문 연결 필요"] }, // 실제 공고가 연결되기 전에는 예시로 표시해요.
    ], // 청년 단계 예시를 마쳐요.
    newlywed: [ // 신혼 단계의 제도 이름을 준비해요.
        { id: "newlywed-housing", title: "신혼부부전용 전세자금", category: "주거 · 기금 제도", icon: "home", description: "둘이 함께할 집을 준비하며 확인할 수 있는 기금 제도예요.", checks: ["혼인 정보 확인", "부부합산 소득·자산 확인", "주택·세대주 조건 확인"] }, // 실제 대출 자격과 상품 정보는 제공하지 않아요.
        { id: "newlywed-notice", title: "신혼부부 주거 지원 공고", category: "신혼 · 공고 예시", icon: "heart", description: "혼인 여부와 지역에 따라 달라지는 공고를 살펴보세요.", checks: ["혼인 상태 확인", "거주 지역 확인", "공고 원문 연결 필요"] }, // 당첨 가능성이나 신청 가능 여부를 단정하지 않아요.
    ], // 신혼 단계 예시를 마쳐요.
    birth: [ // 출산 단계에서는 일반적인 공고 분류만 보여줘요.
        { id: "birth-notice", title: "출산 단계 지원 공고", category: "출산 · 공고 예시", icon: "sparkles", description: "새 가족을 맞이할 때 확인할 제도를 모아보는 자리예요.", checks: ["출산 관련 조건 확인", "거주 지역 확인", "공고 원문 연결 필요"] }, // 민감정보는 입력받거나 저장하지 않아요.
        { id: "birth-housing", title: "신생아 특례 버팀목", category: "주거 · 기금 제도", icon: "home", description: "출산 후 달라지는 주거 지원 조건을 확인해 보세요.", checks: ["출산 관련 조건 확인", "소득·자산 기준 확인", "해당 공고의 기준일 확인"] }, // 금리와 금융사 상품 및 신청 링크는 넣지 않아요.
    ], // 출산 단계 예시를 마쳐요.
    childcare: [ // 육아 단계의 공고 분류를 준비해요.
        { id: "childcare-notice", title: "육아 단계 지원 공고", category: "육아 · 공고 예시", icon: "family", description: "아이와 함께하는 일상에 필요한 지원 공고를 살펴보세요.", checks: ["자녀 관련 조건 확인", "가구 정보 확인", "공고 원문 연결 필요"] }, // 확인되지 않은 혜택이나 지원액은 쓰지 않아요.
        { id: "childcare-local", title: "우리 지역 양육 지원 공고", category: "지역 · 공고 예시", icon: "home", description: "사는 지역에서 안내하는 양육 지원을 확인하는 자리예요.", checks: ["거주 지역 확인", "자녀 관련 조건 확인", "공고 원문 연결 필요"] }, // 지역 조건도 아직 판정하지 않아요.
    ], // 육아 단계 예시를 마쳐요.
    multi: [ // 다자녀 단계의 공고 분류를 준비해요.
        { id: "multi-housing", title: "다자녀 주거 지원 공고", category: "주거 · 공고 예시", icon: "home", description: "가족 구성에 따라 달라지는 주거 지원 조건을 살펴보세요.", checks: ["자녀 수와 가구 정보 확인", "주택 관련 조건 확인", "공고 원문 연결 필요"] }, // 공고마다 다른 자녀 수 기준을 임의로 정하지 않아요.
        { id: "multi-local", title: "다자녀 가구 지원 공고", category: "가족 · 공고 예시", icon: "family", description: "커지는 가족에게 열릴 제도를 함께 살펴보는 자리예요.", checks: ["자녀 관련 조건 확인", "거주 지역 확인", "공고 원문 연결 필요"] }, // 실제 원문이 연결되기 전까지 확인 필요로 표시해요.
    ], // 다자녀 단계 예시를 마쳐요.
}; // 단계별 정책 목록을 마쳐요.
const parentPolicies: Policy[] = [ // 부모님 예시는 본인 예시와 별도로 준비해요.
    { id: "parent-pension", title: "기초연금", category: "부모님 · 생활 지원", icon: "heart", description: "부모님의 연령과 소득인정액 등 공식 조건을 확인하는 자리예요.", checks: ["연령 조건 확인", "소득인정액 확인 · 재산 환산 필요", "공고 원문 연결 필요"] }, // 기초연금은 재산 환산이 필요하므로 항상 확인 필요예요.
    { id: "parent-care", title: "부모님 돌봄 관련 제도", category: "부모님 · 돌봄", icon: "family", description: "공식 판정 결과와 돌봄 필요에 따라 관련 제도를 살펴보세요.", checks: ["부모님 정보 확인", "공식 판정 결과 확인", "공고 원문 연결 필요"] }, // 건강 관련 정보를 저장하지 않아요.
]; // 부모님 정책 예시를 마쳐요.
const disclaimer = "참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정"; // 모든 예시 카드에 같은 모의 판정 안내를 붙여요.
export default function MyPage() { // 내 징검다리 화면을 만들어요.
    const [subject, setSubject] = useState<Subject>("self"); // 처음에는 본인 탭을 보여줘요.
    const [stage, setStage] = useState<Stage>("youth"); // 처음에는 청년 단계를 보여줘요.
    const [filter, setFilter] = useState("all"); // 전체 보기와 저장한 예시를 구분해요.
    const [bookmarks, setBookmarks] = useState<string[]>([]); // 저장 버튼 상태를 현재 화면에서만 기억해요.
    const [selected, setSelected] = useState<Policy | null>(null); // 자세히 살펴볼 예시 카드를 기억해요.
    const [nickname, setNickname] = useState("민지"); // 실제 개인정보 대신 가상의 닉네임을 보여줘요.
    const [draftNickname, setDraftNickname] = useState("민지"); // 닉네임 편집 중인 값을 별도로 기억해요.
    const [alertSettings, setAlertSettings] = useState([true, true, false]); // 알림 스위치의 시연 상태를 기억해요.
    const [toast, setToast] = useState(""); // 버튼을 눌렀을 때 짧은 안내를 보여줘요.
    const detailDialog = useRef<HTMLDialogElement>(null); // 정책 미리보기 대화상자를 가리켜요.
    const profileDialog = useRef<HTMLDialogElement>(null); // 닉네임 편집 대화상자를 가리켜요.
    const stageIndex = stages.findIndex((item) => item.id === stage); // 선택한 단계의 순서를 찾아요.
    const cards = subject === "parent" ? parentPolicies : catalog[stage]; // 본인과 부모님의 예시를 분리해서 보여줘요.
    const shownCards = filter === "saved" ? cards.filter((card) => bookmarks.includes(card.id)) : cards; // 저장 필터를 누르면 저장한 예시만 보여줘요.
    useEffect(() => { // 부모님 바로가기 주소에서 들어왔는지 확인해요.
        if (new URLSearchParams(window.location.search).get("subject") === "parent") setSubject("parent"); // 부모님 바로가기라면 부모님 탭을 열어요.
    }, []); // 화면을 처음 열 때만 주소를 읽어요.
    useEffect(() => { // 짧은 안내가 표시되면 자동으로 지워요.
        if (!toast) return; // 보여줄 안내가 없다면 아무 일도 하지 않아요.
        const timer = window.setTimeout(() => setToast(""), 3500); // 잠시 뒤 안내를 닫아요.
        return () => window.clearTimeout(timer); // 화면을 떠나거나 안내가 바뀌면 예약을 취소해요.
    }, [toast]); // 안내 문구가 바뀔 때만 실행해요.
    function toggleBookmark(id: string) { // 카드의 저장 상태를 바꿔요.
        setBookmarks((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); // 이미 저장했다면 빼고 아니라면 추가해요.
        setToast("이 화면에서만 저장 상태를 유지해요. 실제 보관함에는 저장되지 않아요."); // 시연 버튼이 실제 저장과 다름을 알려줘요.
    } // 저장 처리 함수를 마쳐요.
    function showPolicy(card: Policy) { // 선택한 정책 예시의 확인 항목을 열어요.
        setSelected(card); // 대화상자에 보여줄 예시를 선택해요.
        detailDialog.current?.showModal(); // 키보드로도 닫을 수 있는 기본 대화상자를 열어요.
    } // 정책 미리보기 함수를 마쳐요.
    return ( // 화면 구조를 그리기 시작해요.
        <div className="my-page"> {/* 마이페이지 전체 영역이에요. */}
            <SiteHeader active="my" /> {/* 내 징검다리가 선택된 공통 메뉴를 보여줘요. */}
            <main id="main-content" className="container my-main"> {/* 건너뛰기 링크가 이동할 본문이에요. */}
                <div className="my-breadcrumb"><Link href="/">홈</Link><Icon name="chevron-right" /><span>내 징검다리</span></div> {/* 현재 위치를 안내해요. */}
                <section className="my-heading"> {/* 페이지 제목과 시연 안내를 묶어요. */}
                    <div><p className="eyebrow">MY STEPPING STONES</p><h1>{nickname} 님의 다음 걸음,<br className="my-mobile-break" /> 미리 준비해 볼까요?</h1><p className="muted">지금 필요한 제도부터 다음 단계에서 열릴 제도까지 함께 살펴봐요.</p></div> {/* 닉네임과 안내 문장을 보여줘요. */}
                    <span className="my-demo-label"><span />시연용 가상 사례</span> {/* 실제 개인의 판정 결과가 아님을 표시해요. */}
                </section> {/* 제목 영역을 마쳐요. */}
                <section className="my-profile" aria-label="시연 프로필 요약"> {/* 참고 디자인의 프로필 요약 구성을 보여줘요. */}
                    <div className="my-avatar"><Icon name="user" /></div> {/* 실명이나 사진 대신 기본 아이콘을 사용해요. */}
                    <div className="my-profile-info"><div><strong>{nickname} 님</strong><span>가상 닉네임</span></div><p>프로필과 공고가 연결되면 내 조건에 맞는 정보를 보여드려요.</p><div className="my-profile-tags"><span>청년</span><span>주거 관심</span><span>소득 정보 미입력</span></div></div> {/* 민감정보 없이 예시 프로필 상태를 보여줘요. */}
                    <button className="button button-secondary" type="button" onClick={() => { setDraftNickname(nickname); profileDialog.current?.showModal(); }}><Icon name="settings" />닉네임 바꾸기</button> {/* 현재 화면의 가상 닉네임만 바꿀 수 있어요. */}
                </section> {/* 프로필 요약 영역을 마쳐요. */}
                <div className="my-subject-tabs" role="tablist" aria-label="추천 대상"> {/* 본인과 부모님 정보를 명확히 구분해요. */}
                    <button role="tab" type="button" id="my-tab-self" aria-controls="my-subject-panel" aria-selected={subject === "self"} onClick={() => { setSubject("self"); setFilter("all"); }}><Icon name="user" />나의 징검다리</button> {/* 본인 예시로 이동해요. */}
                    <button role="tab" type="button" id="my-tab-parent" aria-controls="my-subject-panel" aria-selected={subject === "parent"} onClick={() => { setSubject("parent"); setFilter("all"); }}><Icon name="family" />부모님 챙김<span>함께</span></button> {/* 부모님 예시로 이동해요. */}
                </div> {/* 대상 선택 영역을 마쳐요. */}
                <div id="my-subject-panel" role="tabpanel" aria-labelledby={subject === "self" ? "my-tab-self" : "my-tab-parent"}> {/* 선택한 대상의 화면을 묶어요. */}
                    {subject === "self" ? <section className="my-journey"><div className="my-section-top"><div><p className="eyebrow">한 걸음 앞서 살펴보는</p><h2>나의 생애주기 타임라인</h2></div><span className="my-assumption-badge"><Icon name="sparkles" />단계를 가정한 화면 미리보기</span></div><div className="my-stage-track" aria-label="생애 단계 선택">{stages.map((item, index) => <button className={`my-stage ${stage === item.id ? "is-current" : ""} ${index < stageIndex ? "is-past" : ""}`} key={item.id} type="button" aria-pressed={stage === item.id} onClick={() => { setStage(item.id); setFilter("all"); }}><span className="my-stage-node"><Icon name={item.icon} /></span><strong>{item.title}</strong><small>{item.subtitle}</small>{stage === item.id && <span className="my-stage-current">살펴보는 단계</span>}</button>)}</div><div className="my-stage-bottom"><span><Icon name="file" />단계 선택은 실제 프로필을 변경하거나 자격을 판정하지 않아요.</span><button type="button" disabled={stageIndex === stages.length - 1} onClick={() => { setStage(stages[stageIndex + 1].id); setFilter("all"); }}>다음 단계 보기<Icon name="arrow-right" /></button></div></section> : <section className="my-parent-banner"><span className="my-parent-icon"><Icon name="family" /></span><div><p className="eyebrow">PARENTS, TOGETHER</p><h2>부모님에게 필요한 제도도 함께 살펴봐요.</h2><p>본인 조건과 구분해 확인해요. 부모님 정보는 별도 동의 후 필요한 항목만 받도록 준비하고 있어요.</p></div></section>} {/* 본인은 다섯 단계, 부모님은 별도 안내를 보여줘요. */}
                    <div className="my-dashboard-grid"> {/* 추천 영역과 옆 안내 영역을 배치해요. */}
                        <section className="my-policies" aria-labelledby="my-policies-title"> {/* 제도 미리보기 목록이에요. */}
                            <div className="my-section-top"><div><p className="eyebrow">{subject === "self" ? `${stages[stageIndex].title} 단계에서 살펴볼` : "부모님과 함께 살펴볼"}</p><h2 id="my-policies-title">이런 제도가 있어요<span className="my-count">{cards.length}</span></h2></div><Icon name="sparkles" /></div> {/* 현재 선택한 단계의 제목을 보여줘요. */}
                            <div className="my-policy-filters" aria-label="정책 필터"><button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>전체 보기</button><button type="button" aria-pressed={filter === "needs_check"} onClick={() => setFilter("needs_check")}>확인 필요<span>{cards.length}</span></button><button type="button" aria-pressed={filter === "saved"} onClick={() => setFilter("saved")}><Icon name="bookmark" />저장한 예시<span>{cards.filter((card) => bookmarks.includes(card.id)).length}</span></button></div> {/* 전체와 확인 필요 및 저장 보기를 전환해요. */}
                            <div className="my-policy-list"> {/* 정책 예시 카드를 세로로 나열해요. */}
                                {shownCards.map((card) => <article className="my-policy-card" key={card.id}><p className="my-card-disclaimer">{disclaimer}</p><div className="my-card-body"><div className="my-card-top"><span className="my-card-icon"><Icon name={card.icon} /></span><span className="my-status">확인 필요</span><button className={`my-bookmark ${bookmarks.includes(card.id) ? "is-saved" : ""}`} type="button" aria-label={`${card.title} ${bookmarks.includes(card.id) ? "저장 해제" : "저장"}`} aria-pressed={bookmarks.includes(card.id)} onClick={() => toggleBookmark(card.id)}><Icon name="bookmark" /></button></div><p className="my-card-category">{card.category}</p><h3>{card.title}</h3><p className="my-card-description">{card.description}</p><div className="my-check-line"><Icon name="plus" /><span>{card.checks[0]}</span><span>확인 필요</span></div><div className="my-card-bottom"><span>시연용 예시 · 원문·기준일 연결 전</span><button type="button" onClick={() => showPolicy(card)}>확인할 항목<Icon name="arrow-right" /></button></div></div></article>)} {/* 실제 자격 판정 없이 예시와 확인할 항목만 보여줘요. */}
                                {shownCards.length === 0 && <div className="my-empty"><Icon name="bookmark" /><h3>아직 저장한 예시가 없어요.</h3><p>카드의 책갈피를 눌러 현재 화면에서 모아보세요.</p><button className="button button-secondary" type="button" onClick={() => setFilter("all")}>전체 예시 보기</button></div>} {/* 저장한 카드가 없을 때 안내해요. */}
                            </div> {/* 정책 카드 목록을 마쳐요. */}
                            <p className="my-data-note"><Icon name="file" />현재는 디자인 미리보기예요. 원문과 규칙 엔진 연결 후 실제 조건을 확인할 수 있어요.</p> {/* 시연 상태의 한계를 표시해요. */}
                        </section> {/* 정책 목록 영역을 마쳐요. */}
                        <aside className="my-sidebar" aria-label="추천 관련 안내"> {/* 추천 다음에 필요한 안내를 모아요. */}
                            <section className="my-next-card"><span className="my-next-icon"><Icon name="sparkles" /></span><p className="eyebrow">조금 더 정확한 추천을 위해</p><h2>모르는 조건은,<br />확인 필요로 남겨둘게요.</h2><p>소득을 몰라도 괜찮아요. 입력하지 않은 정보만으로 지원 가능 여부를 단정하지 않아요.</p><div className="my-legend"><span><i className="my-dot-green" />확정</span><span><i className="my-dot-amber" />확인 필요</span><span><i className="my-dot-gray" />질문</span></div></section> {/* 세 가지 상태를 이해하기 쉽게 설명해요. */}
                            <section className="my-alert-card"><div className="my-aside-title"><Icon name="bell" /><h2>알림 설정 미리보기</h2></div><p>필요한 소식만 골라 받을 수 있어요.</p>{["새로운 맞춤 공고", "신청 기한 안내", "부모님 관련 소식"].map((label, index) => <label className="my-toggle-row" key={label}><span>{label}</span><input type="checkbox" checked={alertSettings[index]} onChange={() => setAlertSettings((current) => current.map((value, itemIndex) => itemIndex === index ? !value : value))} /><span className="my-switch" aria-hidden="true" /></label>)}<small>스위치는 이 화면에서만 바뀌며 실제 알림은 발송되지 않아요.</small></section> {/* 실제 전송이나 개인정보 저장 없이 스위치를 체험해요. */}
                            <div className="my-privacy-note"><Icon name="shield" /><p>개인정보를 입력하지 않아도<br />가상 사례로 흐름을 둘러볼 수 있어요.</p></div> {/* 실제 개인정보 입력이 필요 없음을 알려줘요. */}
                        </aside> {/* 옆 안내 영역을 마쳐요. */}
                    </div> {/* 대시보드 배치를 마쳐요. */}
                </div> {/* 대상별 화면을 마쳐요. */}
                <section className="my-archive"><div className="my-aside-title"><Icon name="file" /><h2>공고 원문과 근거도 한곳에</h2></div><p>제도별 조건을 어떤 원문에서 읽었는지 함께 보여드려요. 원문이 연결되면 해당 페이지와 기준일을 여기에서 확인할 수 있어요.</p><span>현재는 원문 연결 전이에요.</span></section> {/* 가짜 하이라이트 대신 원문 연동 전 상태를 설명해요. */}
            </main> {/* 본문을 마쳐요. */}
            <SiteFooter /> {/* 공통 바닥글을 보여줘요. */}
            <dialog className="my-dialog" ref={detailDialog} aria-labelledby="my-detail-title"><button className="my-dialog-close" type="button" aria-label="닫기" onClick={() => detailDialog.current?.close()}><Icon name="close" /></button><p className="eyebrow">시연용 예시 · 확인 항목</p><h2 id="my-detail-title">{selected?.title}</h2><p className="my-dialog-disclaimer">{disclaimer}</p><p>아래는 화면 구성을 보여주기 위한 확인 항목 예시예요. 실제 제도 조건은 원문 연결 후 확인해 주세요.</p><ul>{selected?.checks.map((check) => <li key={check}><Icon name="plus" /><span>{check}</span><em>확인 필요</em></li>)}</ul><p className="my-detail-source"><Icon name="file" />원문·기준일 연결 전 · 자격 판정 결과가 아니에요.</p><button className="button button-primary" type="button" onClick={() => detailDialog.current?.close()}>확인했어요</button></dialog> {/* 실제 자격을 단정하지 않는 정책 설명 대화상자예요. */}
            <dialog className="my-dialog" ref={profileDialog} aria-labelledby="my-profile-title"><button className="my-dialog-close" type="button" aria-label="닫기" onClick={() => profileDialog.current?.close()}><Icon name="close" /></button><p className="eyebrow">가상 프로필 미리보기</p><h2 id="my-profile-title">어떤 닉네임으로 불러드릴까요?</h2><p>실명 대신 가상 닉네임을 사용해 주세요. 입력한 값은 현재 화면에서만 사용하고 저장하거나 전송하지 않아요.</p><form onSubmit={(event) => { event.preventDefault(); setNickname(draftNickname.trim() || "민지"); profileDialog.current?.close(); setToast("가상 닉네임을 바꿨어요. 현재 화면에서만 유지돼요."); }}><label htmlFor="my-nickname">가상 닉네임</label><input id="my-nickname" autoComplete="off" value={draftNickname} maxLength={12} onChange={(event) => setDraftNickname(event.target.value)} /><button className="button button-primary" type="submit">화면에 적용하기</button></form></dialog> {/* 서버나 저장소에 접근하지 않는 닉네임 편집 대화상자예요. */}
            <div className={`my-toast ${toast ? "is-visible" : ""}`} role="status" aria-live="polite">{toast}</div> {/* 저장 및 편집 결과를 방해 없이 알려줘요. */}
        </div> // 마이페이지 전체 구성을 마쳐요.
    ); // 그린 화면을 반환해요.
} // 마이페이지 함수를 마쳐요.
