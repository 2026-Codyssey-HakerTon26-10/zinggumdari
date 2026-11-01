"use client"; // 슬라이드 전환이 사용자 화면에서 동작해요.

import { useState, useEffect, useCallback, type MouseEvent } from "react"; // 현재 배너 번호, 자동 전환, 클릭 핸들러를 관리해요.
import Link from "next/link"; // CTA 버튼을 서비스 화면으로 연결해요.
import { useRouter } from "next/navigation"; // 세션 확인 뒤 알맞은 화면으로 이동해요.
import { me, ServiceError } from "../lib/service-api"; // HttpOnly 쿠키는 직접 읽지 않고 서버 세션으로 로그인 여부를 확인해요.
import { authEntryHref, type AuthDestination } from "../lib/auth-validation"; // 비로그인 사용자는 가입 뒤 고른 화면으로 돌아오게 해요.
import { Icon } from "./ui"; // 공통 아이콘을 그려요.
import { JourneyPreview } from "./journey-preview"; // 오른쪽에 다섯 단계 그림을 보여줘요.

const INTERVAL_MS = 5000; // 배너를 자동으로 바꾸는 간격이에요 (5초).

const banners = [ // 순환할 배너 두 개를 정의해요.
    {
        eyebrow: "부모님 것까지, 신고하기 전에", // 첫 번째 배너의 작은 안내 문구예요.
        headlinePlain: "물어보기 전에", // 강조하지 않을 제목 첫 줄이에요.
        headlineAccent: "먼저 찾아드려요", // 파란색으로 강조할 핵심 문구예요.
        description: "나와 부모님 정보를 고르기만 하면,\n받을 수 있는 제도와 거의 해당하는 제도를\n공고 원문 근거와 함께 보여드려요.", // 첫 번째 배너의 설명이에요.
        actions: [ // 첫 번째 배너의 CTA 버튼 목록이에요.
            { href: "/my", auth: "/my" as AuthDestination, label: "3분 만에 확인하기", icon: "arrow-right", primary: true }, // 로그인했다면 내 추천으로 바로, 아니면 가입으로 보내요.
            { href: "/my?subject=parent", auth: "/my?subject=parent" as AuthDestination, label: "부모님 대신 확인하기", icon: "family", primary: false }, // 로그인 상태에 따라 부모님 추천 흐름을 이어가요.
        ],
    },
    {
        eyebrow: "놓치고 있는 부모님 제도가 있을 수 있어요", // 두 번째 배너의 작은 안내 문구예요.
        headlinePlain: "부모님 제도도", // 두 번째 배너 제목의 첫 줄이에요.
        headlineAccent: "함께 챙겨드려요", // 두 번째 배너에서 강조할 문구예요.
        description: "기초연금, 돌봄, 장기요양까지.\n부모님 상황에 맞는 제도를 대신 확인해드려요.\n멀리 계셔도 괜찮아요.", // 두 번째 배너의 설명이에요.
        actions: [ // 두 번째 배너의 CTA 버튼 목록이에요.
            { href: "/my?subject=parent", auth: "/my?subject=parent" as AuthDestination, label: "부모님 혜택 확인하기", icon: "arrow-right", primary: true }, // 이미 로그인했다면 부모님 추천으로 바로 이동해요.
            { href: "/search", auth: undefined, label: "직접 공고 검색하기", icon: "search", primary: false }, // 검색은 로그인 없이 열 수 있어요.
        ],
    },
];

