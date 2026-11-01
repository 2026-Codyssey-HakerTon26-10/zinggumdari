"use client"; // 판정 응답을 읽어 먼저 할 일을 제안하는 브리핑이에요.
import { useState } from "react"; // 생활 변화 확인 단계를 기억해요.
import { Icon } from "../../components/ui"; // 서비스에서 쓰던 아이콘을 사용해요.
import type { Card, FullProfile, Judge, Stage, TimelineStep } from "../../lib/service-api"; // 서버 판정 응답만 읽어요.
import "./briefing.css"; // 브리핑 전용 스타일이에요.

export const STAGE_LABEL: Record<string, string> = { newlywed: "결혼하면", child: "아이가 생기면", multi_child: "가족이 늘면" }; // 단계 키를 사용자 문구로 바꿔요.
const NEXT: Record<string, Stage> = { "": "newlywed", newlywed: "child", child: "multi_child" }; // 단계 넘기기 순서예요.
const TODO: Record<string, string> = { marriage_registration: "혼인신고", move_in: "전입신고", subscription_account: "청약통장 준비", ltc_grade_apply: "장기요양등급 신청" }; // 해둘 일 이름이에요.

type Suggestion = { icon: string; tone?: "now" | "next" | "parent" | "date"; title: string; detail?: string; action?: { label: string; run?: () => void; href?: string; external?: boolean } }; // 제안 한 줄의 모양이에요.
export type LifeEvent = { key: string; label: string; summary: string; patch: Record<string, string | number> }; // 생활 변화 하나와 저장할 칸이에요.
export type Changed = { label: string; prev: Judge }; // 방금 반영한 생활 변화와 반영 전 판정이에요.
type Props = { profile: FullProfile; result: Judge; baseline: Judge | null; stage: Stage; busy: boolean; changed?: Changed | null; onStage: (stage: Stage) => void; onParent: () => void; onFocus: (id: string) => void; onEvent?: (event: LifeEvent) => Promise<void>; onDismiss?: () => void }; // 단계 이동·화면 이동·프로필 저장은 부모 화면이 처리해요.

/** 지금 프로필에서 일어날 수 있는 생활 변화. 저장할 칸을 미리 보여주고 확인을 받아요. */
function lifeEvents(profile: FullProfile): LifeEvent[] {
    const me = profile.self as Record<string, unknown>;
    const today = new Date().toISOString().slice(0, 10);
    const kids = Number(me.children_count) || 0;
    const size = Number(me.household_size) || 1;
    const out: LifeEvent[] = [];
    if (["미혼", "예비부부"].includes(String(me.marital_status))) out.push({ key: "married", label: "결혼했어요", summary: `혼인 상태 신혼 · 혼인신고일 ${today} · 가구원 ${size + 1}명`, patch: { marital_status: "신혼", marriage_date: today, household_size: size + 1 } });
    out.push({ key: "baby", label: kids ? "아이가 또 태어났어요" : "아이가 태어났어요", summary: `자녀 ${kids + 1}명 · 막내 0세 · 가구원 ${size + 1}명`, patch: { children_count: kids + 1, youngest_child_age: 0, household_size: size + 1 } });
    if (me.employment_status === "구직") out.push({ key: "job", label: "취업했어요", summary: "취업 상태 재직", patch: { employment_status: "재직" } });
    else if (me.employment_status === "재직") out.push({ key: "jobless", label: "일을 쉬게 됐어요", summary: "취업 상태 구직", patch: { employment_status: "구직" } });
    return out;
}

function LifeEvents({ profile, onEvent }: { profile: FullProfile; onEvent: (event: LifeEvent) => Promise<void> }) { // 생활 변화를 한 번에 반영해요.
    const [picked, setPicked] = useState<LifeEvent | null>(null); const [saving, setSaving] = useState(false);
    return <div className="briefing-events">
        <p><Icon name="refresh" /> 생활에 변화가 있었나요? 알려주시면 바로 다시 찾아볼게요.</p>
        {!picked ? <div className="briefing-chips">{lifeEvents(profile).map((event) => <button key={event.key} type="button" onClick={() => setPicked(event)}>{event.label}</button>)}<a href="/my/alerts">이사·소득이 바뀌었어요</a></div>
            : <div className="briefing-confirm"><span><strong>{picked.label}</strong> · 내 정보에 이렇게 저장해요: {picked.summary}</span><span className="briefing-confirm-actions"><button type="button" className="is-primary" disabled={saving} onClick={async () => { setSaving(true); try { await onEvent(picked); } finally { setSaving(false); setPicked(null); } }}>{saving ? "반영 중…" : "반영하기"}</button><button type="button" disabled={saving} onClick={() => setPicked(null)}>취소</button></span></div>}
    </div>;
}

