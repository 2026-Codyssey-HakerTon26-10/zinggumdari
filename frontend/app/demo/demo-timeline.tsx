"use client"; // 목록과 표 보기 사이를 버튼으로 전환해요.
import { useState } from "react"; // 보기 방식만 현재 화면에서 기억해요.
export type DemoStep = { step: string; assume: Record<string, string | number>; opens: string[]; closes: string[]; todo: { action: string; evidence: string[] }[] }; // API 타임라인의 단계별 응답 모양이에요.
const labels: Record<string, string> = { newlywed: "신혼", child: "자녀", multi_child: "다자녀" }; // API 단계 키를 사용자에게 익숙한 이름으로 바꿔요.
const names: Record<string, string> = { "manual:hug-newlywed-jeonse": "신혼부부전용 전세자금", "manual:hug-buttimok-youth": "청년전용 버팀목", "manual:hug-newborn-buttimok": "신생아 특례 버팀목" }; // API 예시에 등장하는 제도의 표시 이름이에요.
const assumptions: Record<string, string> = { marital_status: "혼인 상태", marriage_date: "혼인신고일", children_count: "자녀 수", youngest_child_age: "막내 나이" }; // 가정한 프로필 칸을 읽기 쉽게 표시해요.
function assumptionText(step: DemoStep) { // 날짜를 임의로 계산하지 않고 응답의 가정을 설명해요.
    return Object.entries(step.assume).map(([field, value]) => `${assumptions[field] ?? field}: ${value === "today" ? "모의 기준일" : value}`).join(" · "); // 서버가 준 가정 값만 사용해요.
} // 가정 설명을 마쳐요.
function policyText(ids: string[]) { // 제도 ID 목록을 표시 이름으로 바꿔요.
    return ids.length ? ids.map((id) => names[id] ?? "제도 이름 확인 필요").join(", ") : "응답에 표시된 제도 없음"; // 빈 목록을 실제 지원 제도 부재로 단정하지 않아요.
} // 제도 설명을 마쳐요.
function todoText(step: DemoStep) { // 근거가 없는 준비 사항은 만들어내지 않아요.
    const supported = step.todo.filter((todo) => todo.evidence.length > 0); // 근거 줄 ID가 있는 해둘 일만 표시 대상으로 삼아요.
    return supported.length ? supported.map((todo) => `${todo.action} · 근거: ${todo.evidence.join(", ")}`).join(" / ") : "근거가 연결된 해둘 일 없음"; // 미연결 상태를 그대로 알려줘요.
} // 준비 사항 설명을 마쳐요.
export function DemoTimeline({ steps, activeStep }: { steps: DemoStep[]; activeStep?: string }) { // 프로필 응답의 타임라인을 받는 독립 화면 조각이에요.
    const [table, setTable] = useState(false); // 처음에는 읽기 쉬운 단계 목록을 보여줘요.
    return ( // 타임라인 영역을 그려요.
        <section className="demo-results" aria-labelledby="demo-timeline-title"> {/* 단계 목록의 제목을 연결해요. */}
            <h2 id="demo-timeline-title">다음 단계 미리 보기</h2> {/* 미래 상황임을 알려줘요. */}
            <p className="demo-notice">API 문서의 타임라인 예시입니다. 실제로 제도가 열리거나 닫힌다는 판정이 아닙니다. 실제 프로필은 변경하지 않습니다.</p> {/* 예시와 실제 판정을 분리해요. */}
            <p className="demo-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 타임라인에도 같은 필수 고지를 붙여요. */}
            <button type="button" className="button button-secondary" aria-pressed={table} aria-controls="demo-timeline-content" onClick={() => setTable((value) => !value)}>표 보기 {table ? "켜짐" : "꺼짐"}</button> {/* 눌린 상태를 보조기기에도 전달해요. */}
            <div id="demo-timeline-content"> {/* 보기 방식이 바뀌는 영역이에요. */}
                {steps.length === 0 ? <p>표시할 다음 단계가 없습니다.</p> : table ? ( // 빈 결과와 보기 방식을 구분해요.
                    <div className="demo-table-scroll" role="region" aria-label="단계별 비교표, 가로로 스크롤할 수 있습니다" tabIndex={0}> {/* 작은 화면에서도 표를 키보드로 스크롤해요. */}
                        <table className="demo-table"> {/* 비교 정보를 실제 표 구조로 전달해요. */}
                            <caption>가정한 단계별 변화 · 문서 예시</caption> {/* 표의 용도를 설명해요. */}
                            <thead><tr><th scope="col">단계·가정</th><th scope="col">열림 예시</th><th scope="col">닫힘 예시</th><th scope="col">해둘 일·근거</th></tr></thead> {/* 각 열의 의미를 지정해요. */}
                            <tbody>{steps.map((step) => <tr key={step.step} aria-current={activeStep === step.step ? "step" : undefined}><th scope="row">{labels[step.step] ?? step.step}<small>{assumptionText(step)}</small></th><td>{policyText(step.opens)}</td><td>{policyText(step.closes)}</td><td>{todoText(step)}</td></tr>)}</tbody> {/* 목록 보기와 같은 응답을 사용해요. */}
                        </table> {/* 비교표를 마쳐요. */}
                    </div> // 스크롤 영역을 마쳐요.
                ) : ( // 기본 단계 목록을 보여줘요.
                    <ol className="demo-timeline-list"> {/* 단계 순서를 순서 있는 목록으로 전달해요. */}
                        {steps.map((step) => <li className="demo-panel" key={step.step} aria-current={activeStep === step.step ? "step" : undefined}><h3>{labels[step.step] ?? step.step}</h3><p>가정: {assumptionText(step)}</p><dl><dt>열림 예시</dt><dd>{policyText(step.opens)}</dd><dt>닫힘 예시</dt><dd>{policyText(step.closes)}</dd><dt>해둘 일·근거</dt><dd>{todoText(step)}</dd></dl></li>)} {/* 응답에 없는 사건 날짜나 지원 조건은 추가하지 않아요. */}
                    </ol> // 단계 목록을 마쳐요.
                )} {/* 보기 전환을 마쳐요. */}
            </div> {/* 결과 영역을 마쳐요. */}
        </section> // 타임라인을 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 타임라인 조각을 마쳐요.
