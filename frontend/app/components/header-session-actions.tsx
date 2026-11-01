"use client"; // 페이지를 옮길 때 서버 세션에 맞는 계정 메뉴를 보여줘요.
import { useEffect, useId, useRef, useState, type ReactNode } from "react"; // 계정 확인 결과, 펼침 메뉴 상태, 메뉴 영역을 관리해요.
import Link from "next/link"; // 계정과 추천 화면으로 이동해요.
import { LoadingState } from "./loading-state"; // 계정 확인 중임을 메뉴에서도 알려줘요.
import { usePathname } from "next/navigation"; // 현재 화면이 바뀌면 계정 상태를 다시 확인해요.
import { me, ServiceError } from "../lib/service-api"; // 브라우저 저장소 대신 서버 세션을 확인해요.
type Status = "signed_in" | "signed_out" | "unknown" | "loading"; // 연결 실패를 로그아웃으로 오해하지 않도록 구분해요.
type Props = { navigation: ReactNode; menuIcon: ReactNode; closeIcon: ReactNode; arrowIcon: ReactNode }; // 메뉴 링크와 아이콘을 바깥에서 받아 공통 UI와 순환 참조하지 않아요.
export function HeaderSessionActions({ navigation, menuIcon, closeIcon, arrowIcon }: Props) { // 데스크톱과 모바일에서 하나의 세션 결과를 함께 써요.
    const pathname = usePathname(); // 이동한 화면을 기준으로 세션 결과를 구분해요.
    const [checked, setChecked] = useState<{ pathname: string | null; status: Status }>({ pathname: null, status: "loading" }); // 서버 확인 전에는 가입이나 로그인을 단정하지 않아요.
    const status = checked.pathname === pathname ? checked.status : "loading"; // 다른 화면에서 받은 이전 계정 결과를 잠시 숨겨요.
    const [menu, setMenu] = useState<{ open: boolean; pathname: string | null }>({ open: false, pathname: null }); // 햄버거 메뉴가 열린 화면 주소를 함께 기억해요.
    const open = menu.open && menu.pathname === pathname; // 다른 화면으로 이동하면 메뉴는 저절로 닫혀요.
    const menuId = useId(); // 버튼과 펼친 메뉴를 보조기기에 연결해요.
    const menuRoot = useRef<HTMLDivElement>(null); // 메뉴 바깥을 눌렀는지 판단할 영역이에요.
    useEffect(() => { // 메뉴가 열려 있을 때만 바깥 클릭과 Esc 키를 들어요.
        if (!open) return; // 닫혀 있으면 할 일이 없어요.
        const close = () => setMenu({ open: false, pathname: null }); // 메뉴를 닫아요.
        const onPointer = (event: PointerEvent) => { if (!menuRoot.current?.contains(event.target as Node)) close(); }; // 메뉴 바깥을 누르면 닫아요.
        const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); }; // Esc 키로도 닫아요.
        document.addEventListener("pointerdown", onPointer); document.addEventListener("keydown", onKey); // 열린 동안만 듣기 시작해요.
        return () => { document.removeEventListener("pointerdown", onPointer); document.removeEventListener("keydown", onKey); }; // 닫히면 듣기를 멈춰요.
    }, [open]); // 열림 상태가 바뀔 때만 다시 연결해요.
    useEffect(() => { // 로그인과 로그아웃 뒤 새 화면에서 서버 세션을 다시 읽어요.
        const controller = new AbortController(); // 화면을 떠난 뒤 도착한 응답은 반영하지 않아요.
        async function checkSession() { // HttpOnly 쿠키는 직접 읽지 않고 서버에 확인해요.
            try { await me(controller.signal); if (!controller.signal.aborted) setChecked({ pathname, status: "signed_in" }); } // 정상 응답에서만 로그인 메뉴를 보여줘요.
            catch (cause) { if (!controller.signal.aborted) setChecked({ pathname, status: cause instanceof ServiceError && cause.status === 401 ? "signed_out" : "unknown" }); } // 인증 거절일 때만 로그인과 가입을 안내해요.
        } // 세션 확인 함수를 마쳐요.
        void checkSession(); // 화면 표시를 막지 않고 계정 상태를 확인해요.
        return () => controller.abort(); // 이동 전 요청을 정리해요.
    }, [pathname]); // 주소가 달라질 때마다 세션을 확인해요.
    return <> {/* 두 화면 크기의 메뉴가 같은 계정 상태를 사용해요. */}
        <div className="header-account-actions"> {/* 데스크톱과 작은 화면 상단의 계정 메뉴예요. */}
            {status === "loading" ? <LoadingState label="계정 확인 중" compact /> : status === "signed_out" ? <><Link className="header-login" href="/login">로그인</Link><Link className="button button-primary header-cta" href="/signup">회원가입{arrowIcon}</Link></> : <>{status === "signed_in" && <Link className="header-login" href="/settings">설정</Link>}<Link className="button button-primary header-cta" href="/my">내 징검다리{arrowIcon}</Link></>} {/* 계정을 확인하지 못해도 추천 화면에서 연결을 다시 확인할 수 있어요. */}
        </div> {/* 상단 계정 메뉴를 마쳐요. */}
        <div className="mobile-nav" ref={menuRoot}> {/* 좁은 화면에서만 보이는 햄버거 메뉴예요. */}
            <button type="button" className="mobile-nav-toggle" aria-label={open ? "메뉴 닫기" : "메뉴 열기"} aria-expanded={open} aria-controls={menuId} onClick={() => setMenu({ open: !open, pathname })}>{open ? closeIcon : menuIcon}</button> {/* 누를 때마다 메뉴를 열고 닫아요. */}
            {open && <nav id={menuId} className="mobile-nav-panel" aria-label="전체 메뉴" onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setMenu({ open: false, pathname: null }); }}>{navigation}{status === "signed_out" ? <><Link href="/login">로그인</Link><Link href="/signup">회원가입</Link></> : status === "signed_in" ? <Link href="/settings">설정</Link> : null}</nav>} {/* 링크를 누르면 메뉴를 닫고, 계정 상태에 맞는 메뉴만 보여줘요. */}
        </div> {/* 햄버거 메뉴를 마쳐요. */}
    </>; // 이메일이나 계정 식별자는 헤더에 남기지 않아요.
} // 계정 메뉴 컴포넌트를 마쳐요.