const todos = (step?: TimelineStep) => [...new Set((step?.todo || []).filter((t) => t.status !== "met").map((t) => TODO[t.action] || t.read_as || "준비 조건 확인"))]; // 이미 된 일은 빼요.
const nameList = (names: string[], limit = 3) => names.slice(0, limit).join(", ") + (names.length > limit ? ` 외 ${names.length - limit}개` : ""); // 긴 목록은 개수로 줄여요.

/** 지금 단계와 넘겨 본 단계를 비교해 새로 열리는 제도와 닫히는 제도를 찾아요. */
export function stageDiff(result: Judge, baseline: Judge | null) {
    const before = new Map((baseline?.cards || []).filter((c) => c.subject === "self").map((c) => [c.rule_id, c.verdict]));
    const folded = new Map((baseline?.folded?.items || []).map((f) => [f.rule_id, f.verdict])); // 접혀 있었을 뿐인 제도는 새로 열린 것이 아니에요.
    const was = (id: string) => before.get(id) ?? folded.get(id); // 지금 단계에서의 판정(없으면 탈락이었어요).
    const now = result.cards.filter((c) => c.subject === "self");
    const opened = now.filter((c) => c.verdict !== "opens_later" && (was(c.rule_id) === undefined || was(c.rule_id) === "opens_later"));
    const ids = new Set(now.map((c) => c.rule_id));
    const closed = (baseline?.cards || []).filter((c) => c.subject === "self" && c.verdict !== "opens_later" && !ids.has(c.rule_id));
    return { opened, closed };
}

function dday(date: string) { // 마감까지 남은 날을 세요.
    const days = Math.ceil((new Date(`${date}T00:00:00`).getTime() - Date.now()) / 86_400_000);
    return days > 0 ? `D-${days}` : days === 0 ? "오늘 마감" : "";
}

function nowSuggestions({ profile, result, changed, onStage, onParent, onFocus, onDismiss }: Props): Suggestion[] {
    const out: Suggestion[] = [];
    if (changed) { // 방금 반영한 생활 변화로 무엇이 달라졌는지 먼저 알려줘요.
        const { opened, closed } = stageDiff(result, changed.prev);
        out.push({ icon: "sparkles", tone: "next", title: `「${changed.label}」 반영 · 새로 열린 제도 ${opened.length}개${closed.length ? `, 끝난 제도 ${closed.length}개` : ""}`, detail: opened.length ? nameList(opened.map((c) => c.name)) : "새로 열린 제도는 없지만 판정을 최신 정보로 다시 했어요", action: opened.length ? { label: "새 카드 보기", run: () => onFocus("recommendations") } : onDismiss ? { label: "확인", run: onDismiss } : undefined });
    }
    const self = result.cards.filter((c) => c.subject === "self");
    const eligible = self.filter((c) => c.verdict === "eligible");
    if (eligible.length) out.push({ icon: "check-circle", tone: "now", title: `지금 바로 신청할 수 있는 제도 ${eligible.length}개`, detail: nameList(eligible.map((c) => c.name)), action: { label: "카드 보기", run: () => onFocus("recommendations") } });
    if (result.ask?.subject === "self") {
        const waiting = self.filter((c) => c.conditions.some((x) => x.grade === "질문")).length;
        out.push({ icon: "sparkles", tone: "now", title: "질문 하나면 판정이 더 정확해져요", detail: `${result.ask.question}${waiting ? ` · 답을 기다리는 제도 ${waiting}개` : ""}`, action: { label: "답하기", run: () => onFocus("ask") } });
    }
    const next = result.timeline.self[0];
    if (next?.opens.length) {
        const names = next.opens.map((id) => result.cards.find((c) => c.rule_id === id)?.name || result.folded?.items.find((f) => f.rule_id === id)?.name).filter((n): n is string => Boolean(n));
        const prep = todos(next);
        out.push({ icon: "heart", tone: "next", title: `${STAGE_LABEL[next.step] || "다음 단계에"} 새로 열리는 제도 ${new Set(next.opens).size}개`, detail: `${nameList(names)}${prep.length ? ` · 그 전에 해둘 일: ${prep.join(", ")}` : ""}`, action: { label: "미리 보기", run: () => onStage(next.step as Stage) } });
    }
    const parent = result.timeline.parent.find((s) => s.year) || result.timeline.parent[0];
    if (parent?.opens.length && profile.consents.parent) {
        const who = parent.relation === "모" ? "어머니" : parent.relation === "부" ? "아버지" : "부모님";
        const more = result.timeline.parent.filter((s) => s !== parent && todos(s).length).map((s) => todos(s).join(", "));
        out.push({ icon: "family", tone: "parent", title: parent.year ? `${who} ${parent.year}년 만 65세, 열리는 제도 ${parent.opens.length}개` : `${who}께 필요한 제도 ${parent.opens.length}개`, detail: `${parent.apply_from ? `${parent.apply_from} 신청 · ` : ""}${more.length ? `지금 챙길 일: ${more.join(", ")}` : "자녀가 대신 신청을 도울 수 있어요"}`, action: { label: "부모님", run: onParent } });
    }
    const due = (result.timeline.dated || []).find((d) => d.date && dday(d.date));
    if (due?.date) out.push({ icon: "clock", tone: "date", title: `${due.what} ${dday(due.date)}`, detail: `${due.date}까지 · 놓치지 않게 알림을 켜 둘 수 있어요`, action: { label: "알림 켜기", href: "/my/alerts" } });
    out.push({ icon: "mail", title: "오늘 정리한 내용을 생애주기 리포트로 받아 보세요", detail: "지금 → 결혼 → 자녀 → 부모님까지 한 장에 정리해 드려요", action: { label: "리포트", href: "/api/backend/notify/report", external: true } });
    return out;
}

