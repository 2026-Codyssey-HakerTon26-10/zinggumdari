"use client"; // 조건을 펼쳐 근거 줄을 읽는 화면 조각이에요.
import { useId } from "react"; // 여러 카드가 있어도 안내 영역 ID가 겹치지 않게 해요.
import type { DemoCondition } from "./demo-data"; // 판정 응답의 조건과 근거 모양을 사용해요.
export type DemoLine = { id: string; page: number | null; bbox: number[] | null; text: string }; // 원문 API의 줄 필드를 사용해요.
export type DemoNotice = { doc_id: string; title: string; lines: DemoLine[] }; // 원문 ID와 줄 목록을 함께 보관해요.
export function DemoEvidence({ condition, notice }: { condition: DemoCondition; notice: DemoNotice }) { // 조건이 직접 가리키는 줄만 표시 대상으로 받아요.
    const id = useId(); // 설명과 근거 목록을 연결할 고유 이름이에요.
    const ids = new Set(condition.evidence.map((entry) => entry.id)); // 문장 검색 대신 응답의 근거 ID를 사용해요.
    const matches = notice.lines.filter((line) => ids.has(`${notice.doc_id}:${line.id}`)); // 문서 ID까지 일치한 줄만 강조해요.
    const missing = condition.evidence.filter((entry) => !notice.lines.some((line) => entry.id === `${notice.doc_id}:${line.id}`)); // 다른 문서나 삭제된 줄을 추측해서 연결하지 않아요.
    return ( // 조건 한 줄과 펼칠 수 있는 원문 예시를 그려요.
        <details className="demo-evidence"> {/* 기본 펼침 요소로 키보드 Enter·Space 조작을 지원해요. */}
            <summary><span>{condition.read_as}</span><strong>{condition.grade}</strong><span className="demo-evidence-action">근거 줄 보기</span></summary> {/* 버튼 역할을 하는 제목에 조건과 상태를 함께 표시해요. */}
            <section aria-labelledby={`${id}-title`} aria-describedby={`${id}-notice`}> {/* 선택한 조건의 근거만 설명하는 영역이에요. */}
                <h4 id={`${id}-title`}>{notice.title}</h4> {/* 공식 공고가 아닌 문서 예시임을 제목으로 밝혀요. */}
                <p id={`${id}-notice`}>공식 공고 원문 미연결 · 아래는 팀 API 문서의 발췌 예시입니다. 실제 자격의 근거로 사용할 수 없습니다.</p> {/* 샘플 문장을 실제 인용으로 오해하지 않도록 안내해요. */}
                {matches.length === 0 ? <p>이 조건에 연결된 근거 줄이 없습니다. 텍스트로 위치를 추측해 강조하지 않습니다.</p> : <ol className="demo-source-lines">{notice.lines.map((line) => <li key={line.id}><span>{line.id}</span>{ids.has(`${notice.doc_id}:${line.id}`) ? <mark>{line.text}<span className="demo-evidence-label">선택한 조건의 근거 예시</span></mark> : <span>{line.text}</span>}</li>)}</ol>} {/* 완전한 근거 ID가 일치할 때만 mark를 그려요. */}
                {missing.length > 0 && <p>응답의 근거 중 현재 줄 목록에 없는 항목이 있습니다. 원문 연결을 확인해야 합니다.</p>} {/* 부분 누락도 조용히 무시하지 않아요. */}
            </section> {/* 원문 영역을 마쳐요. */}
        </details> // 조건의 펼침 영역을 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 근거 보기 컴포넌트를 마쳐요.
