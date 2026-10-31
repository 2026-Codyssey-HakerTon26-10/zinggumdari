"use client"; // 비밀번호 표시와 폼 안내가 사용자의 조작에 반응하게 해요.

import { useState, useRef, type FormEvent, type ReactNode } from "react"; // 입력값을 잠시 기억하고 폼 제출 동작을 제어해요.
import { useRouter } from "next/navigation"; // 인증 성공 시 다음 화면으로 이동해요.
import Link from "next/link"; // 로그인과 회원가입 화면을 서로 연결해요.
import { Icon } from "./ui"; // 기존 서비스와 같은 선 아이콘을 사용해요.
import { signup as apiSignup, login as apiLogin, AuthError, setAccountData } from "../lib/auth"; // 백엔드 인증 API를 호출해요.

type PasswordFieldProps = { // 두 화면에서 함께 쓰는 비밀번호 입력칸의 설정을 정해요.
    id: string; // 각 입력칸을 구분하는 고유한 이름이에요.
    label: string; // 입력칸 위에 보여줄 이름이에요.
    value: string; // 현재 입력한 값을 받아요.
    onChange: (value: string) => void; // 입력값이 바뀌면 부모 폼에 알려줘요.
    autoComplete: "current-password" | "new-password"; // 비밀번호 관리자가 입력칸의 목적을 알 수 있게 해요.
    hint?: string; // 입력칸 아래에 필요한 설명을 보여줘요.
    describedBy?: string; // 비밀번호 조건 안내의 식별자를 입력칸에 연결해요.
    invalid?: boolean; // 비밀번호 확인이 맞지 않으면 오류 상태로 알려줘요.
}; // 비밀번호 입력 설정을 마쳐요.

function PasswordField({ id, label, value, onChange, autoComplete, hint, describedBy, invalid = false }: PasswordFieldProps) { // 표시 전환 버튼이 있는 비밀번호 입력칸을 만들어요.
    const [visible, setVisible] = useState(false); // 비밀번호는 처음에 숨긴 상태로 보여줘요.
    return <div className="auth-field"><label className="auth-field-label" htmlFor={id}>{label}</label><div className="auth-input-wrap"><span className="auth-input-icon"><Icon name="lock" /></span><input className="auth-input" id={id} type={visible ? "text" : "password"} value={value} onChange={(event) => onChange(event.target.value)} placeholder={id === "auth-confirm-password" ? "비밀번호를 한 번 더 입력해 주세요" : "비밀번호를 입력해 주세요"} autoComplete={autoComplete} required minLength={autoComplete === "new-password" ? 8 : undefined} maxLength={128} aria-invalid={invalid || undefined} aria-describedby={[hint ? `${id}-hint` : "", describedBy].filter(Boolean).join(" ") || undefined} /><button type="button" className="auth-password-toggle" onClick={() => setVisible((previous) => !previous)} aria-label={`${label} ${visible ? "숨기기" : "보기"}`} aria-pressed={visible}><Icon name={visible ? "eye-off" : "eye"} /></button></div>{hint && <p id={`${id}-hint`} className={`auth-field-hint ${invalid ? "auth-field-error" : ""}`}>{hint}</p>}</div>; // 입력값은 이 화면에서만 사용하고 전송이나 저장에 쓰지 않아요.
} // 비밀번호 입력칸을 마쳐요.

// 동의 항목 키 타입 — 4개 항목을 구분해요.
type ConsentKey = "terms" | "privacy" | "email" | "sensitive";

