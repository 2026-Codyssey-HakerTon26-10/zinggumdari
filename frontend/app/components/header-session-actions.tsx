"use client"; // 페이지를 옮길 때 서버 세션에 맞는 계정 메뉴를 보여줘요.
import { useEffect, useState, type ReactNode } from "react"; // 계정 확인 결과와 서버에서 받은 메뉴 장식을 관리해요.
import Link from "next/link"; // 계정과 추천 화면으로 이동해요.
import { LoadingState } from "./loading-state"; // 계정 확인 중임을 메뉴에서도 알려줘요.
import { usePathname } from "next/navigation"; // 현재 화면이 바뀌면 계정 상태를 다시 확인해요.
import { me, ServiceError } from "../lib/service-api"; // 브라우저 저장소 대신 서버 세션을 확인해요.
type Status = "signed_in" | "signed_out" | "unknown" | "loading"; // 연결 실패를 로그아웃으로 오해하지 않도록 구분해요.
type Props = { navigation: ReactNode; menuIcon: ReactNode; arrowIcon: ReactNode }; // 아이콘을 바깥에서 받아 공통 UI와 순환 참조하지 않아요.
export function HeaderSessionActions({ navigation, menuIcon, arrowIcon }: Props) { // 데스크톱과 모바일에서 하나의 세션 결과를 함께 써요.
    const pathname = usePathname(); // 이동한 화면을 기준으로 세션 결과를 구분해요.
    const [checked, setChecked] = useState<{ pathname: string | null; status: Status }>({ pathname: null, status: "loading" }); // 서버 확인 전에는 가입이나 로그인을 단정하지 않아요.
    const status = checked.pathname === pathname ? checked.status : "loading"; // 다른 화면에서 받은 이전 계정 결과를 잠시 숨겨요.
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
        <details className="mobile-nav" key={pathname}> {/* 이동 뒤 모바일 메뉴를 접어서 본문을 가리지 않아요. */}
            <summary aria-label="메뉴 열기">{menuIcon}</summary> {/* 기존 모바일 메뉴 아이콘을 그대로 사용해요. */}
            <nav aria-label="모바일 메뉴">{navigation}{status === "signed_out" ? <><Link href="/login">로그인</Link><Link href="/signup">회원가입</Link></> : status === "signed_in" ? <Link href="/settings">설정</Link> : null}</nav> {/* 서버가 확인한 계정 상태에 맞는 메뉴만 보여줘요. */}
        </details> {/* 모바일 메뉴를 마쳐요. */}
    </>; // 이메일이나 계정 식별자는 헤더에 남기지 않아요.
} // 계정 메뉴 컴포넌트를 마쳐요.
