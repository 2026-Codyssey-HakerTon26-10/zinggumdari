"use client"; // 가입 후 최소 프로필을 저장하는 폼이에요.
import { LoadingState } from "../../components/loading-state"; // 요청 중에는 회전 표시와 처리 안내를 보여줘요.
import { useEffect, useState, type FormEvent } from "react"; // 입력과 저장 실패 상태, 프리셋 목록을 관리해요.
import { api, createFromPreset, message, presets, type Preset } from "../../lib/service-api"; // 계정 세션으로 프로필을 만들어요.
import { Icon } from "../../components/ui"; // 기존 아이콘으로 정보 입력과 다음 이동을 안내해요.
import "./profile-setup.css"; // 기본 정보 폼에만 새 선택 카드 스타일을 적용해요.
function ProfileChoice({ name, label, options, value }: { name: string; label: string; options: string[]; value?: string }) { // 같은 이름의 라디오 선택지를 한 묶음으로 만들어요.
    return <fieldset className="profile-choice"><legend>{label}</legend><div className="profile-choice-options">{options.map((option) => <label className="profile-choice-option" key={option}><input type="radio" name={name} value={option} required defaultChecked={option === value} /><span>{option === "여" ? "여성" : option === "남" ? "남성" : option}<Icon name="check" /></span></label>)}</div></fieldset>; // 브라우저의 필수 선택과 키보드 이동 기능을 그대로 사용해요.
} // 선택지 묶음을 마쳐요.
export function ProfileSetup({ nickname, onSaved }: { nickname: string; onSaved: () => void }) { // 기존 프로필이 없는 계정에만 보여줘요.
    const [busy, setBusy] = useState(false); const [error, setError] = useState(""); // 중복 제출과 실패 안내를 관리해요.
    const [list, setList] = useState<Preset[]>([]); // 서버가 알려준 시연용 가상 프로필만 보여줘요.
    const [seed] = useState<Record<string, string | number> | null>(() => { try { const raw = typeof window === "undefined" ? null : sessionStorage.getItem("zing_signup_seed"); return raw ? JSON.parse(raw) : null; } catch { return null; } }); // 가입 때 고른 선택 정보로 칸을 미리 채워요(이 기기에 잠시 둔 값만 읽어요).
    const pre = (key: string) => (seed?.[key] ?? undefined) as string | undefined; // 미리 채울 값이에요.
    useEffect(() => { const controller = new AbortController(); void presets(controller.signal).then((rows) => { if (!controller.signal.aborted && Array.isArray(rows)) setList(rows.filter((row) => typeof row?.id === "string" && typeof row?.label === "string")); }).catch(() => { /* 목록을 못 받아도 직접 입력 폼은 그대로 써요. */ }); return () => controller.abort(); }, []); // 화면을 떠나면 요청을 취소해요.
    async function start(id: string) { // 가상 프리셋으로 프로필을 만들고 추천을 다시 불러와요.
        if (busy) return; setBusy(true); setError(""); try { await createFromPreset(id); onSaved(); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } // 이미 프로필이 있으면 409 안내를 그대로 보여줘요.
    } // 프리셋 시작을 마쳐요.
    async function submit(event: FormEvent<HTMLFormElement>) { // 입력한 원값으로만 최소 프로필을 만들어요.
        event.preventDefault(); if (busy) return; const form = new FormData(event.currentTarget); if (String(form.get("nickname") || "").trim().length < 2) { setError("닉네임을 공백 제외 2자 이상 입력해 주세요."); return; } setBusy(true); setError(""); // 브라우저 주소에 입력값을 남기지 않아요.
        try { await api("/profiles", { method: "POST", body: JSON.stringify({ self: { nickname: String(form.get("nickname")).trim(), gender: form.get("gender"), birth_date: form.get("birth_date"), sido: form.get("sido"), sigungu: String(form.get("sigungu")).trim(), marital_status: form.get("marital_status"), children_count: Number(form.get("children_count")), household_size: Number(form.get("household_size")), employment_status: form.get("employment_status") }, consents: { sensitive: false, parent: false }, parents: [] }) }); try { sessionStorage.removeItem("zing_signup_seed"); } catch { /* 저장소가 막혀도 저장은 끝났어요. */ } onSaved(); } // 민감정보·부모님 동의는 기본 false예요.
        catch (cause) { setError(message(cause)); } finally { setBusy(false); } // 실패하면 입력을 유지하고 다시 저장할 수 있어요.
    } // 최소 프로필 저장을 마쳐요.
    return <section className="work-panel profile-setup" aria-labelledby="profile-setup-title"> {/* 기본 정보를 하나의 독립된 입력 카드로 묶어요. */}
        <span className="profile-step"><Icon name="user" /> 나를 알아가는 첫걸음</span> {/* 내부 단계 번호 대신 친근한 시작 안내를 보여줘요. */}
        <h2 id="profile-setup-title">나에게 맞는 제도를 찾아볼까요?</h2> {/* 정보를 입력하는 목적을 먼저 안내해요. */}
        <p className="profile-intro">기본 정보만 알려주세요. 지금의 생활에 맞춰 추천해 드릴게요.</p> {/* 입력 전에 부담이 적은 설명을 보여줘요. */}
        {list.length > 0 && <div className="profile-presets" role="group" aria-label="시연용 가상 프로필로 시작"> {/* 시연 동선을 위해 가상 프로필 버튼을 폼 위에 둬요. */}
            <p><span className="profile-preset-badge">시연용 가상 사례</span>가상 프로필로 바로 둘러볼 수 있어요. 실제 정보가 아니며, 이 계정에 프로필이 없을 때만 만들어져요.</p> {/* 가상 데이터임과 덮어쓰지 않음을 알려줘요. */}
            <div className="profile-preset-options">{list.map((preset) => <button type="button" className="button button-secondary" key={preset.id} disabled={busy} onClick={() => void start(preset.id)}><Icon name="sparkles" />{preset.label}</button>)}</div> {/* 서버가 준 라벨만 표시해요. */}
        </div>}
        {seed && <p className="profile-seeded"><Icon name="check" /> 가입할 때 알려주신 정보로 미리 채웠어요. 나머지만 골라 주세요.</p>}
        <form key={seed ? "seeded" : "blank"} onSubmit={submit} className="work-form"> {/* 기존 저장 함수를 그대로 연결해요. */}
            <fieldset className="profile-fields" disabled={busy}> {/* 저장하는 동안 모든 입력을 함께 잠가요. */}
                <label>닉네임<input name="nickname" defaultValue={nickname} placeholder="어떻게 불러드릴까요?" required minLength={2} maxLength={16} autoComplete="nickname" /></label> {/* 실명 대신 닉네임만 입력받아요. */}
                <label>생년월일<input name="birth_date" type="date" defaultValue={pre("birth_date")} required min="1900-01-01" max={new Date().toISOString().slice(0, 10)} /></label> {/* 기존 생년월일 범위를 유지해요. */}
                <ProfileChoice name="gender" label="성별" options={["여", "남"]} /> {/* 성별을 펼침 메뉴 대신 바로 선택해요. */}
                <div className="profile-section-label"><Icon name="home" /><span>어디에서 생활하고 계신가요?</span></div> {/* 거주지 입력 항목의 목적을 안내해요. */}
                <label>시도<select name="sido" defaultValue={pre("sido") ?? ""} required><option value="">지역을 선택해 주세요</option>{["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"].map((value) => <option key={value}>{value}</option>)}</select></label> {/* 지역 값은 기존 API 형식을 유지해요. */}
                <label>시군구<input name="sigungu" placeholder="예: 마포구" maxLength={40} required /></label> {/* 상세 주소 없이 시군구까지만 입력받아요. */}
                <div className="profile-section-label"><Icon name="family" /><span>지금의 생활을 알려주세요</span></div> {/* 가구와 생활 항목을 함께 묶어 보여줘요. */}
                <ProfileChoice name="marital_status" label="혼인 상태" options={["미혼", "예비부부", "신혼", "기혼", "이혼·사별"]} value={pre("marital_status")} /> {/* 혼인 상태를 한눈에 보고 선택해요. */}
                <label>자녀 수<input name="children_count" type="number" min={0} max={30} placeholder="0" defaultValue={pre("children_count")} required /></label> {/* 입력 전에는 자녀 수를 임의로 저장하지 않아요. */}
                <label>가구원 수<input name="household_size" type="number" min={1} max={50} placeholder="본인을 포함해 주세요" defaultValue={pre("household_size")} required /></label> {/* 기존 가구원 수 범위를 유지해요. */}
                <ProfileChoice name="employment_status" label="취업 상태" options={["재학", "구직", "재직", "자영업", "육아휴직", "기타"]} /> {/* 취업 상태도 선택 카드로 입력해요. */}
            </fieldset> {/* 기본 정보 입력 묶음을 마쳐요. */}
            <p className="profile-privacy"><Icon name="shield" />소득·건강 정보는 필요한 때 별도 동의 후 입력해 주세요.</p> {/* 민감정보는 현재 폼에서 받지 않는다고 안내해요. */}
            {busy && <LoadingState label="기본 정보를 저장하고 있습니다." compact />}{error && <p role="alert">{error}</p>} {/* 저장 실패가 있으면 입력값을 유지하며 안내해요. */}
            <button className="button button-primary profile-next" disabled={busy}>{busy ? "저장 중…" : <>다음으로<Icon name="arrow-right" /></>}</button> {/* 짧은 다음 이동 문구로 저장 후 추천 화면을 열어요. */}
        </form> {/* 기본 정보 폼을 마쳐요. */}
    </section>; // 실제 세션 계정에만 저장하며 가상 프리셋으로 덮어쓰지 않아요.
} // 최소 프로필 폼을 마쳐요.