// 동의 항목 하나를 체크박스·보기/접기 버튼·상세 내용으로 구성해요.
function ConsentItem({ id, label, required, checked, onCheck, open, onToggle, children }: { id: string; label: string; required: boolean; checked: boolean; onCheck: (v: boolean) => void; open: boolean; onToggle: () => void; children: ReactNode }) {
    return (
        <div className="auth-consent-item"> {/* 동의 항목 하나를 묶어요. */}
            <div className="auth-consent-row"> {/* 체크박스 행과 보기 버튼을 나란히 배치해요. */}
                <label className="auth-checkbox-label"> {/* 체크박스와 문구를 함께 클릭할 수 있게 해요. */}
                    <input className="auth-checkbox" type="checkbox" id={id} checked={checked} onChange={(e) => onCheck(e.target.checked)} />
                    <span><strong>{required ? "[필수]" : "[선택]"}</strong> {label}</span>
                </label>
                <button type="button" className="auth-inline-link" onClick={onToggle} aria-expanded={open} aria-controls={`${id}-detail`}>{open ? "접기" : "보기"}</button>
            </div>
            {open && ( // 펼쳤을 때만 상세 내용을 보여줘요.
                <div id={`${id}-detail`} className="auth-consent-detail-panel">
                    {children}
                </div>
            )}
        </div>
    );
} // 동의 항목 컴포넌트를 마쳐요.

