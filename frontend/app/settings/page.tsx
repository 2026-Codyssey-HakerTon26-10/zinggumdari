"use client"; // 서버에서 확인한 계정의 로그아웃·탈퇴를 처리해요.
import { useEffect, useState } from "react"; // 요청 중 중복 클릭과 실패 안내를 관리해요.
import { useRouter } from "next/navigation"; // 성공한 뒤에만 로그인 화면으로 이동해요.
import Link from "next/link"; // 내 정보 설정으로 이동해요.
import { SiteHeader, SiteFooter } from "../components/ui"; // 공통 메뉴를 사용해요.
import { api, me, message, type Me } from "../lib/service-api"; // 계정 삭제는 DELETE /auth/me만 사용해요.
import "../my/workspace.css"; // 같은 흰색 설정 스타일이에요.
export default function Settings() { // 계정이 없는 화면에서 삭제 버튼을 표시하지 않아요.
    const router = useRouter(); const [account, setAccount] = useState<Me | null>(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); // 계정 응답과 처리 상태예요.
    useEffect(() => { const controller = new AbortController(); void me(controller.signal).then(setAccount).catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); }); return () => controller.abort(); }, []); // 새로 들어올 때마다 서버 세션을 확인해요.
    async function action(remove: boolean) { // 탈퇴와 로그아웃을 분리해요.
        if (!account || busy) return; setBusy(true); setError(""); try { const current = await me(); if (current.account_id !== account.account_id) { setAccount(current); setError("다른 계정으로 변경되었습니다. 현재 계정을 확인한 뒤 다시 선택해 주세요."); return; } await api(remove ? "/auth/me" : "/auth/logout", { method: remove ? "DELETE" : "POST" }); if (remove) { try { localStorage.removeItem(`zing_account_${account.account_id}`); localStorage.removeItem("zing_nickname"); } catch { /* 저장소 차단이 서버 삭제 성공을 바꾸지는 않아요. */ } } setAccount(null); router.replace("/login"); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } // 서버 실패 시 계정과 화면을 유지해 재시도할 수 있어요.
    } // 계정 동작을 마쳐요.
    return <><SiteHeader active="my" /><main id="main-content" className="container work-main"><Link href="/my">← 내 징검다리</Link><h1>설정</h1>{error && <p role="alert">{error}</p>}{account ? <><section className="work-panel"><h2>현재 계정</h2><p>{account.email}</p><div className="work-actions"><Link href="/my/alerts">알림·민감정보 동의</Link><Link href="/my/parents">부모님 정보·동의</Link><button type="button" className="button button-secondary" disabled={busy} onClick={() => void action(false)}>로그아웃</button></div></section><section className="work-panel"><h2>회원 탈퇴</h2><p>아래 버튼을 한 번 누르면 계정·모든 세션·프로필·알림·업로드한 공고가 삭제됩니다. 삭제한 정보는 복구할 수 없습니다.</p><p>현재 계정: {account.email}</p><button type="button" className="button button-secondary" disabled={busy} onClick={() => void action(true)}>{busy ? "처리 중…" : "회원 탈퇴하고 모든 정보 삭제"}</button></section></> : !error ? <p role="status">현재 계정을 확인하고 있습니다.</p> : <Link href="/login">다시 로그인</Link>}</main><SiteFooter /></>; // 추가 확인창 없이 명시적인 삭제 버튼으로 한 번에 요청해요.
} // 설정 화면을 마쳐요.
