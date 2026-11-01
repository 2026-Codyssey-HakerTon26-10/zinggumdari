"use client"; // 실제 프로필에 알림 설정을 저장해요.
import { useState, type FormEvent } from "react"; // 동의와 저장 상태를 관리해요.
import Link from "next/link"; // 추천 홈과 로그인으로 이동해요.
import { Icon, SiteHeader, SiteFooter } from "../../components/ui"; // 공통 메뉴와 설정 항목의 아이콘을 사용해요.
import { LoadingState } from "../../components/loading-state"; // 불러오기와 저장 중 상태를 공통 모양으로 보여줘요.
import { patchProfile, message, type FullProfile } from "../../lib/service-api"; // 동의와 설정을 같은 요청으로 저장해요.
import { useProfile } from "../components/profile-context"; // 본인 프로필만 불러와요.
import { FieldsForm, readFields, type Field } from "../components/fields"; // 모르는 숫자와 0을 구분해요.
import "../workspace.css"; // 연결 화면 스타일을 사용해요.
import "./alerts.css"; // 맞춤 정보 설정을 읽기 쉬운 카드와 입력 영역으로 정리해요.
const housing: Field[] = [{ key: "tenure_type", label: "주거 형태", options: ["자가", "전세", "월세", "보증부월세", "무상거주"] }, { key: "is_householder", label: "세대주 여부", options: ["세대주", "세대원"] }, { key: "is_homeless", label: "무주택 여부", options: ["Y", "N"] }, { key: "deposit", label: "보증금 (만원)", type: "number", min: 0 }, { key: "monthly_rent", label: "월세 (만원)", type: "number", min: 0 }, { key: "move_in_date", label: "전입일", type: "date" }, { key: "house_price", label: "주택 가격 (만원)", type: "number", min: 0 }]; // 주거 정보는 시트 칸을 따라요.
const income: Field[] = [{ key: "employment_type", label: "맞벌이 여부", options: ["맞벌이", "외벌이", "해당없음"] }, { key: "income_self", label: "본인 월평균소득 (만원)", type: "number", min: 0 }, { key: "income_spouse", label: "배우자 월평균소득 (만원)", type: "number", min: 0 }, { key: "income_household", label: "가구 월평균소득 (만원)", type: "number", min: 0 }]; // 비율 환산은 프론트에서 하지 않아요.
const subscription: Field[] = [{ key: "has_account", label: "청약통장 가입", options: ["Y", "N"] }, { key: "joined_date", label: "청약통장 가입일", type: "date" }, { key: "payment_count", label: "납입 횟수", type: "number", min: 0, step: 1 }, { key: "deposit_amount", label: "청약 예치금 (만원)", type: "number", min: 0 }, { key: "dependents_count", label: "부양가족 수", type: "number", min: 0, step: 1 }, { key: "supports_parent_65", label: "만 65세 이상 부모님 부양", options: ["Y", "N"] }, { key: "support_start_date", label: "부양 시작일", type: "date" }]; // 필요한 추가 준비 정보만 받아요.
function AlertForm({ profile, onSaved }: { profile: FullProfile; onSaved: (profile: FullProfile) => void }) { // 저장 성공 응답으로 화면을 다시 초기화해요.
    const [sensitive, setSensitive] = useState(profile.consents.sensitive); const [email, setEmail] = useState(profile.self.alert_channel === "이메일"); const [busy, setBusy] = useState(false); const [feedback, setFeedback] = useState(""); const [failed, setFailed] = useState(false); // 저장된 동의와 성공·실패 안내를 구분해요.
    async function submit(event: FormEvent<HTMLFormElement>) { // 입력한 정보를 명시적인 저장 시점에만 보내요.
        event.preventDefault(); if (busy) return; const form = new FormData(event.currentTarget); setBusy(true); setFeedback(""); setFailed(false); // 중복 저장을 막고 이전 안내를 비워요.
        try { const self = { ...readFields(form, housing), ...readFields(form, subscription), ...(sensitive ? readFields(form, income) : {}), alert_channel: email ? "이메일" : "앱", email: email ? String(form.get("email")).trim() : null, alert_categories: form.getAll("alert_categories").map(String) }; const result = await patchProfile(profile.user_id, { self, consents: { sensitive }, stages_done: [...new Set([...profile.stages_done, "alerts"])] }); onSaved(result); setFeedback("설정을 저장했어요. 나의 추천에서 새 정보에 맞는 제도를 확인해 주세요."); } // 소득 원값과 동의를 함께 저장하고 서버 성공 후에만 완료를 안내해요.
        catch (cause) { setFailed(true); setFeedback(message(cause)); } finally { setBusy(false); } // 실패한 저장을 성공으로 표시하지 않고 다시 시도할 수 있게 해요.
    } // 맞춤 정보 저장을 마쳐요.
    return <form className="work-form alerts-form" onSubmit={submit} aria-busy={busy}> {/* 여러 정보를 따로 살펴본 뒤 한 번에 저장할 수 있어요. */}
        <section className="alerts-card" aria-labelledby="alerts-housing-title"> {/* 주거 정보를 독립된 카드에 모아요. */}
            <div className="alerts-card-heading"><span className="alerts-card-icon"><Icon name="home" /></span><div><h2 id="alerts-housing-title">지금 살고 있는 집</h2><p>주거 지원을 살펴볼 때 필요한 정보예요.</p></div></div> {/* 주거 정보를 받는 이유를 설명해요. */}
            <fieldset disabled={busy}><legend className="alerts-sr-only">주거 정보</legend><FieldsForm fields={housing} values={profile.self} /></fieldset> {/* 기존 필드 이름과 선택 값을 그대로 사용해요. */}
            <p className="alerts-help"><Icon name="info" />금액은 만원 단위예요. 모르는 항목은 비워 두셔도 괜찮아요.</p> {/* 모름을 0으로 입력하지 않도록 안내해요. */}
        </section> {/* 주거 정보 카드를 마쳐요. */}
        <section className="alerts-card" aria-labelledby="alerts-subscription-title"> {/* 청약과 부양 정보를 별도 카드로 보여줘요. */}
            <div className="alerts-card-heading"><span className="alerts-card-icon"><Icon name="bookmark" /></span><div><h2 id="alerts-subscription-title">청약과 가족 돌봄</h2><p>미리 준비한 정보도 추천에 도움이 돼요.</p></div></div> {/* 청약과 부양 정보를 입력하는 목적을 알려줘요. */}
            <fieldset disabled={busy}><legend className="alerts-sr-only">청약·부양 정보</legend><FieldsForm fields={subscription} values={profile.self} /></fieldset> {/* 원래 청약과 부양 필드를 그대로 저장해요. */}
            <p className="alerts-help"><Icon name="info" />정확한 날짜나 금액을 모르면 빈칸으로 남겨 주세요.</p> {/* 모르는 정보의 임의 입력을 막아요. */}
        </section> {/* 청약·부양 카드를 마쳐요. */}
        <section className="alerts-card alerts-card-wide" aria-labelledby="alerts-income-title"> {/* 별도 동의가 필요한 소득을 다른 정보와 구분해요. */}
            <div className="alerts-card-heading"><span className="alerts-card-icon"><Icon name="shield" /></span><div><h2 id="alerts-income-title">소득 정보 <span className="alerts-optional">선택</span></h2><p>동의한 경우에만 소득을 저장하고 관련 조건을 살펴봐요.</p></div></div> {/* 소득 정보의 선택 여부와 용도를 안내해요. */}
            <label className="alerts-consent"><span><strong>민감정보 저장에 동의해요</strong><small>소득·건강 등 민감정보를 맞춤 추천 목적으로 저장하는 데 별도로 동의합니다.</small></span><input className="alerts-toggle" type="checkbox" checked={sensitive} disabled={busy} onChange={(event) => setSensitive(event.target.checked)} /></label> {/* 실제 체크박스로 선택 동의를 직접 바꿀 수 있어요. */}
            <p className="alerts-help">동의하지 않아도 다른 정보를 바탕으로 추천을 볼 수 있어요. 동의를 해제한 뒤 저장하면 본인·부모님의 저장된 민감정보가 삭제되며, 관련 조건은 확인 필요로 남아요.</p> {/* 공통 민감정보 동의 해제의 실제 삭제 범위를 안내해요. */}
            {sensitive && <fieldset className="alerts-income-fields" disabled={busy}><legend className="alerts-sr-only">소득 정보 · 금액은 만원 단위</legend><FieldsForm fields={income} values={profile.self} /></fieldset>} {/* 동의가 켜져 있을 때만 소득 입력란을 보여줘요. */}
            {sensitive && <p className="alerts-help"><Icon name="info" />실제 월평균소득을 만원 단위로 입력해 주세요. 소득 기준 비율은 직접 계산하지 않아도 돼요.</p>} {/* 소득 원값만 받고 비율은 서버가 계산하도록 안내해요. */}
        </section> {/* 민감정보 카드를 마쳐요. */}
        <section className="alerts-card" aria-labelledby="alerts-categories-title"> {/* 관심 분야 선택을 쉽게 찾을 수 있게 모아요. */}
            <div className="alerts-card-heading"><span className="alerts-card-icon"><Icon name="sparkles" /></span><div><h2 id="alerts-categories-title">관심 있는 분야</h2><p>새 공고 알림을 받고 싶은 분야를 골라 주세요.</p></div></div> {/* 관심 분야의 용도를 구체적으로 알려줘요. */}
            <fieldset className="alerts-category-options" disabled={busy}><legend className="alerts-sr-only">관심 분야 · 여러 개 선택 가능</legend>{["주거", "임신출산", "양육", "생활", "돌봄"].map((category) => <label className="alerts-category" key={category}><input name="alert_categories" type="checkbox" value={category} defaultChecked={Array.isArray(profile.self.alert_categories) && profile.self.alert_categories.includes(category)} /><span>{category === "임신출산" ? "임신·출산" : category}</span><Icon name="check" /></label>)}</fieldset> {/* API 값은 유지하고 사용자가 보는 표기만 읽기 쉽게 바꿔요. */}
            <p className="alerts-help">여러 개를 선택할 수 있어요. 관심 분야는 언제든 바꿀 수 있어요.</p> {/* 중복 선택이 가능함을 알려줘요. */}
        </section> {/* 관심 분야 카드를 마쳐요. */}
        <section className="alerts-card" aria-labelledby="alerts-email-title"> {/* 이메일 수신 동의를 별도 카드에 담아요. */}
            <div className="alerts-card-heading"><span className="alerts-card-icon"><Icon name="mail" /></span><div><h2 id="alerts-email-title">이메일로도 받아볼까요?</h2><p>알림함과 별도로 이메일 수신을 선택할 수 있어요.</p></div></div> {/* 이메일이 선택 사항임을 알려줘요. */}
            <label className="alerts-consent"><span><strong>이메일 알림 받기</strong><small>맞춤 공고 이메일 수신에 동의합니다.</small></span><input className="alerts-toggle" type="checkbox" checked={email} disabled={busy} onChange={(event) => setEmail(event.target.checked)} /></label> {/* 수신 여부를 실제 체크박스로 선택해요. */}
            {email && <label className="alerts-email-field">알림을 받을 이메일<input name="email" type="email" autoComplete="email" maxLength={254} placeholder="example@email.com" defaultValue={typeof profile.self.email === "string" ? profile.self.email : ""} required disabled={busy} /></label>} {/* 수신을 선택한 경우에만 이메일을 입력받아요. */}
            <p className="alerts-help">회원가입 동의와 이메일 수신 동의는 별개예요. 저장했다고 이메일이 바로 발송되는 것은 아니에요.</p> {/* 설정 저장과 실제 이메일 발송을 구분해요. */}
        </section> {/* 이메일 설정 카드를 마쳐요. */}
        <div className="alerts-save-area"> {/* 저장 결과와 다음 행동을 폼 마지막에 모아요. */}
            {busy && <LoadingState label="맞춤 정보를 저장하고 있습니다." compact />} {/* 중복 저장을 막는 동안 진행 상태를 알려줘요. */}
            {feedback && <p className={`alerts-feedback ${failed ? "is-error" : "is-success"}`} role={failed ? "alert" : "status"}><Icon name={failed ? "info" : "check-circle"} />{feedback}</p>} {/* 성공과 실패를 글과 아이콘으로 구분해요. */}
            <div className="alerts-save-actions"><button className="button button-primary" disabled={busy}>{busy ? "저장 중…" : "설정 저장하기"}<Icon name="check" /></button><Link className="button button-secondary" href="/my">나의 추천으로 돌아가기<Icon name="arrow-right" /></Link></div> {/* 저장과 추천 복귀를 서로 다른 행동으로 제공해요. */}
            <p>입력한 내용과 동의 변경은 저장 버튼을 누르면 반영돼요.</p> {/* 버튼을 누르기 전에는 서버 정보가 바뀌지 않는다고 안내해요. */}
        </div> {/* 저장 영역을 마쳐요. */}
    </form>; // 알림 설정 폼을 마쳐요.
} // 알림 설정 폼을 마쳐요.
export default function AlertSettings() { // 저장된 프로필과 동의를 불러와 설정 화면을 열어요.
    const { profile, setProfile, loading, error } = useProfile(); // 로그인·프로필 없음·연결 실패를 구분해요.
    return <><SiteHeader active="my" /><main id="main-content" className="container work-main alerts-main"> {/* 알림 설정 화면의 범위를 지정해요. */}
        <Link className="alerts-back" href="/my"><Icon name="chevron-left" />나의 추천</Link> {/* 추천으로 돌아가는 길을 제목 위에 배치해요. */}
        <header className="alerts-heading"><span className="alerts-eyebrow"><Icon name="bell" />나에게 맞는 공고 소식</span><h1>내게 필요한 정보만,<br />조금 더 가까이</h1><p>지금 아는 정보부터 알려 주세요.<br />선택한 관심 분야와 상황에 맞춰 공고를 살펴볼 수 있어요.</p></header> {/* 정보 입력의 목적을 사용자 중심 문구로 설명해요. */}
        {loading ? <LoadingState label="맞춤 정보를 불러오고 있습니다." /> : error ? <section className="alerts-empty" role="alert"><Icon name="info" /><h2>설정을 불러오지 못했어요</h2><p>{error}</p><Link className="button button-secondary" href="/login">로그인 확인하기</Link></section> : profile ? <AlertForm profile={profile} onSaved={setProfile} /> : <section className="alerts-empty"><Icon name="user" /><h2>기본 정보부터 알려 주세요</h2><p>기본 정보를 입력한 뒤 맞춤 알림을 설정할 수 있어요.</p><Link className="button button-primary" href="/my">기본 정보 입력하기<Icon name="arrow-right" /></Link></section>} {/* 준비 상태에 맞는 안내와 이동 버튼을 보여줘요. */}
    </main><SiteFooter /></>; // 공통 화면 메뉴를 유지해요.
} // 알림 설정 화면을 마쳐요.
