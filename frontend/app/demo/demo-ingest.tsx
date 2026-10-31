"use client"; // 준비된 공고 예시를 선택하고 재생 결과를 확인해요.
import { useState } from "react"; // 선택한 예시와 재생 상태를 기억해요.
import type { DemoCard } from "./demo-data"; // 추천 카드와 같은 표시 계약을 사용해요.
type Replay = { log: { doc_id: string; llm_calls: number; auto_verified: number; needs_review: number; unaccounted: string[] }; replayed: true; replay_reason: string; rules: { id: string; review: { status: "unreviewed" }; conditions: { read_as: string; evidence: string[]; checks: Record<string, string> }[] }[] }; // 공고 투입 응답에서 이번 화면이 사용하는 필드예요.
const samples = [{ id: "demo-ingest-a", name: "가상 공고 A · 조건 확인 필요", text: "화면 동작을 설명하기 위한 가상 공고입니다." }, { id: "demo-ingest-b", name: "가상 공고 B · 미반영 줄 확인", text: "추출되지 않은 줄을 보여주기 위한 가상 공고입니다." }]; // 실제 공공 공고를 가장하지 않는 두 가지 고정 예시예요.
function replaySample(id: string): Replay { // 실제 캐시 파일이나 AI 호출 없이 응답 모양만 만들어요.
    return { log: { doc_id: id, llm_calls: 0, auto_verified: 0, needs_review: 1, unaccounted: id === "demo-ingest-b" ? [`${id}:l2`] : [] }, replayed: true, replay_reason: "고정된 화면 예시 재생 · 실제 캐시 아님", rules: [{ id: `upload:${id}:example`, review: { status: "unreviewed" }, conditions: [{ read_as: "원문 조건 확인 필요", evidence: [], checks: { schema: "ok", evidence: "missing", value: "not_checked", comparator: "not_checked" } }] }] }; // 근거 없는 예시 조건은 검증 통과나 신청 가능으로 만들지 않아요.
} // 응답 예시 생성을 마쳐요.
const checkNames: Record<string, string> = { schema: "형식", evidence: "근거 줄", value: "값", comparator: "비교어" }; // 검사 키를 읽기 쉬운 이름으로 바꿔요.
export function DemoIngest({ onAdd }: { onAdd: (card: DemoCard) => void }) { // 재생 결과를 현재 화면의 카드 목록에 합류시켜요.
    const [sampleId, setSampleId] = useState(samples[0].id); // 첫 번째 가상 공고를 기본 선택해요.
    const [cached, setCached] = useState(true); // 실제 호출과 구분되는 재생 모드를 표시해요.
    const [result, setResult] = useState<Replay | null>(null); // 아직 재생하지 않았다면 검사 결과를 보여주지 않아요.
    function replay() { // 명시적으로 버튼을 눌렀을 때만 예시를 추가해요.
        if (!cached) return; // 실제 AI 호출은 이 화면에서 지원하지 않아요.
        const sample = samples.find((entry) => entry.id === sampleId); // 사용자가 선택한 고정 자료만 사용해요.
        if (!sample) return; // 목록에 없는 값은 처리하지 않아요.
        const response = replaySample(sample.id); // 네트워크 없이 정해진 예시를 불러와요.
        setResult(response); // 검사 표와 재생 안내를 보여줘요.
        onAdd({ rule_id: response.rules[0].id, subject: "self", name: sample.name, verdict: "needs_check", conditions: [{ read_as: "검수 전 가상 공고 · 원문 확인 필요", grade: "확인 필요", ok: null, evidence: [] }], detail_url: null, updated: "2026-10-31" }); // 검수 전 카드는 확인 필요 상태로만 합류해요.
    } // 재생 처리를 마쳐요.
    return ( // 공고 투입 체험 영역을 그려요.
        <section className="demo-results" aria-labelledby="demo-ingest-title"> {/* 시연 경로에서 검색 다음에 놓이는 영역이에요. */}
            <h2 id="demo-ingest-title">공고 투입 · 재생 화면 체험</h2> {/* 실제 파일 처리와 구분되는 제목이에요. */}
            <p className="demo-notice">개인 서류를 올리지 마세요. 현재는 준비된 가상 자료만 재생하며, 파일·URL 입력과 업로드·AI 호출은 연결 전입니다.</p> {/* 수집하지 않는 입력란을 만들어 개인정보를 받지 않아요. */}
            <label htmlFor="demo-ingest-sample">재생할 가상 공고</label> {/* 선택 항목의 이름을 연결해요. */}
            <select id="demo-ingest-sample" className="demo-ingest-select" value={sampleId} onChange={(event) => { setSampleId(event.target.value); setResult(null); }}>{samples.map((sample) => <option key={sample.id} value={sample.id}>{sample.name}</option>)}</select> {/* 자료를 바꾸면 이전 검사 결과를 지워요. */}
            <p>{samples.find((sample) => sample.id === sampleId)?.text}</p> {/* 선택한 자료의 가상 성격을 설명해요. */}
            <label className="demo-search-mode"><input type="checkbox" checked={cached} onChange={(event) => { setCached(event.target.checked); setResult(null); }} />캐시 재생 표시 체험</label> {/* 실제 서버 캐시와 구분해 표시 동작만 체험해요. */}
            {!cached && <p role="status">실제 공고 처리는 API 연결 후 사용할 수 있습니다. 재생 표시를 켜 주세요.</p>} {/* 지원하지 않는 실시간 호출을 실행한 척하지 않아요. */}
            <button type="button" className="button button-primary" disabled={!cached} onClick={replay}>가상 결과 재생 · 예시 카드에 추가</button> {/* 선택한 자료만 중복 없이 카드에 추가해요. */}
            <p>추가한 카드는 이 화면에만 표시됩니다. 단계 변경·프로필 재선택·초기화 시 사라지며 알림은 발송하지 않습니다.</p> {/* 실제 저장·계정 알림과 분리된 동작을 알려줘요. */}
            {result && <div className="demo-panel"> {/* 재생한 뒤에만 검사 결과를 보여줘요. */}
                <p role="status"><strong>재생 예시 · 실제 AI 호출 없음</strong> — {result.replay_reason}. 예시 카드에 추가했습니다.</p> {/* 캐시 재생 여부를 눈에 띄게 표시해요. */}
                <ol className="demo-ingest-steps">{["줄 만들기", "자격 구간", "읽기", "검증", "카드 합류"].map((step) => <li key={step}>{step} · 표시 예시</li>)}</ol> {/* 가짜 진행 시간을 연출하지 않고 처리 단계를 설명해요. */}
                <div className="demo-table-scroll" role="region" aria-label="가상 공고 검사 결과" tabIndex={0}><table className="demo-table"><caption>우리가 읽은 조건 · 검사 표시 예시</caption><thead><tr><th scope="col">조건</th><th scope="col">근거 줄</th><th scope="col">검사</th></tr></thead><tbody>{result.rules[0].conditions.map((condition) => <tr key={condition.read_as}><th scope="row">{condition.read_as}</th><td>{condition.evidence.length ? condition.evidence.join(", ") : "연결 없음"}</td><td><ul>{Object.entries(condition.checks).map(([name, value]) => <li key={name}>{checkNames[name] ?? name}: {value === "ok" ? "✓ 형식 예시 충족" : value === "missing" ? "✗ 근거 없음" : "— 미검사"}</li>)}</ul></td></tr>)}</tbody></table></div> {/* 검사 상태를 색뿐 아니라 기호와 글자로 표시해요. */}
                <p>미반영 줄: {result.log.unaccounted.length ? result.log.unaccounted.join(", ") : "예시에 표시된 미반영 줄 없음"}</p> {/* 누락된 줄을 숨기지 않고 ID로 표시해요. */}
                <p>검수 전 · 확인 필요. 실제 원문과 검증 결과가 연결되기 전에는 자격을 확정할 수 없습니다.</p> {/* AI 추출 결과를 확정 판정으로 취급하지 않아요. */}
                <details><summary>가상 응답 로그 보기</summary><pre className="demo-ingest-log">{JSON.stringify(result, null, 2)}</pre></details> {/* 로그가 실제 서버 기록이 아니라는 이름을 붙여요. */}
            </div>} {/* 재생 결과를 마쳐요. */}
        </section> // 공고 투입 체험을 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 공고 투입 컴포넌트를 마쳐요.