function stageSuggestions({ result, baseline, stage, onStage, onFocus }: Props): Suggestion[] {
    const label = STAGE_LABEL[stage] || "이 단계에서";
    const { opened, closed } = stageDiff(result, baseline);
    const step = baseline?.timeline.self.find((s) => s.step === stage);
    const out: Suggestion[] = [];
    if (opened.length) out.push({ icon: "plus", tone: "next", title: `${label} 새로 열리는 제도 ${opened.length}개`, detail: nameList(opened.map((c: Card) => c.name), 4), action: { label: "카드 보기", run: () => onFocus("recommendations") } });
    if (closed.length) out.push({ icon: "info", tone: "date", title: `더 이상 해당하지 않는 제도 ${closed.length}개`, detail: `${nameList(closed.map((c) => c.name))} · 미리 신청할 수 있는지 확인해 보세요` });
    const prep = todos(step);
    if (prep.length) out.push({ icon: "check-circle", tone: "now", title: `그 전에 해둘 일: ${prep.join(", ")}`, detail: "공고 원문에 근거가 있는 준비 사항이에요" });
    const after = NEXT[stage];
    if (after) out.push({ icon: "arrow-right", title: `그다음, ${STAGE_LABEL[after]}?`, detail: "다음 생애 단계도 이어서 살펴볼 수 있어요", action: { label: "이어 보기", run: () => onStage(after) } });
    out.push({ icon: "refresh", title: "지금의 나로 돌아가기", detail: "저장된 내 정보는 바뀌지 않았어요", action: { label: "지금으로", run: () => onStage("") } });
    return out;
}

export function Briefing(props: Props) { // 판정이 끝나면 먼저 해야 할 일을 골라 보여줘요.
    const { profile, stage, busy } = props;
    const nick = String(profile.self.nickname || "회원");
    const items = stage ? stageSuggestions(props) : nowSuggestions(props);
    const key = `${stage}-${props.result.cards.length}`; // 결과가 바뀌면 제안이 다시 차례로 나타나요.
    return <section className="briefing" aria-live="polite" aria-busy={busy}>
        <div className="briefing-head">
            <span className="briefing-avatar" aria-hidden="true"><Icon name="sparkles" /></span>
            <div>
                <p className="briefing-eyebrow">징검다리 브리핑{stage ? ` · ${STAGE_LABEL[stage]} 가정` : ""}</p>
                <h2>{busy ? `${STAGE_LABEL[stage] || "지금"} 상황으로 다시 살펴보고 있어요` : stage ? `${STAGE_LABEL[stage]}, 이렇게 달라져요` : props.changed ? `${nick}님의 새 생활에 맞춰 다시 찾아봤어요` : `${nick}님, 오늘 먼저 챙겨 봤어요`}</h2>
            </div>
        </div>
        {busy ? <div className="briefing-thinking" role="status"><span /><span /><span /> 공고 조건표로 다시 판정하는 중</div> :
            <ol className="briefing-list" key={key}>
                {items.map((item, index) => <li key={item.title} className={`briefing-item ${item.tone ? `is-${item.tone}` : ""}`} style={{ animationDelay: `${index * 110}ms` }}>
                    <span className="briefing-icon"><Icon name={item.icon} /></span>
                    <span className="briefing-copy"><strong>{item.title}</strong>{item.detail && <small>{item.detail}</small>}</span>
                    {item.action && (item.action.href
                        ? <a className="briefing-action" href={item.action.href} {...(item.action.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{item.action.label}<Icon name="chevron-right" /></a>
                        : <button type="button" className="briefing-action" onClick={item.action.run}>{item.action.label}<Icon name="chevron-right" /></button>)}
                </li>)}
            </ol>}
        {!busy && !stage && props.onEvent && <LifeEvents profile={profile} onEvent={props.onEvent} />}
        <p className="briefing-note"><Icon name="info" /> 제안은 공고 원문 조건표와 내 정보로 계산했어요. AI가 자격을 판정하지 않아요.</p>
    </section>;
} // 브리핑을 마쳐요.
