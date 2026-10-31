"use client"; // 공고별 빈 칸 하나만 물어보고 명시적으로 저장해요.
import { useId, useState, type FormEvent } from "react"; // 질문마다 다른 이름과 선택한 답을 관리해요.
import Link from "next/link"; // 별도 동의 설정으로 이동해요.
import { Icon } from "../../components/ui"; // 기존 서비스 아이콘으로 선택과 이동을 안내해요.
import { message, patchProfile, type FullProfile, type Question } from "../../lib/service-api"; // 답변 저장은 세션 소유 프로필 PATCH를 사용해요.
import "./question.css"; // 답변 선택 카드를 질문 화면에만 적용해요.
const sensitive = new Set(["income_self", "income_spouse", "income_household", "income_recognized", "pregnant", "due_month", "ltc_grade", "disability_registered", "basic_pension", "livelihood_status", "care_wanted"]); // 민감 칸은 동의 없이 요청하지 않아요.
export function QuestionForm({ question, profile, simulated, onSaved }: { question: Question; profile: FullProfile; simulated: boolean; onSaved: () => void }) { // 서버가 고른 한 질문만 보여줘요.
    const questionId = useId(); // 여러 질문이 있어도 라디오 그룹과 제목이 겹치지 않게 해요.
    const [choice, setChoice] = useState(question.options.length === 1 ? "0" : ""); const [value, setValue] = useState(""); const [relation, setRelation] = useState(question.relation || (profile.parents.length === 1 ? String(profile.parents[0].relation) : "")); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); // 답이 하나면 입력란을 바로 열고, 질문이 바뀌면 이전 선택을 비워요.
    const option = question.options[Number(choice)]; const typed = choice !== "" && ["date", "month", "number", "text"].includes(String(option?.value)); // 입력 형식은 서버 옵션을 따라요.
    const blocked = simulated || (question.subject === "parent" && !profile.parents.length) || (sensitive.has(question.field) && !profile.consents.sensitive) || (question.subject === "parent" && !profile.consents.parent); // 모의 단계의 가정을 실제 정보에 저장하지 않아요.
    async function submit(event: FormEvent<HTMLFormElement>) { // 선택한 답을 실제 프로필에 저장해요.
        event.preventDefault(); if (blocked || busy || choice === "" || !option) return; setBusy(true); setError(""); // 중복·무동의 저장을 막아요.
        try { const answer = typed ? option.value === "number" ? Number(value) : value : option.value; if (typed && (!value || (option.value === "number" && !Number.isFinite(Number(value))))) throw new Error(); let patch: object; if (option.add_qualification) { const existing = profile.self.qualifications || []; const entry = option.add_qualification; patch = { self: { qualifications: [...existing.filter((item) => !(item.qual_code === entry.qual_code && item.target === entry.target)), entry] } }; } else if (question.subject === "parent") { const index = profile.parents.findIndex((parent) => parent.relation === relation); if (index < 0) { setError("답변을 저장할 부모님을 선택해 주세요."); return; } patch = { parents: profile.parents.map((parent, i) => i === index ? { ...parent, [question.field]: answer, ...option.set } : parent) }; } else patch = { self: { [question.field]: answer, ...option.set } }; await patchProfile(profile.user_id, patch); onSaved(); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } // 성공한 뒤 서버 판정을 다시 불러와요.
    } // 답변 저장을 마쳐요.
    return <section className="work-panel question-panel" aria-labelledby={questionId}> {/* 질문을 하나의 독립된 카드로 보여줘요. */}
        <p className="question-kicker"><Icon name="sparkles" />맞춤 추천을 위한 질문</p> {/* 사용자가 질문의 목적을 쉽게 알 수 있게 해요. */}
        <h2 id={questionId}>{question.question}</h2> {/* 서버에서 정한 질문만 제목으로 표시해요. */}
        <p className="question-help">현재 상황에 맞는 항목을 선택해 주세요.</p> {/* 후보 수 등 서버 내부 설명은 화면에 노출하지 않아요. */}
        {blocked ? <p className="question-consent">{simulated ? "현재 상황으로 돌아온 뒤 실제 정보를 입력해 주세요." : <>정보 저장에 별도 동의가 필요합니다. <Link href={question.subject === "parent" ? "/my/parents" : "/my/alerts"}>동의 설정</Link></>}</p> : <form onSubmit={submit} className="work-form question-form"> {/* 기존 동의와 모의 단계의 저장 제한을 유지해요. */}
            <fieldset disabled={busy} className="question-fields" aria-labelledby={questionId}> {/* 저장 중에는 모든 답변을 잠가 중복 변경을 막아요. */}
                <div className="question-options"> {/* 답을 펼쳐 보여줘서 드롭다운을 여는 단계를 줄여요. */}
                    {question.options.map((item, index) => <label className="question-option" key={index}> {/* 서버 선택지와 순서를 그대로 유지해요. */}
                        <input className="question-radio" type="radio" name={`${questionId}-answer`} value={index} checked={choice === String(index)} onChange={(event) => { setChoice(event.target.value); setValue(""); }} required /> {/* 기본 라디오로 방향키 선택과 필수 응답을 지원해요. */}
                        <span className="question-option-surface"><span className="question-option-label">{item.label}</span><span className="question-option-check"><Icon name="check" /></span></span> {/* 선택한 답은 테두리와 체크 표시로 구분해요. */}
                    </label>)} {/* 전체 선택지 표시를 마쳐요. */}
                </div> {/* 답변 선택 영역을 마쳐요. */}
                {question.subject === "parent" && <fieldset className="question-parent-fields"><legend>누구의 정보인가요?</legend><div className="question-options">{profile.parents.map((parent) => <label className="question-option" key={String(parent.relation)}><input className="question-radio" type="radio" name={`${questionId}-parent`} value={String(parent.relation)} checked={relation === String(parent.relation)} onChange={(event) => setRelation(event.target.value)} required /><span className="question-option-surface"><span className="question-option-label">{parent.relation === "모" ? "어머니" : "아버지"}</span><span className="question-option-check"><Icon name="check" /></span></span></label>)}</div></fieldset>} {/* 부모님 답변도 선택한 분에게만 저장해요. */}
                {typed && <label className="question-value">{option.label}{option.unit ? ` (${option.unit})` : ""}<input type={String(option.value)} min={option.value === "number" ? question.field === "household_size" ? 1 : 0 : question.field === "birth_date" ? "1900-01-01" : undefined} max={question.field === "birth_date" ? new Date().toISOString().slice(0, 10) : undefined} maxLength={option.value === "text" ? 100 : undefined} required value={value} onChange={(event) => setValue(event.target.value)} step={option.value === "number" ? option.unit ? "any" : 1 : undefined} /></label>} {/* 직접 입력이 필요한 답은 기존 서버 입력 형식을 유지해요. */}
            </fieldset> {/* 질문 입력 영역을 마쳐요. */}
            {error && <p role="alert">{error}</p>} {/* 저장에 실패하면 같은 화면에서 원인을 안내해요. */}
            <div className="question-footer"><span>선택한 정보는 다음 추천에 반영돼요.</span><button className="button button-primary question-next" type="submit" disabled={busy || choice === ""}>{busy ? "저장 중…" : "다음으로"}<Icon name="arrow-right" /></button></div> {/* 다음 동작을 짧고 분명하게 안내해요. */}
        </form>} {/* 답변을 제출한 뒤에만 기존 저장 흐름을 실행해요. */}
    </section>; // 질문 카드를 마쳐요.
} // 질문 폼을 마쳐요.