export function HeroBanner() { // 두 배너를 자동으로 순환해서 보여주는 히어로 컴포넌트예요.
    const [current, setCurrent] = useState(0); // 지금 보여주는 배너의 번호를 기억해요.
    const [hovered, setHovered] = useState(false); // 마우스가 배너 위에 있는지만 따로 기억해요.
    const [paused, setPaused] = useState(false); // 사용자가 정지하거나 키보드로 접근한 상태를 유지해요.
    const [reducedMotion, setReducedMotion] = useState(true); // 움직임 설정을 읽기 전에는 자동 전환을 시작하지 않아요.
    const [session, setSession] = useState<"loading" | "signed_in" | "signed_out" | "unknown">("loading"); // 서버가 확인한 로그인 상태예요.
    const router = useRouter(); // 클릭 시점에 세션을 확인한 뒤 이동해요.

    useEffect(() => { // 랜딩에 들어오면 서버 세션을 한 번 확인해요.
        const controller = new AbortController(); // 화면을 떠난 뒤 도착한 응답은 반영하지 않아요.
        me(controller.signal).then(() => { if (!controller.signal.aborted) setSession("signed_in"); }).catch((cause) => { if (!controller.signal.aborted) setSession(cause instanceof ServiceError && cause.status === 401 ? "signed_out" : "unknown"); }); // 401일 때만 비로그인으로 보고 연결 실패는 따로 구분해요.
        return () => controller.abort(); // 화면을 떠나면 요청을 취소해요.
    }, []); // 처음 한 번만 확인해요.

    function actionHref(action: { href: string; auth?: AuthDestination }) { // 로그인 상태에 맞는 이동 주소를 골라요.
        if (!action.auth || session !== "signed_out") return action.href; // 로그인했거나 확인 중이면 원래 화면 주소를 써요.
        return authEntryHref("signup", action.auth); // 비로그인이면 가입 뒤 고른 화면으로 돌아오게 해요.
    } // 주소 선택을 마쳐요.

    async function openAction(event: MouseEvent<HTMLAnchorElement>, auth?: AuthDestination) { // 세션 확인이 끝나기 전 클릭도 올바른 화면으로 보내요.
        if (!auth || session === "signed_in" || session === "signed_out") return; // 이미 상태를 알면 링크 기본 이동을 그대로 써요.
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return; // 새 탭 열기 같은 브라우저 동작은 막지 않아요.
        event.preventDefault(); // 확인 전에는 잠시 이동을 멈춰요.
        try { await me(); router.push(auth); } // 로그인되어 있으면 원하는 화면으로 바로 가요.
        catch (cause) { router.push(cause instanceof ServiceError && cause.status === 401 ? authEntryHref("signup", auth) : auth); } // 비로그인일 때만 가입으로 보내고, 연결 실패는 화면에서 안내하게 해요.
    } // 클릭 처리를 마쳐요.

    const goNext = useCallback(() => { // 다음 배너로 이동하는 함수예요.
        setCurrent((prev) => (prev + 1) % banners.length); // 마지막 배너 뒤엔 첫 번째로 돌아와요.
    }, []);

    useEffect(() => { // 운영체제의 움직임 줄이기 설정과 이후 변경을 구독해요.
        const preference = window.matchMedia("(prefers-reduced-motion: reduce)"); // 사용자가 선택한 움직임 설정을 읽어요.
        const update = () => setReducedMotion(preference.matches); // 현재 설정에 맞춰 자동 전환 허용 여부를 바꿔요.
        update(); // 첫 화면에서도 현재 설정을 적용해요.
        preference.addEventListener("change", update); // 설정이 바뀌면 즉시 반영해요.
        return () => preference.removeEventListener("change", update); // 화면을 떠나면 구독을 정리해요.
    }, []); // 움직임 설정 구독은 처음 한 번 연결해요.

    useEffect(() => { // 자동 전환이 허용된 동안에만 타이머를 실행해요.
        if (paused || hovered || reducedMotion) return; // 사용자 정지·호버·움직임 줄이기 중에는 전환하지 않아요.
        const id = setInterval(goNext, INTERVAL_MS); // 5초마다 배너를 바꿔요.
        return () => clearInterval(id); // 화면을 떠나거나 paused가 바뀌면 타이머를 정리해요.
    }, [paused, hovered, reducedMotion, goNext]); // 정지 조건이 바뀌면 이전 타이머를 정리해요.

    const banner = banners[current]; // 지금 보여줄 배너 정보를 가져와요.

    return (
        <section
            className="landing-hero" // 히어로 영역 전체예요.
            onMouseEnter={() => setHovered(true)} // 마우스를 올린 동안에만 임시로 전환을 멈춰요.
            onMouseLeave={() => setHovered(false)} // 호버만 해제하고 사용자의 정지 선택은 유지해요.
            onFocusCapture={(event) => { // 키보드 접근은 멈추고 재생 버튼의 마우스 포커스는 클릭 의도를 유지해요.
                if (event.target.closest("[data-banner-playback]") && !event.target.matches(":focus-visible")) return; // 마우스로 정지를 누르기 직전 포커스가 상태를 반전시키지 않게 해요.
                setPaused(true); // 키보드로 들어오면 명시적으로 재생할 때까지 정지해요.
            }}
        >
            <div className="container hero-grid"> {/* 소개 글과 그림을 나란히 배치해요. */}
                <div className="hero-copy"> {/* 텍스트, 버튼, 인디케이터 영역이에요. */}
                    <span className="eyebrow hero-eyebrow"> {/* 배너 상단 작은 안내예요. */}
                        <span className="live-dot" />{banner.eyebrow}
                    </span>
                    <h1> {/* 배너별 메인 제목이에요. */}
                        {banner.headlinePlain}<br />
                        <span>{banner.headlineAccent}</span>
                        <span className="headline-period">.</span>
                    </h1>
                    <p className="hero-description" style={{ whiteSpace: "pre-line" }}> {/* 설명을 줄바꿈 그대로 표시해요. */}
                        {banner.description}
                    </p>
                    <div className="hero-actions"> {/* CTA 버튼 두 개를 나란히 배치해요. */}
                        {banner.actions.map((action, index) => (
                            <Link
                                key={index} // 같은 위치의 링크 요소를 유지해 불필요한 포커스 손실을 줄여요.
                                className={`button button-large ${action.primary ? "button-primary" : "button-secondary"}`}
                                href={actionHref(action)} // 로그인 상태에 맞는 주소로 이동해요.
                                onClick={(event) => void openAction(event, action.auth)} // 세션 확인 전 클릭도 처리해요.
                            >
                                {!action.primary && <Icon name={action.icon} />} {/* 보조 버튼은 왼쪽 아이콘이에요. */}
                                {action.label}
                                {action.primary && <Icon name="arrow-right" />} {/* 주요 버튼은 오른쪽 화살표예요. */}
                            </Link>
                        ))}
                    </div>
                    <p className="hero-action-note">회원가입 후 나의 정보를 이어서 살펴봐요 · 현재는 시연용 화면이에요</p> {/* 시작 조건을 안내해요. */}
                    <div className="hero-trust"> {/* 신뢰 안내 요소를 나열해요. */}
                        <span><Icon name="shield" />주민등록번호 입력 없이</span>
                        <span><Icon name="file" />공고 원문 근거와 함께</span>
                    </div>
                    <div className="hero-banner-dots" role="group" aria-label="배너 이동 및 자동 전환"> {/* 배너 선택 인디케이터 점이에요. */}
                        {banners.map((_, index) => (
                            <button
                                key={index}
                                type="button"
                                aria-pressed={index === current} // 현재 배너를 보조기기에 알려요.
                                aria-label={`배너 ${index + 1}`}
                                className={`hero-banner-dot${index === current ? " is-active" : ""}`}
                                onClick={() => { // 점을 누르면 해당 배너로 이동해요.
                                    setCurrent(index);
                                    setPaused(true); // 직접 선택한 배너는 재생을 누르기 전까지 유지해요.
                                }}
                            />
                        ))}
                        <button type="button" className="hero-banner-playback" data-banner-playback="true" disabled={reducedMotion} onClick={() => setPaused((previous) => !previous)} aria-label={reducedMotion ? "움직임 줄이기 설정으로 자동 전환 정지됨" : paused ? "배너 자동 전환 재생" : "배너 자동 전환 정지"}>{reducedMotion ? "자동 전환 꺼짐" : paused ? "자동 전환 재생" : "자동 전환 정지"}</button> {/* 마우스와 키보드 모두로 자동 전환을 직접 제어해요. */}
                    </div>
                </div>
                <JourneyPreview /> {/* 오른쪽 다섯 단계 그림이에요. */}
            </div>
            <div className="hero-bottom-label"> {/* 하단 슬로건이에요. */}
                <span />오늘의 나를 알고, 내일의 가능성을 잇다<span />
            </div>
        </section>
    );
}
