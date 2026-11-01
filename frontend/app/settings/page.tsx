"use client"; // 서버에서 확인한 계정의 로그아웃·탈퇴를 처리해요.
import { LoadingState } from "../components/loading-state"; // 요청 중에는 회전 표시와 처리 안내를 보여줘요.
import { useEffect, useState } from "react"; // 요청 중 중복 클릭과 실패 안내를 관리해요.
import { useRouter } from "next/navigation"; // 성공한 뒤에만 로그인 화면으로 이동해요.
import Link from "next/link"; // 내 정보 설정으로 이동해요.
import { Icon, SiteHeader, SiteFooter } from "../components/ui"; // 설정 항목을 알아보기 쉬운 아이콘으로 구분해요.
import { api, me, message, type Me } from "../lib/service-api"; // 계정 삭제는 DELETE /auth/me만 사용해요.
import "../my/workspace.css"; // 같은 흰색 설정 스타일이에요.
import "./settings.css"; // 계정과 정보 설정을 카드 형태로 정리해요.
export default function Settings() { // 계정이 없는 화면에서 삭제 버튼을 표시하지 않아요.
    const router = useRouter(); const [account, setAccount] = useState<Me | null>(null); const [error, setError] = useState(""); const [pending, setPending] = useState<"logout" | "delete" | null>(null); const busy = pending !== null; // 진행 중인 작업의 이름을 정확히 보여줘요.
    useEffect(() => { const controller = new AbortController(); void me(controller.signal).then((current) => { if (!controller.signal.aborted) setAccount(current); }).catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); }); return () => controller.abort(); }, []); // 화면을 떠난 뒤에는 계정 정보를 다시 표시하지 않아요.
    async function action(remove: boolean) { // 탈퇴와 로그아웃을 분리해요.
        if (!account || busy) return; setPending(remove ? "delete" : "logout"); setError(""); try { const current = await me(); if (current.account_id !== account.account_id) { setAccount(current); setError("다른 계정으로 변경되었습니다. 현재 계정을 확인한 뒤 다시 선택해 주세요."); return; } await api(remove ? "/auth/me" : "/auth/logout", { method: remove ? "DELETE" : "POST" }); try { localStorage.removeItem(`zing_account_${account.account_id}`); localStorage.removeItem("zing_nickname"); } catch { /* 브라우저 저장소가 차단되어도 서버에서 끝난 작업은 유지해요. */ } setAccount(null); router.replace("/login"); router.refresh(); } catch (cause) { setError(message(cause)); } finally { setPending(null); } // 로그아웃할 때도 이전 계정의 브라우저 저장 정보를 지우고 서버 실패 시에는 유지해요.
    } // 계정 동작을 마쳐요.
    return <><SiteHeader active="my" /><main id="main-content" className="container work-main settings-main"> {/* 설정 화면의 너비와 간격을 맞춰요. */}
        <Link className="settings-back" href="/my"><Icon name="chevron-left" />나의 추천</Link> {/* 추천으로 쉽게 돌아갈 수 있어요. */}
        <header className="settings-heading"><span className="settings-eyebrow">나의 징검다리</span><h1>내 정보와 설정</h1><p>알림부터 정보 관리까지, 필요한 설정을 한곳에서 바꿔보세요.</p></header> {/* 설정에서 할 수 있는 일을 먼저 안내해요. */}
        {busy && <LoadingState label={pending === "delete" ? "계정 정보를 삭제하고 있습니다." : "로그아웃하고 있습니다."} compact />}{error && <p role="alert">{error}</p>} {/* 요청이 실패하면 오류를 유지해요. */}
        {account ? <> {/* 서버에서 확인한 계정이 있을 때만 계정 작업을 보여줘요. */}
            <section className="work-panel settings-account"><span className="settings-account-icon"><Icon name="user" /></span><div><h2>{account.nickname || "현재 로그인한 계정"}</h2><p>{account.email}</p></div><button type="button" className="button button-secondary" disabled={busy} onClick={() => void action(false)}><Icon name="log-out" />{pending === "logout" ? "로그아웃 중…" : "로그아웃"}</button></section> {/* 다른 사람의 계정을 조작하지 않도록 현재 계정을 알려줘요. */}
            <section className="settings-preferences" aria-label="정보와 알림 관리"> {/* 자주 찾는 설정을 두 카드로 묶어요. */}
                <Link className="settings-option" href={account.user_id ? "/my/alerts" : "/my"}><span className="settings-option-icon"><Icon name="bell" /></span><span><strong>맞춤 알림과 내 정보</strong><small>주거·소득·청약 정보와 알림 수신을 관리해요.</small></span><Icon name="chevron-right" /></Link> {/* 기본 정보가 없는 계정은 입력 단계로 안내해요. */}
                <Link className="settings-option" href={account.user_id ? "/my/parents" : "/my?subject=parent"}><span className="settings-option-icon"><Icon name="family" /></span><span><strong>부모님 정보</strong><small>부모님 정보와 별도 동의를 관리해요.</small></span><Icon name="chevron-right" /></Link> {/* 부모님 동의와 정보 입력을 독립적으로 안내해요. */}
            </section> {/* 정보 관리 카드를 마쳐요. */}
            <section className="settings-privacy"><Icon name="shield" /><p>소득·건강 등 민감정보의 저장 동의는 언제든 설정에서 바꿀 수 있어요. 동의를 해제하고 저장하면 해당 정보가 삭제돼요.</p></section> {/* 삭제 효과가 저장 시점에 적용된다는 점을 정확하게 알려줘요. */}
            <section className="work-panel settings-delete"><h2>회원 탈퇴</h2><p>탈퇴하면 계정·모든 세션·프로필·알림·업로드한 공고가 함께 삭제돼요. 삭제한 정보는 복구할 수 없어요.</p><p className="settings-delete-account">삭제할 계정: {account.email}</p><button type="button" className="button settings-delete-button" disabled={busy} onClick={() => void action(true)}><Icon name="trash" />{pending === "delete" ? "정보 삭제 중…" : "회원 탈퇴하고 모든 정보 삭제"}</button></section> {/* 삭제 범위가 명확한 한 번의 버튼으로 탈퇴를 요청해요. */}
        </> : !error ? <LoadingState label="계정 정보를 불러오고 있습니다." /> : <Link className="button button-primary" href="/login">다시 로그인</Link>} {/* 계정 확인이 끝나기 전에는 삭제 버튼을 표시하지 않아요. */}
    </main><SiteFooter /></>; // 서버에서 성공한 작업만 반영해요.
} // 설정 화면을 마쳐요.
