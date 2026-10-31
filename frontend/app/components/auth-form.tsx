"use client"; // 비밀번호 표시와 폼 안내가 사용자의 조작에 반응하게 해요.

import { useState, type FormEvent } from "react"; // 입력값을 잠시 기억하고 폼 제출 동작을 제어해요.
import Link from "next/link"; // 로그인과 회원가입 화면을 서로 연결해요.
import { Icon } from "./ui"; // 기존 서비스와 같은 선 아이콘을 사용해요.

type PasswordFieldProps = { // 두 화면에서 함께 쓰는 비밀번호 입력칸의 설정을 정해요.
    id: string; // 각 입력칸을 구분하는 고유한 이름이에요.
    label: string; // 입력칸 위에 보여줄 이름이에요.
    value: string; // 현재 입력한 값을 받아요.
    onChange: (value: string) => void; // 입력값이 바뀌면 부모 폼에 알려줘요.
    autoComplete: "current-password" | "new-password"; // 비밀번호 관리자가 입력칸의 목적을 알 수 있게 해요.
    hint?: string; // 입력칸 아래에 필요한 설명을 보여줘요.
    invalid?: boolean; // 비밀번호 확인이 맞지 않으면 오류 상태로 알려줘요.
}; // 비밀번호 입력 설정을 마쳐요.

function PasswordField({ id, label, value, onChange, autoComplete, hint, invalid = false }: PasswordFieldProps) { // 표시 전환 버튼이 있는 비밀번호 입력칸을 만들어요.
    const [visible, setVisible] = useState(false); // 비밀번호는 처음에 숨긴 상태로 보여줘요.
    return <div className="auth-field"><label className="auth-field-label" htmlFor={id}>{label}</label><div className="auth-input-wrap"><span className="auth-input-icon"><Icon name="lock" /></span><input className="auth-input" id={id} type={visible ? "text" : "password"} value={value} onChange={(event) => onChange(event.target.value)} placeholder={id === "auth-confirm-password" ? "비밀번호를 한 번 더 입력해 주세요" : "비밀번호를 입력해 주세요"} autoComplete={autoComplete} required minLength={autoComplete === "new-password" ? 8 : undefined} maxLength={128} aria-invalid={invalid || undefined} aria-describedby={hint ? `${id}-hint` : undefined} /><button type="button" className="auth-password-toggle" onClick={() => setVisible((previous) => !previous)} aria-label={`${label} ${visible ? "숨기기" : "보기"}`} aria-pressed={visible}><Icon name={visible ? "eye-off" : "eye"} /></button></div>{hint && <p id={`${id}-hint`} className={`auth-field-hint ${invalid ? "auth-field-error" : ""}`}>{hint}</p>}</div>; // 입력값은 이 화면에서만 사용하고 전송이나 저장에 쓰지 않아요.
} // 비밀번호 입력칸을 마쳐요.

