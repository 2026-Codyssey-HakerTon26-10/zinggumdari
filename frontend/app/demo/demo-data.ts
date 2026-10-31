import type { DemoStep } from "./demo-timeline"; // 타임라인 응답의 단계 모양을 공유해요.
export const demoStages = [{ id: "youth", label: "청년", assumption: "미혼으로 가정" }, { id: "marriage_planned", label: "예비부부", assumption: "원래 가상 프로필" }, { id: "newlywed", label: "신혼", assumption: "혼인신고일을 모의 기준일로 가정" }, { id: "child", label: "자녀", assumption: "자녀 1명 · 막내 나이 0세로 가정" }, { id: "multi_child", label: "다자녀", assumption: "자녀 2명으로 가정" }] as const; // 시연 단계의 순서와 가정을 분리해요.
export type DemoStage = typeof demoStages[number]["id"]; // 허용된 단계만 선택할 수 있어요.
export type DemoCondition = { read_as: string; grade: "확정" | "확인 필요" | "질문"; ok: boolean | null }; // API 조건 중 이번 화면이 사용하는 칸이에요.
export type DemoCard = { rule_id: string; subject: "self"; name: string; verdict: "needs_check"; conditions: DemoCondition[]; detail_url: string | null; updated: string }; // 판정 응답의 카드 이름을 그대로 사용해요.
export type DemoResult = { user_id: string; cards: DemoCard[]; timeline: { self: DemoStep[] } }; // API 판정 응답 중 첫 기능에 필요한 부분이에요.
export const demoProfile = { user_id: "demo-jiwon", self: { nickname: "지원", birth_year: 1999, sido: "서울", sigungu: "마포구", marital_status: "예비부부" } }; // API 문서를 바탕으로 만든 가상 프로필이며 서버에 저장하지 않아요.
const result: DemoResult = { // 실제 엔진 응답과 구분되는 고정 화면 예시예요.
    user_id: demoProfile.user_id, // 선택한 가상 프로필과 결과를 연결해요.
    timeline: { self: [ // API 문서 §3의 단계 예시이며 실제 엔진 계산 결과가 아니에요.
        { step: "newlywed", assume: { marital_status: "신혼", marriage_date: "today" }, opens: ["manual:hug-newlywed-jeonse"], closes: ["manual:hug-buttimok-youth"], todo: [] }, // 준비 사항의 예시 근거는 원문 미확인이라 포함하지 않아요.
        { step: "child", assume: { children_count: 1, youngest_child_age: 0 }, opens: ["manual:hug-newborn-buttimok"], closes: [], todo: [] }, // 자녀 단계의 응답 예시예요.
        { step: "multi_child", assume: { children_count: 2 }, opens: [], closes: [], todo: [] }, // 문서의 생략 기호를 실제 제도 ID로 만들지 않아요.
    ] }, // 다음 단계의 고정 예시를 마쳐요.
    cards: [{ // API 문서 §3의 카드 예시를 화면에 필요한 만큼 사용해요.
        rule_id: "manual:hug-newlywed-jeonse", subject: "self", name: "신혼부부전용 전세자금", verdict: "needs_check", // 현재 프로필의 자격을 확정하지 않아요.
        conditions: [ // 조건 문구는 API 문서의 예시이며 실제 공고 판정이 아니에요.
            { read_as: "혼인 7년 이내(신청일 기준)", grade: "질문", ok: null }, // 혼인신고일을 확인해야 해요.
            { read_as: "부부합산 소득 조건", grade: "질문", ok: null }, // 소득 정보가 없으므로 통과로 표시하지 않아요.
            { read_as: "순자산 기준 이하", grade: "확인 필요", ok: null }, // 자산 확인이 필요하다는 상태를 보여줘요.
        ], // 조건 예시를 마쳐요.
        detail_url: null, updated: "2026-10-31", // 문서 예시 기준일이며 공식 공고 URL은 연결 전이에요.
    }], // 카드 예시를 마쳐요.
}; // 고정 응답을 마쳐요.
export async function loadDemoRecommendation(stage: DemoStage = "marriage_planned"): Promise<DemoResult> { // 나중에 API 어댑터로 교체할 수 있는 데이터 경계예요.
    const response = structuredClone(result); // 원본 예시와 실제 프로필은 수정하지 않아요.
    if (stage === "youth" || stage === "multi_child") response.cards = []; // 문서에 해당 단계의 카드 응답이 없으므로 제도를 지어내지 않아요.
    if (stage === "newlywed") response.cards[0].conditions[0] = { read_as: "혼인신고일을 모의 기준일로 가정 · 실제 날짜와 원문 확인 필요", grade: "확인 필요", ok: null }; // 가정만으로 실제 자격을 확정하지 않아요.
    if (stage === "child") response.cards = [{ rule_id: "manual:hug-newborn-buttimok", subject: "self", name: "신생아 특례 버팀목", verdict: "needs_check", conditions: [{ read_as: "자녀 1명으로 가정 · 세부 자격과 원문 확인 필요", grade: "확인 필요", ok: null }], detail_url: null, updated: "2026-10-31" }]; // 타임라인에 등장하는 제도의 화면 예시만 제공해요.
    return response; // 매번 독립된 응답을 돌려주고 실제 계정이나 네트워크는 사용하지 않아요.
} // 가상 응답 함수를 마쳐요.
