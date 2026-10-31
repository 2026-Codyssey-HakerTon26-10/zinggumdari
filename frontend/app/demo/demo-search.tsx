"use client"; // 검색 폼과 결과를 같은 화면에서 갱신해요.
import { useState, type FormEvent } from "react"; // 입력 중인 값과 제출한 검색어를 구분해요.
type SearchItem = { service_id: string; rule_id: string | null; name: string; subject: "self" | "parent"; badge: "needs_check" | "no_rule" | null; stage_tags: string[]; detail_url: string | null; updated: string | null }; // API 검색 결과의 필드 이름을 사용해요.
const items: SearchItem[] = [ // API 계약을 사용하는 고정 시연 응답이며 최신 공고 목록이 아니에요.
    { service_id: "demo:newlywed", rule_id: "manual:hug-newlywed-jeonse", name: "신혼부부전용 전세자금", subject: "self", badge: "needs_check", stage_tags: ["newlywed"], detail_url: null, updated: "2026-10-31" }, // 기존 추천 카드와 같은 예시 제도예요.
    { service_id: "demo:newborn", rule_id: "manual:hug-newborn-buttimok", name: "신생아 특례 버팀목", subject: "self", badge: "needs_check", stage_tags: ["child"], detail_url: null, updated: "2026-10-31" }, // 실제 자격을 계산하지 않으므로 확정 배지를 쓰지 않아요.
    { service_id: "demo:local", rule_id: null, name: "○○구 신혼부부 주거비 지원", subject: "self", badge: "no_rule", stage_tags: ["newlywed"], detail_url: null, updated: null }, // API 문서의 가상 지역 예시이며 조건표가 없어요.
]; // 예시 목록을 마쳐요.
function normalize(value: string) { // 띄어쓰기가 달라도 정책명을 찾을 수 있게 해요.
    return value.toLocaleLowerCase("ko-KR").replace(/\s+/g, ""); // 검색어는 메모리 안에서만 가공해요.
} // 검색어 정리를 마쳐요.
export function DemoSearch() { // 추천·단계 넘기기 다음에 사용할 시연 검색이에요.
    const [query, setQuery] = useState(""); // 아직 제출하지 않은 입력을 기억해요.
    const [submitted, setSubmitted] = useState<string | null>(null); // 최초 상태와 빈 결과를 구분해요.
    const [personalized, setPersonalized] = useState(true); // 실제 인증과 구분되는 배지 표시 예시를 선택해요.
    const [error, setError] = useState(""); // 빈 검색어 안내를 입력란에 연결해요.
    const results = submitted === null ? [] : items.filter((item) => normalize(item.name).includes(normalize(submitted))); // 규칙 판정 없이 이름만 검색해요.
    function search(event: FormEvent<HTMLFormElement>) { // 검색 버튼 또는 Enter를 처리해요.
        event.preventDefault(); // 검색어가 URL이나 서버로 전송되지 않게 해요.
        if (!query.trim()) { setError("정책명을 입력해 주세요."); return; } // 빈 검색어로 전체 결과가 나온 것처럼 표시하지 않아요.
        setError(""); // 유효한 검색어의 이전 오류를 지워요.
        setSubmitted(query.trim()); // 제출한 검색어와 결과를 함께 갱신해요.
    } // 검색 처리를 마쳐요.
    function reset() { // 결과와 검색 조건을 모두 초기화해요.
        setQuery(""); setSubmitted(null); setError(""); setPersonalized(true); // 화면 밖에는 아무 값도 저장하지 않아요.
    } // 초기화를 마쳐요.
    return ( // 검색 화면 조각을 그려요.
        <section className="demo-results" aria-labelledby="demo-search-title"> {/* 추천 화면 안에서 검색을 이어갈 수 있어요. */}
            <h2 id="demo-search-title">공고 검색 체험</h2> {/* 실제 검색 API와 구분되는 제목이에요. */}
            <p className="demo-notice">고정된 정책명 예시를 검색합니다. 실제 공고 검색이나 자격 판정이 아니며 검색어를 서버로 전송·저장하지 않습니다.</p> {/* 데이터와 개인정보 처리 범위를 밝혀요. */}
            <form className="demo-search-form" role="search" aria-label="가상 공고 검색" onSubmit={search}> {/* 다른 검색 폼과 구분되는 이름을 붙여요. */}
                <label htmlFor="demo-search-query">정책명</label> {/* 입력란에 보이는 이름을 연결해요. */}
                <div className="demo-actions"><input id="demo-search-query" type="search" maxLength={100} value={query} onChange={(event) => setQuery(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? "demo-search-error" : "demo-search-hint"} autoComplete="off" /><button type="submit" className="button button-primary">검색</button><button type="button" className="button button-secondary" onClick={reset}>초기화</button></div> {/* 버튼과 Enter 모두 같은 검색을 수행해요. */}
                <p id="demo-search-hint">예: 신혼, 버팀목 · 띄어쓰기 없이 입력해도 찾을 수 있습니다.</p> {/* 지원하는 검색 범위를 알려줘요. */}
                {error && <p id="demo-search-error" role="alert">{error}</p>} {/* 오류를 보조기기에도 전달해요. */}
            </form> {/* 검색 입력을 마쳐요. */}
            <label className="demo-search-mode"><input type="checkbox" checked={personalized} onChange={(event) => setPersonalized(event.target.checked)} />가상 프로필의 배지 표시 예시 보기</label> {/* 실제 로그인 상태를 변경하지 않고 표시 계약만 체험해요. */}
            <p>끄면 비로그인 표시 예시로 전환합니다. 조건표 없는 결과는 계속 ‘조건표 없음’으로 표시합니다.</p> {/* 비로그인 badge null과 no_rule의 차이를 설명해요. */}
            <p role="status">{submitted === null ? "정책명을 입력해 검색해 주세요." : `‘${submitted}’ 검색 예시 ${results.length}개`}</p> {/* 입력 중에는 결과 수가 바뀌지 않아요. */}
            {submitted !== null && results.length === 0 && <p>일치하는 예시가 없습니다. 실제 지원 제도가 없다는 뜻은 아닙니다. 다른 정책명을 입력해 주세요.</p>} {/* 목업 검색의 한계를 명확하게 알려줘요. */}
            {results.map((item) => <article className="demo-panel demo-card" key={item.service_id}> {/* 검색 API의 안정된 식별자를 목록 키로 사용해요. */}
                <p className="demo-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 각 결과의 맨 위에 필수 안내를 표시해요. */}
                <span className="demo-verdict">{item.badge === "no_rule" ? "조건표 없음 · 자격 판정 불가" : personalized ? "확인 필요 · 가상 프로필 예시" : "개인화 배지 없음 · 비로그인 표시 예시"}</span> {/* 조건표 없는 공고와 판정 미확정을 분리해요. */}
                <h3>{item.name}</h3><p>{item.subject === "self" ? "본인" : "부모님"} 대상 · 화면 예시</p> {/* 본인과 부모님 대상을 섞지 않아요. */}
                <p>예시 데이터 기준일: {item.updated ?? "원문 연결 후 확인"}</p> {/* 날짜가 없는 결과에 임의 날짜를 넣지 않아요. */}
                <p>공식 공고 원문 미연결 · 실제 조건은 원문 연결 후 확인해 주세요.</p> {/* 없는 원문 링크를 만들지 않아요. */}
            </article>)} {/* 검색 결과를 마쳐요. */}
        </section> // 시연 검색을 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 검색 컴포넌트를 마쳐요.