export function AuthForm({ mode }: { mode: "login" | "signup" }) { // 같은 디자인으로 로그인과 회원가입 폼을 만들어요.
    const isSignup = mode === "signup"; // 현재 페이지가 회원가입인지 구분해요.
    const [email, setEmail] = useState(""); // 이메일은 화면을 벗어나기 전까지만 기억해요.
    const [nickname, setNickname] = useState(""); // 실명 대신 사용할 닉네임을 화면 안에서만 기억해요.
    const [password, setPassword] = useState(""); // 입력한 비밀번호를 서버나 저장소로 보내지 않아요.
    const [confirmation, setConfirmation] = useState(""); // 비밀번호를 같은 값으로 입력했는지 안내할 때만 사용해요.
    const [consent, setConsent] = useState(false); // 필수 동의의 화면 선택 상태만 기억해요.
    const [feedback, setFeedback] = useState(""); // 로그인이나 가입을 실제로 처리하지 않는다는 안내를 보여줘요.
    const [showConsent, setShowConsent] = useState(false); // 동의 항목의 설명을 펼칠지 기억해요.
    const [showHelp, setShowHelp] = useState(false); // 비밀번호 찾기 안내를 펼칠지 기억해요.
    const [emailTouched, setEmailTouched] = useState(false); // 이메일 칸에서 벗어난 적 있는지 기억해요.
    const [nicknameTouched, setNicknameTouched] = useState(false); // 닉네임 칸에서 벗어난 적 있는지 기억해요.
    const hasMismatch = isSignup && confirmation.length > 0 && password !== confirmation; // 두 비밀번호가 다를 때 입력칸 바로 아래에 알려줘요.
    const isEmailInvalid = emailTouched && email.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); // 이메일 형식이 잘못됐는지 확인해요.
    const isNicknameInvalid = isSignup && nicknameTouched && nickname.length > 0 && (nickname.length < 2 || nickname.length > 16); // 닉네임 길이가 범위를 벗어났는지 확인해요.
    const pwStrength = { min8: password.length >= 8, hasLetter: /[a-zA-Zㄱ-힣]/.test(password), hasNumber: /[0-9]/.test(password) }; // 비밀번호가 각 조건을 만족하는지 확인해요.

    function handleSubmit(event: FormEvent<HTMLFormElement>) { // 디자인 폼이 실제 인증 요청을 보내지 않도록 처리해요.
        event.preventDefault(); // 기본 폼 제출로 입력값이 주소에 붙거나 전송되는 것을 막아요.
        if (isSignup && password !== confirmation) { // 회원가입의 두 비밀번호가 다른 경우를 구분해요.
            setFeedback("비밀번호가 일치하지 않아요. 입력한 내용을 다시 확인해 주세요."); // 사용자가 고칠 입력칸을 알려줘요.
            return; // 일치하지 않으면 다음 안내로 넘어가지 않아요.
        } // 비밀번호 일치 안내를 마쳐요.
        if (isSignup && !consent) { // 필수 동의를 고르지 않은 상태를 구분해요.
            setFeedback("서비스 이용을 위한 필수 동의 항목을 확인해 주세요."); // 동의 항목이 필요하다는 안내를 보여줘요.
            return; // 동의하지 않았으면 다음 안내로 넘어가지 않아요.
        } // 동의 선택 안내를 마쳐요.
        setFeedback(isSignup ? "회원가입 화면 미리보기입니다. 계정은 생성되지 않았으며 입력한 정보는 저장하지 않았습니다." : "로그인 화면 미리보기입니다. 실제 로그인은 진행되지 않았으며 입력한 정보는 저장하지 않았습니다."); // 인증에 성공한 것처럼 표시하지 않고 현재 화면의 동작을 설명해요.
        setEmail(""); // 제출한 이메일을 화면 상태에서 비워요.
        setNickname(""); // 제출한 닉네임을 화면 상태에서 비워요.
        setPassword(""); // 제출한 비밀번호를 화면 상태에서 비워요.
        setConfirmation(""); // 비밀번호 확인 값도 함께 비워요.
        setConsent(false); // 실제 동의가 저장되지 않았으므로 선택 상태를 되돌려요.
    } // 디자인 폼의 제출 처리를 마쳐요.

    return ( // 입력칸과 주요 행동을 하나의 흰색 카드에 담아요.
        <section className="auth-form-card" aria-labelledby="auth-title"> {/* 현재 폼의 제목을 보조기기에도 알려줘요. */}
            <div className="auth-form-heading"><span className="auth-form-eyebrow">{isSignup ? "처음 만나는 나의 징검다리" : "다시 만나 반가워요"}</span><h1 id="auth-title" className="auth-form-title">{isSignup ? "회원가입" : "로그인"}</h1><p className="auth-form-description">{isSignup ? "작은 시작으로, 나에게 맞는 다음을 찾아보세요." : "나에게 맞는 제도와 다음 걸음을 이어가세요."}</p></div> {/* 각 화면의 목적을 짧은 존댓말로 안내해요. */}
            <div className="auth-notice"><Icon name="info" /><span>디자인 미리보기입니다. 실제 인증과 정보 저장은 진행되지 않습니다.</span></div> {/* 실제 계정 기능과 화면 디자인을 구분해요. */}
            <form className="auth-form" onSubmit={handleSubmit}> {/* 입력값을 서버로 보내는 주소는 연결하지 않아요. */}
                {isSignup && <div className="auth-field"><label className="auth-field-label" htmlFor="auth-nickname">닉네임</label><div className="auth-input-wrap"><span className="auth-input-icon"><Icon name="user" /></span><input className="auth-input" id="auth-nickname" value={nickname} onChange={(event) => setNickname(event.target.value)} onBlur={() => setNicknameTouched(true)} placeholder="어떤 이름으로 불러드릴까요?" autoComplete="nickname" minLength={2} maxLength={16} required aria-describedby="auth-nickname-hint" aria-invalid={isNicknameInvalid || undefined} /></div><p className={`auth-field-hint${isNicknameInvalid ? " auth-field-error" : ""}`} id="auth-nickname-hint">{isNicknameInvalid ? "2~16자 사이로 입력해 주세요." : "실명 대신 사용할 별명을 2~16자로 입력해 주세요."}</p></div>} {/* 회원가입에만 닉네임을 받고 실명은 요청하지 않아요. */}
                <div className="auth-field"><label className="auth-field-label" htmlFor="auth-email">이메일</label><div className="auth-input-wrap"><span className="auth-input-icon"><Icon name="mail" /></span><input className="auth-input" id="auth-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} onBlur={() => setEmailTouched(true)} placeholder="이메일 주소를 입력해 주세요" autoComplete="username" autoCapitalize="none" spellCheck={false} inputMode="email" maxLength={254} required aria-invalid={isEmailInvalid || undefined} aria-describedby={isEmailInvalid ? "auth-email-hint" : undefined} /></div>{isEmailInvalid && <p className="auth-field-hint auth-field-error" id="auth-email-hint">올바른 이메일 형식이 아니에요. (예: name@example.com)</p>}</div> {/* 이메일은 계정 입력칸으로만 사용하고 알림 수신에는 동의한 것으로 취급하지 않아요. */}
                <PasswordField id="auth-password" label="비밀번호" value={password} onChange={setPassword} autoComplete={isSignup ? "new-password" : "current-password"} hint={isSignup && password.length === 0 ? "8자 이상, 문자와 숫자를 포함해 주세요." : undefined} /> {/* 화면에 맞는 자동완성과 비밀번호 표시 전환을 제공해요. */}
                {isSignup && password.length > 0 && <ul className="auth-requirements" aria-label="비밀번호 조건"><li className={`auth-requirement${pwStrength.min8 ? " is-met" : ""}`}><Icon name="check" />8자 이상</li><li className={`auth-requirement${pwStrength.hasLetter ? " is-met" : ""}`}><Icon name="check" />문자 포함</li><li className={`auth-requirement${pwStrength.hasNumber ? " is-met" : ""}`}><Icon name="check" />숫자 포함</li></ul>} {/* 비밀번호를 입력하는 동안 충족한 조건을 파란색으로 보여줘요. */}
                {isSignup && <PasswordField id="auth-confirm-password" label="비밀번호 확인" value={confirmation} onChange={setConfirmation} autoComplete="new-password" hint={hasMismatch ? "비밀번호가 일치하지 않아요." : "같은 비밀번호를 한 번 더 입력해 주세요."} invalid={hasMismatch} />} {/* 회원가입에서는 비밀번호를 다시 입력하도록 안내해요. */}
                {isSignup ? <div className="auth-consent"><div className="auth-consent-row"><label className="auth-checkbox-label"><input className="auth-checkbox" type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required /><span><strong>[필수]</strong> 서비스 이용 및 개인정보 처리 안내 확인</span></label><button type="button" className="auth-inline-link" onClick={() => setShowConsent((previous) => !previous)} aria-expanded={showConsent} aria-controls="auth-consent-detail">{showConsent ? "접기" : "보기"}</button></div>{showConsent && <div id="auth-consent-detail" className="auth-consent-detail">현재는 동의 항목의 디자인 예시이며 실제 약관 동의를 수집하지 않습니다. 정식 서비스의 이용약관과 개인정보 처리 안내는 회원가입 기능 제공 전에 안내됩니다. 이메일 알림 수신과 소득·건강 등 민감정보 동의는 이 항목에 포함되지 않습니다.</div>}</div> : <div className="auth-form-options"><span>나의 다음 걸음을 이어서</span><button type="button" className="auth-inline-link" onClick={() => setShowHelp((previous) => !previous)} aria-expanded={showHelp} aria-controls="auth-password-help">비밀번호를 잊으셨나요?</button></div>} {/* 동의 항목과 비밀번호 도움말은 화면의 성격에 맞게 구분해요. */}
                {!isSignup && showHelp && <p id="auth-password-help" className="auth-consent-detail">비밀번호 재설정은 정식 로그인 기능이 제공되면 이용하실 수 있습니다. 현재 화면에서는 이메일을 발송하지 않습니다.</p>} {/* 없는 비밀번호 재설정 기능이 작동한 것처럼 표시하지 않아요. */}
                {feedback && <p className="auth-status" role="status" aria-live="polite">{feedback}</p>} {/* 제출 후 안내를 화면과 보조기기에 함께 전달해요. */}
                <button className="button button-primary auth-submit" type="submit">{isSignup ? "가입하고 시작하기" : "로그인"}<Icon name="arrow-right" /></button> {/* 선택한 화면에 맞는 주요 제출 버튼을 보여줘요. */}
            </form> {/* 로그인과 회원가입 입력 영역을 마쳐요. */}
            <div className="auth-divider"><span>또는</span></div> {/* 계정 입력과 화면 둘러보기를 구분해요. */}
            <Link className="button button-secondary auth-guest" href="/my">로그인 없이 먼저 둘러보기<Icon name="chevron-right" /></Link> {/* 입력 없이 기존 시연 화면으로 이동할 수 있어요. */}
            <p className="auth-switch">{isSignup ? "이미 징검다리 계정이 있으신가요?" : "징검다리가 처음이신가요?"}<Link href={isSignup ? "/login" : "/signup"}>{isSignup ? "로그인" : "회원가입"}<Icon name="arrow-right" /></Link></p> {/* 두 계정 화면을 서로 연결해요. */}
        </section> // 폼 카드의 구성을 마쳐요.
    ); // 폼 화면을 반환해요.
} // 로그인과 회원가입 공통 폼을 마쳐요.
