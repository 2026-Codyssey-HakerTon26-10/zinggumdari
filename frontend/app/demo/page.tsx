"use client"; // 버튼으로 가상 프로필과 결과 상태를 바꾸는 화면이에요.
import Link from "next/link"; // 기존 화면으로 돌아가는 링크를 사용해요.
import { useRef, useState } from "react"; // 요청 순서와 화면 상태를 관리해요.
import { SiteFooter, SiteHeader } from "../components/ui"; // 기존 서비스의 공통 머리말과 꼬리말이에요.
import { demoProfile, demoNotice, demoStages, loadDemoRecommendation, type DemoStage, type DemoResult, type DemoCard } from "./demo-data"; // 가상 데이터와 API 응답 모양을 가져와요.
import { DemoTimeline } from "./demo-timeline"; // 추천 응답의 다음 단계와 비교표를 보여줘요.
import { DemoSearch } from "./demo-search"; // 시연 경로의 정책명 검색과 배지 예시를 연결해요.
import { DemoEvidence } from "./demo-evidence"; // 각 조건에서 근거 ID로 연결한 텍스트 줄을 펼쳐요.
import { DemoIngest } from "./demo-ingest"; // 가상 공고 재생 결과를 추천 카드에 합류시켜요.
import { DemoParent } from "./demo-parent"; // 본인과 분리된 부모님 동의와 가상 결과를 보여줘요.
import "./demo.css"; // 흰색 바탕의 시연 화면 스타일을 적용해요.
type View = { status: "idle" | "loading" | "error"; result: null } | { status: "ready"; result: DemoResult }; // 결과가 없을 때와 준비됐을 때를 구분해요.
export default function DemoPage() { // 실제 계정과 분리된 가상 사례 화면이에요.
    const [view, setView] = useState<View>({ status: "idle", result: null }); // 선택 전에는 추천 결과를 표시하지 않아요.
    const [stage, setStage] = useState<DemoStage>("marriage_planned"); // 원래 가상 사례는 예비부부 단계예요.
    const requestId = useRef(0); // 초기화 뒤 늦게 도착한 응답을 무시하기 위한 번호예요.
    async function selectProfile(nextStage: DemoStage = "marriage_planned") { // 사용자가 직접 선택했을 때만 가상 결과를 불러와요.
        setStage(nextStage); // 요청한 가정과 결과를 같은 단계로 맞춰요.
        const current = ++requestId.current; // 이번 요청 번호를 기억해요.
        setView({ status: "loading", result: null }); // 이전 카드를 지우고 불러오는 상태를 알리죠.
        try { // 데이터 연결이 실패해도 다시 시도할 수 있게 처리해요.
            const result = await loadDemoRecommendation(nextStage); // 현재는 고정 예시이며 실제 판정 요청은 보내지 않아요.
            if (current === requestId.current) setView({ status: "ready", result }); // 가장 최근 선택의 결과만 보여줘요.
        } catch { // 오류 내용이나 개인정보를 화면과 로그에 노출하지 않아요.
            if (current === requestId.current) setView({ status: "error", result: null }); // 재시도 안내로 바꿔요.
        } // 데이터 처리를 마쳐요.
    } // 선택 처리를 마쳐요.
    function addReplayCard(card: DemoCard) { // 같은 가상 공고를 여러 번 재생해도 중복 카드가 생기지 않게 해요.
        setView((current) => current.status === "ready" ? { status: "ready", result: { ...current.result, cards: [...current.result.cards.filter((entry) => entry.rule_id !== card.rule_id), card] } } : current); // 현재 가상 결과만 바꾸고 실제 프로필은 저장하지 않아요.
    } // 재생 카드 합류를 마쳐요.
    function reset() { // 실제 계정에 영향을 주지 않고 이 화면만 초기화해요.
        setStage("marriage_planned"); // 초기화하면 원래 가상 프로필의 단계로 돌아가요.
        requestId.current += 1; // 진행 중인 요청이 결과를 덮어쓰지 못하게 해요.
        setView({ status: "idle", result: null }); // 가상 프로필 선택 전 상태로 돌아가요.
    } // 초기화를 마쳐요.
    return ( // 화면 구조를 그려요.
        <div> {/* 공통 메뉴와 시연 본문을 묶어요. */}
            <SiteHeader active="my" /> {/* 기존 내 징검다리 메뉴를 사용해요. */}
            <main id="main-content" className="container demo-main"> {/* 건너뛰기 링크가 이동할 본문이에요. */}
                <Link href="/my">← 내 징검다리로 돌아가기</Link> {/* 기존 디자인 화면으로 돌아가요. */}
                <header className="demo-heading"><p>가상 사례 체험</p><h1>지원 님의 첫 징검다리</h1><p>가상의 프로필로 추천 화면을 살펴보세요. 실제 계정 정보는 읽거나 변경하지 않습니다.</p></header> {/* 체험과 실제 계정을 구분해요. */}
                <section className="demo-panel" aria-labelledby="demo-profile-title"> {/* 가상 프로필 선택 영역이에요. */}
                    <h2 id="demo-profile-title">시연 프로필</h2> {/* 선택 영역의 제목이에요. */}
                    <p>{demoProfile.self.nickname} · {demoProfile.self.birth_year}년생 · {demoProfile.self.sido} {demoProfile.self.sigungu} · {demoProfile.self.marital_status}</p> {/* 가상 정보만 보여줘요. */}
                    <p>소득·자산 정보 미입력 · 부모님 정보 없음</p> {/* 판정에 필요한 빈 정보를 밝혀요. */}
                    <div className="demo-actions"> {/* 프로필 선택과 초기화 버튼을 묶어요. */}
                        <button type="button" className="button button-primary" onClick={() => selectProfile()} disabled={view.status === "loading"}>{view.status === "loading" ? "불러오는 중…" : view.status === "ready" ? "가상 사례 다시 불러오기" : "가상 프로필로 시작하기"}</button> {/* 같은 프로필을 다시 선택할 수도 있어요. */}
                        <button type="button" className="button button-secondary" onClick={reset}>체험 초기화</button> {/* 진행 중에도 안전하게 선택을 취소해요. */}
                    </div> {/* 버튼 영역을 마쳐요. */}
                </section> {/* 프로필 영역을 마쳐요. */}
                {view.status !== "idle" && <section className="demo-panel" aria-labelledby="demo-stage-title"> {/* 가상 사례를 선택한 뒤에만 모의 단계 버튼을 보여줘요. */}
                    <h2 id="demo-stage-title">생애 단계 넘기기</h2> {/* 실제 프로필 편집과 구분되는 제목이에요. */}
                    <p>가정한 단계의 고정 예시를 보여드립니다. 실제 엔진 재판정이나 프로필 저장은 하지 않습니다.</p> {/* 단계별 화면 예시임을 명확하게 밝혀요. */}
                    <div className="demo-actions" role="group" aria-label="가정할 생애 단계">{demoStages.map((item) => <button type="button" key={item.id} className="button button-secondary" aria-pressed={stage === item.id} disabled={view.status === "loading"} onClick={() => selectProfile(item.id)}>{item.label}</button>)}</div> {/* 각 단계로 직접 이동하고 현재 선택을 알려줘요. */}
                    <p role="status">현재 가정: {demoStages.find((item) => item.id === stage)?.assumption}</p> {/* 어떤 정보가 바뀌었다고 가정했는지 설명해요. */}
                    <div className="demo-actions"><button type="button" className="button button-primary" disabled={view.status === "loading" || stage === "multi_child"} onClick={() => selectProfile(demoStages[demoStages.findIndex((item) => item.id === stage) + 1].id)}>다음 단계 보기</button><button type="button" className="button button-secondary" disabled={view.status === "loading"} onClick={() => selectProfile()}>원래 가상 프로필로 돌아가기</button></div> {/* 마지막 단계에서는 다음 버튼을 막고 원래 사례로 돌아갈 수 있게 해요. */}
                </section>} {/* 단계 선택 영역을 마쳐요. */}
                <section className="demo-results" aria-labelledby="demo-result-title" aria-busy={view.status === "loading"}> {/* 결과를 불러오는 상태를 보조기기에 알려줘요. */}
                    <h2 id="demo-result-title">추천 카드 살펴보기</h2> {/* 실제 개인화 결과가 아닌 체험 제목이에요. */}
                    <p className="demo-notice">API 문서의 예시 데이터입니다. 실제 자격 판정·최신 공고 조회 결과가 아닙니다.</p> {/* 샘플임을 항상 표시해요. */}
                    <p role="status">{view.status === "idle" ? "위에서 가상 프로필을 선택해 주세요." : view.status === "loading" ? "가상 사례를 불러오고 있습니다." : view.status === "ready" ? `${view.result.cards.length}개의 예시 카드를 불러왔습니다.` : ""}</p> {/* 상태 변화를 읽어줘요. */}
                    {view.status === "error" && <div role="alert"><p>카드를 불러오지 못했습니다. 다시 시도해 주세요.</p><button type="button" className="button button-secondary" onClick={() => selectProfile(stage)}>다시 시도</button></div>} {/* 실패 시 선택 내용을 노출하지 않고 재시도해요. */}
                    {view.status === "ready" && view.result.cards.length === 0 && <p>이 단계에 연결된 카드 예시가 없습니다. 실제 지원 제도가 없다는 뜻은 아닙니다.</p>} {/* 빈 응답도 안전하게 표시해요. */}
                    {view.status === "ready" && view.result.cards.map((card) => ( // API 응답 순서대로 카드를 표시해요.
                        <article className="demo-panel demo-card" key={card.rule_id}> {/* 제도 ID를 안정된 목록 키로 사용해요. */}
                            <p className="demo-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 카드 맨 위에 필수 고지를 표시해요. */}
                            <span className="demo-verdict">확인 필요 · 화면 예시</span><h3>{card.name}</h3> {/* 신청 가능이라고 단정하지 않아요. */}
                            <ul>{card.conditions.map((condition) => <li key={condition.read_as}><DemoEvidence condition={condition} notice={demoNotice} /></li>)}</ul> {/* 상태를 색뿐 아니라 글자로도 표시해요. */}
                            <p>예시 데이터 기준일: <time dateTime={card.updated}>{card.updated}</time></p> {/* 실제 최신 공고 기준일과 구분해요. */}
                            {card.detail_url ? <a href={card.detail_url} target="_blank" rel="noopener noreferrer">공식 원문 보기</a> : <p>공식 공고 원문 미연결 · 자격 조건은 원문 연결 후 확인해 주세요.</p>} {/* 없는 원문 주소를 지어내지 않아요. */}
                        </article> // 한 장의 카드를 마쳐요.
                    ))} {/* 카드 목록을 마쳐요. */}
                </section> {/* 결과 영역을 마쳐요. */}
                {view.status === "ready" && <DemoTimeline key={view.result.user_id} steps={view.result.timeline.self} activeStep={stage} />} {/* 선택된 가상 사례에만 타임라인을 표시해요. */}
                {view.status === "ready" && <DemoSearch />} {/* 프로필 초기화 시 검색어와 결과도 함께 사라져요. */}
                {view.status === "ready" && <DemoIngest onAdd={addReplayCard} />} {/* 실제 업로드 대신 고정 가상 결과의 화면 흐름을 체험해요. */}
                {view.status === "ready" && <DemoParent />} {/* 프로필 재선택과 단계 변경 때 부모님 동의도 초기화해요. */}
            </main> {/* 본문을 마쳐요. */}
            <SiteFooter /> {/* 공공기관이 운영하는 서비스가 아니라는 기존 고지를 보여줘요. */}
        </div> // 전체 화면을 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 시연 페이지를 마쳐요.