export function AuthForm({ mode }: { mode: "login" | "signup" }) { // 같은 디자인으로 로그인과 회원가입 폼을 만들어요.
    const isSignup = mode === "signup"; // 현재 페이지가 회원가입인지 구분해요.
    const router = useRouter(); // 인증 성공 후 내 징검다리 화면으로 이동해요.
    const [email, setEmail] = useState(""); // 이메일은 서버에 전송한 뒤 상태에서 삭제해요.
    const [nickname, setNickname] = useState(""); // 실명 대신 사용할 닉네임이에요. 회원가입 성공 시 로컬 스토리지에 저장해요.
    const [password, setPassword] = useState(""); // 비밀번호는 서버로 전송한 뒤 즉시 상태에서 삭제해요.
    const [confirmation, setConfirmation] = useState(""); // 비밀번호 일치 여부를 확인할 때만 사용해요.
    // 4개 동의 항목 상태 — terms(이용약관)·privacy(개인정보)는 필수, email·sensitive는 선택이에요.
    const [consents, setConsents] = useState<Record<ConsentKey, boolean>>({ terms: false, privacy: false, email: false, sensitive: false });
    // 각 항목의 상세 내용 펼침 상태예요.
    const [consentDetail, setConsentDetail] = useState<Record<ConsentKey, boolean>>({ terms: false, privacy: false, email: false, sensitive: false });
    const [feedback, setFeedback] = useState(""); // 입력 오류나 서버 오류를 화면에 표시해요.
    const [loading, setLoading] = useState(false); // API 요청 중에 버튼을 비활성화해요.
    const [showHelp, setShowHelp] = useState(false); // 비밀번호 찾기 안내를 펼칠지 기억해요.
    const [emailTouched, setEmailTouched] = useState(false); // 이메일 칸에서 벗어난 적 있는지 기억해요.
    const [nicknameTouched, setNicknameTouched] = useState(false); // 닉네임 칸에서 벗어난 적 있는지 기억해요.
    const allCheckRef = useRef<HTMLInputElement>(null); // 전체 동의 체크박스의 불확정 상태를 제어해요.
    const hasMismatch = isSignup && confirmation.length > 0 && password !== confirmation; // 두 비밀번호가 다를 때 입력칸 바로 아래에 알려줘요.
    const isEmailInvalid = emailTouched && email.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); // 이메일 형식이 잘못됐는지 확인해요.
    const isNicknameInvalid = isSignup && nicknameTouched && nickname.length > 0 && (nickname.length < 2 || nickname.length > 16); // 닉네임 길이가 범위를 벗어났는지 확인해요.
    const pwStrength = { min8: password.length >= 8, hasLetter: /[a-zA-Zㄱ-힣]/.test(password), hasNumber: /[0-9]/.test(password) }; // 비밀번호가 각 조건을 만족하는지 확인해요.
    // 전체 동의 상태 계산 — 4개 모두 체크됐는지, 일부만 체크됐는지 판단해요.
    const allChecked = Object.values(consents).every(Boolean);
    const someChecked = Object.values(consents).some(Boolean) && !allChecked;
    const requiredConsented = consents.terms && consents.privacy; // 필수 2개가 모두 동의됐는지 확인해요.

    // 전체 동의 체크박스의 불확정(indeterminate) 상태를 DOM에 직접 반영해요.
    if (allCheckRef.current) allCheckRef.current.indeterminate = someChecked;

    // 전체 동의 또는 전체 해제를 한 번에 적용해요.
    function toggleAll(checked: boolean) {
        setConsents({ terms: checked, privacy: checked, email: checked, sensitive: checked });
    } // 전체 동의 토글을 마쳐요.

    // 개별 항목을 바꿀 때 key와 value만 받아 안전하게 갱신해요.
    function toggleOne(key: ConsentKey, checked: boolean) {
        setConsents((prev) => ({ ...prev, [key]: checked }));
    } // 개별 동의 토글을 마쳐요.

    // 상세 내용 펼침/접기를 한 항목씩 토글해요.
    function toggleDetail(key: ConsentKey) {
        setConsentDetail((prev) => ({ ...prev, [key]: !prev[key] }));
    } // 상세 보기 토글을 마쳐요.

    async function handleSubmit(event: FormEvent<HTMLFormElement>) { // 폼을 제출할 때 백엔드 인증 API를 호출해요.
        event.preventDefault(); // 기본 폼 제출로 입력값이 주소에 붙거나 전송되는 것을 막아요.
        if (isSignup && (!pwStrength.min8 || !pwStrength.hasLetter || !pwStrength.hasNumber)) { // 비밀번호 조건을 서버에 보내기 전에 먼저 확인해요.
            setFeedback("비밀번호는 8자 이상이며 문자와 숫자를 포함해야 해요.");
            return;
        }
        if (isSignup && password !== confirmation) { // 두 비밀번호가 다르면 서버에 보내지 않아요.
            setFeedback("비밀번호가 일치하지 않아요. 입력한 내용을 다시 확인해 주세요.");
            return;
        }
        if (isSignup && !requiredConsented) { // 필수 동의(이용약관·개인정보)가 없으면 가입 요청을 보내지 않아요.
            setFeedback("서비스 이용을 위한 필수 동의 항목(이용약관, 개인정보 수집·이용)을 확인해 주세요.");
            return;
        }
        setLoading(true); // API 요청 중 버튼을 비활성화해요.
        setFeedback(""); // 이전 오류 메시지를 지워요.
        try {
            if (isSignup) {
                const data = await apiSignup(email, password); // 계정을 생성하고 세션 쿠키를 발급받아요.
                // 닉네임과 선택 동의(이메일·민감정보)를 계정 ID별 키로 저장해요. 프로필 연결 전 임시 저장이에요.
                setAccountData(data.account_id, { nickname: nickname.trim(), consents });
            } else {
                await apiLogin(email, password); // 이메일·비밀번호를 인증하고 세션 쿠키를 받아요.
            }
            router.push("/my"); // 인증 성공 후 내 징검다리 화면으로 이동해요.
        } catch (err) {
            setFeedback(err instanceof AuthError ? err.message : "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
            setLoading(false); // 오류 시 다시 시도할 수 있도록 버튼을 활성화해요.
        }
        // 성공 시 router.push 후 컴포넌트가 언마운트되므로 setLoading(false)를 생략해요.
    } // 인증 요청 처리를 마쳐요.

    return ( // 입력칸과 주요 행동을 하나의 흰색 카드에 담아요.
        <section className="auth-form-card" aria-labelledby="auth-title"> {/* 현재 폼의 제목을 보조기기에도 알려줘요. */}
            <div className="auth-form-heading"><span className="auth-form-eyebrow">{isSignup ? "처음 만나는 나의 징검다리" : "다시 만나 반가워요"}</span><h1 id="auth-title" className="auth-form-title">{isSignup ? "회원가입" : "로그인"}</h1><p className="auth-form-description">{isSignup ? "작은 시작으로, 나에게 맞는 다음을 찾아보세요." : "나에게 맞는 제도와 다음 걸음을 이어가세요."}</p></div> {/* 각 화면의 목적을 짧은 존댓말로 안내해요. */}
            <form className="auth-form" onSubmit={handleSubmit}> {/* 폼 제출 시 백엔드 인증 API를 호출해요. */}
                {isSignup && <div className="auth-field"><label className="auth-field-label" htmlFor="auth-nickname">닉네임</label><div className="auth-input-wrap"><span className="auth-input-icon"><Icon name="user" /></span><input className="auth-input" id="auth-nickname" value={nickname} onChange={(event) => setNickname(event.target.value)} onBlur={() => setNicknameTouched(true)} placeholder="어떤 이름으로 불러드릴까요?" autoComplete="nickname" minLength={2} maxLength={16} required aria-describedby="auth-nickname-hint" aria-invalid={isNicknameInvalid || undefined} /></div><p className={`auth-field-hint${isNicknameInvalid ? " auth-field-error" : ""}`} id="auth-nickname-hint">{isNicknameInvalid ? "2~16자 사이로 입력해 주세요." : "실명 대신 사용할 별명을 2~16자로 입력해 주세요."}</p></div>} {/* 회원가입에만 닉네임을 받고 실명은 요청하지 않아요. */}
                <div className="auth-field"><label className="auth-field-label" htmlFor="auth-email">이메일</label><div className="auth-input-wrap"><span className="auth-input-icon"><Icon name="mail" /></span><input className="auth-input" id="auth-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} onBlur={() => setEmailTouched(true)} placeholder="이메일 주소를 입력해 주세요" autoComplete="username" autoCapitalize="none" spellCheck={false} inputMode="email" maxLength={254} required aria-invalid={isEmailInvalid || undefined} aria-describedby={isEmailInvalid ? "auth-email-hint" : undefined} /></div>{isEmailInvalid && <p className="auth-field-hint auth-field-error" id="auth-email-hint">올바른 이메일 형식이 아니에요. (예: name@example.com)</p>}</div> {/* 이메일은 계정 입력칸으로만 사용하고 알림 수신에는 동의한 것으로 취급하지 않아요. */}
                <PasswordField id="auth-password" label="비밀번호" value={password} onChange={setPassword} autoComplete={isSignup ? "new-password" : "current-password"} hint={isSignup ? "8자 이상, 문자와 숫자를 포함해 주세요." : undefined} describedBy={isSignup ? "auth-password-requirements" : undefined} /> {/* 화면에 맞는 자동완성과 비밀번호 표시 전환을 제공해요. */}
                {isSignup && <ul id="auth-password-requirements" className="auth-requirements" aria-label="비밀번호 조건">{[{ label: "8자 이상", met: pwStrength.min8 }, { label: "문자 포함", met: pwStrength.hasLetter }, { label: "숫자 포함", met: pwStrength.hasNumber }].map((item) => <li className={`auth-requirement${item.met ? " is-met" : ""}`} key={item.label}><Icon name="check" />{item.label}: {item.met ? "충족" : "미충족"}</li>)}</ul>} {/* 색상 외에도 상태를 글자로 표시하고 입력칸에 연결해요. */}
                {isSignup && <PasswordField id="auth-confirm-password" label="비밀번호 확인" value={confirmation} onChange={setConfirmation} autoComplete="new-password" hint={hasMismatch ? "비밀번호가 일치하지 않아요." : "같은 비밀번호를 한 번 더 입력해 주세요."} invalid={hasMismatch} />} {/* 회원가입에서는 비밀번호를 다시 입력하도록 안내해요. */}

                {isSignup ? (
                    // 회원가입 동의 섹션 — 전체 동의 + 필수 2개 + 선택 2개로 구성해요.
                    <div className="auth-consent" role="group" aria-label="이용 동의">
                        {/* 전체 동의 행 — 선택 항목까지 포함해요. */}
                        <div className="auth-consent-all">
                            <label className="auth-checkbox-label auth-checkbox-label--all">
                                <input className="auth-checkbox" type="checkbox" ref={allCheckRef} checked={allChecked} onChange={(e) => toggleAll(e.target.checked)} aria-label="전체 동의 (선택 항목 포함)" />
                                <span className="auth-consent-all-text">전체 동의 <em className="auth-consent-all-sub">선택 항목 포함</em></span>
                            </label>
                        </div>
                        <div className="auth-consent-divider" role="separator" aria-hidden="true" /> {/* 전체 동의와 개별 항목을 회색 선으로 구분해요. */}

                        {/* [필수] 서비스 이용약관 */}
                        <ConsentItem id="consent-terms" label="서비스 이용약관 동의" required checked={consents.terms} onCheck={(v) => toggleOne("terms", v)} open={consentDetail.terms} onToggle={() => toggleDetail("terms")}>
                            <p className="auth-consent-detail-desc">징검다리는 생애주기에 맞는 공공 제도를 미리 알려주는 추천 서비스입니다. 공공기관이 운영하는 서비스가 아닙니다.</p>
                            <table className="auth-consent-table">
                                <tbody>
                                    <tr><th>서비스 범위</th><td>공공 제도 자격 모의 판정, 타임라인 안내, 알림(선택 동의 시)</td></tr>
                                    <tr><th>판정 고지</th><td>모든 판정은 참고용 모의 판정입니다. 실제 자격 여부는 접수 기관 심사로 결정됩니다.</td></tr>
                                    <tr><th>대출 범위</th><td>기금 대출(버팀목·디딤돌) 자격 판정까지만 안내합니다. 금융사 상품·금리·신청 링크는 제공하지 않습니다.</td></tr>
                                    <tr><th>정보 이용</th><td>입력한 정보는 제도 추천 외 목적으로 사용하지 않습니다.</td></tr>
                                </tbody>
                            </table>
                        </ConsentItem>

                        {/* [필수] 개인정보 수집·이용 동의 (기본) */}
                        <ConsentItem id="consent-privacy" label="개인정보 수집·이용 동의" required checked={consents.privacy} onCheck={(v) => toggleOne("privacy", v)} open={consentDetail.privacy} onToggle={() => toggleDetail("privacy")}>
                            <table className="auth-consent-table">
                                <tbody>
                                    <tr><th>수집 항목</th><td>무작위 식별자(자동 생성), 닉네임</td></tr>
                                    <tr><th>수집 목적</th><td>프로필 저장, 생애주기 맞춤 제도 추천</td></tr>
                                    <tr><th>보유 기간</th><td>회원 탈퇴 즉시 삭제</td></tr>
                                    <tr><th>동의 거부 시</th><td>서비스 이용이 불가합니다.</td></tr>
                                </tbody>
                            </table>
                            <p className="auth-consent-detail-note">실명·전화번호·주민번호는 수집하지 않습니다.</p>
                        </ConsentItem>

                        {/* [선택] 이메일 알림 수신 동의 */}
                        <ConsentItem id="consent-email" label="이메일 알림 수신 동의" required={false} checked={consents.email} onCheck={(v) => toggleOne("email", v)} open={consentDetail.email} onToggle={() => toggleDetail("email")}>
                            <table className="auth-consent-table">
                                <tbody>
                                    <tr><th>수집 항목</th><td>이메일 주소</td></tr>
                                    <tr><th>수집 목적</th><td>새 공고·기한·맞춤 알림 발송</td></tr>
                                    <tr><th>보유 기간</th><td>알림 수신 해제 또는 탈퇴 즉시 삭제</td></tr>
                                    <tr><th>동의 거부 시</th><td>이메일 알림을 받지 못합니다. 서비스 이용에는 영향이 없습니다.</td></tr>
                                </tbody>
                            </table>
                        </ConsentItem>

                        {/* [선택] 민감정보 수집·이용 동의 */}
                        <ConsentItem id="consent-sensitive" label="민감정보 수집·이용 동의" required={false} checked={consents.sensitive} onCheck={(v) => toggleOne("sensitive", v)} open={consentDetail.sensitive} onToggle={() => toggleDetail("sensitive")}>
                            <table className="auth-consent-table">
                                <tbody>
                                    <tr><th>수집 항목</th><td>소득 정보(만원 단위), 건강 정보(장기요양등급·장애 등록 여부·임신 여부), 수급 여부, 차상위계층 여부</td></tr>
                                    <tr><th>수집 목적</th><td>소득·건강 조건이 포함된 제도의 자격 모의 판정</td></tr>
                                    <tr><th>보유 기간</th><td>동의 철회 또는 탈퇴 즉시 삭제</td></tr>
                                    <tr><th>동의 거부 시</th><td>민감 조건 제도 판정에서 해당 항목이 제외됩니다. 소득·건강 무관 제도는 계속 이용 가능합니다.</td></tr>
                                </tbody>
                            </table>
                            <p className="auth-consent-detail-note">민감정보는 별도 동의 시에만 저장되며, 판정 시 원값만 보관하고 % 환산은 판정 때 계산합니다.</p>
                        </ConsentItem>
                    </div>
                ) : (
                    // 로그인 화면에는 비밀번호 찾기 보조 안내만 표시해요.
                    <div className="auth-form-options"><span>나의 다음 걸음을 이어서</span><button type="button" className="auth-inline-link" onClick={() => setShowHelp((previous) => !previous)} aria-expanded={showHelp} aria-controls="auth-password-help">비밀번호를 잊으셨나요?</button></div>
                )}
                {!isSignup && showHelp && <p id="auth-password-help" className="auth-consent-detail-panel auth-consent-detail-panel--login">비밀번호 재설정은 아직 지원하지 않습니다. 이메일을 발송하지 않습니다.</p>} {/* 없는 비밀번호 재설정 기능이 작동한 것처럼 표시하지 않아요. */}
                {feedback && <p className="auth-status" role="status" aria-live="polite">{feedback}</p>} {/* 제출 후 안내를 화면과 보조기기에 함께 전달해요. */}
                <button className="button button-primary auth-submit" type="submit" disabled={loading} aria-busy={loading}>{loading ? (isSignup ? "가입하는 중…" : "로그인 중…") : (isSignup ? "가입하고 시작하기" : "로그인")}{!loading && <Icon name="arrow-right" />}</button> {/* 요청 중에는 버튼을 비활성화하고 상태를 글자로 알려줘요. */}
            </form> {/* 로그인과 회원가입 입력 영역을 마쳐요. */}
            <div className="auth-divider"><span>또는</span></div> {/* 계정 입력과 화면 둘러보기를 구분해요. */}
            <Link className="button button-secondary auth-guest" href="/my">가상 사례로 화면 둘러보기<Icon name="chevron-right" /></Link> {/* 입력 없이 기존 시연 화면으로 이동할 수 있어요. */}
            <p className="auth-switch">{isSignup ? "이미 징검다리 계정이 있으신가요?" : "징검다리가 처음이신가요?"}<Link href={isSignup ? "/login" : "/signup"}>{isSignup ? "로그인" : "회원가입"}<Icon name="arrow-right" /></Link></p> {/* 두 계정 화면을 서로 연결해요. */}
        </section> // 폼 카드의 구성을 마쳐요.
    ); // 폼 화면을 반환해요.
} // 로그인과 회원가입 공통 폼을 마쳐요.
