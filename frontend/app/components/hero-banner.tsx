"use client"; // 슬라이드 전환이 사용자 화면에서 동작해요.

import { useState, useEffect, useCallback } from "react"; // 현재 배너 번호, 자동 전환, 클릭 핸들러를 관리해요.
import Link from "next/link"; // CTA 버튼을 서비스 화면으로 연결해요.
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
            { href: "/my", label: "3분 만에 확인하기", icon: "arrow-right", primary: true },
            { href: "/my?subject=parent", label: "부모님 대신 확인하기", icon: "family", primary: false },
        ],
    },
    {
        eyebrow: "놓치고 있는 부모님 제도가 있을 수 있어요", // 두 번째 배너의 작은 안내 문구예요.
        headlinePlain: "부모님 제도도", // 두 번째 배너 제목의 첫 줄이에요.
        headlineAccent: "함께 챙겨드려요", // 두 번째 배너에서 강조할 문구예요.
        description: "기초연금, 돌봄, 장기요양까지.\n부모님 상황에 맞는 제도를 대신 확인해드려요.\n멀리 계셔도 괜찮아요.", // 두 번째 배너의 설명이에요.
        actions: [ // 두 번째 배너의 CTA 버튼 목록이에요.
            { href: "/my?subject=parent", label: "부모님 혜택 확인하기", icon: "arrow-right", primary: true },
            { href: "/search", label: "직접 공고 검색하기", icon: "search", primary: false },
        ],
    },
];

export function HeroBanner() { // 두 배너를 자동으로 순환해서 보여주는 히어로 컴포넌트예요.
    const [current, setCurrent] = useState(0); // 지금 보여주는 배너의 번호를 기억해요.
    const [paused, setPaused] = useState(false); // 마우스를 올렸을 때 타이머를 잠시 멈춰요.

    const goNext = useCallback(() => { // 다음 배너로 이동하는 함수예요.
        setCurrent((prev) => (prev + 1) % banners.length); // 마지막 배너 뒤엔 첫 번째로 돌아와요.
    }, []);

    useEffect(() => { // 화면이 나타나면 자동 전환 타이머를 시작해요.
        if (paused) return; // 마우스를 올리면 타이머를 멈춰요.
        const id = setInterval(goNext, INTERVAL_MS); // 5초마다 배너를 바꿔요.
        return () => clearInterval(id); // 화면을 떠나거나 paused가 바뀌면 타이머를 정리해요.
    }, [paused, goNext]);

    const banner = banners[current]; // 지금 보여줄 배너 정보를 가져와요.

    return (
        <section
            className="landing-hero" // 히어로 영역 전체예요.
            onMouseEnter={() => setPaused(true)} // 마우스를 올리면 자동 전환을 멈춰요.
            onMouseLeave={() => setPaused(false)} // 마우스를 내리면 자동 전환을 재개해요.
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
                        {banner.actions.map((action) => (
                            <Link
                                key={`${current}-${action.label}`} // 배너 번호와 버튼 이름으로 고유 키를 만들어요.
                                className={`button button-large ${action.primary ? "button-primary" : "button-secondary"}`}
                                href={action.href}
                            >
                                {!action.primary && <Icon name={action.icon} />} {/* 보조 버튼은 왼쪽 아이콘이에요. */}
                                {action.label}
                                {action.primary && <Icon name="arrow-right" />} {/* 주요 버튼은 오른쪽 화살표예요. */}
                            </Link>
                        ))}
                    </div>
                    <p className="hero-action-note">로그인 없이 시작해요 · 입력 시간은 개인마다 달라요</p> {/* 시작 조건을 안내해요. */}
                    <div className="hero-trust"> {/* 신뢰 안내 요소를 나열해요. */}
                        <span><Icon name="shield" />주민등록번호 입력 없이</span>
                        <span><Icon name="file" />공고 원문 근거와 함께</span>
                    </div>
                    <div className="hero-banner-dots" role="tablist" aria-label="배너 이동"> {/* 배너 선택 인디케이터 점이에요. */}
                        {banners.map((_, index) => (
                            <button
                                key={index}
                                role="tab"
                                aria-selected={index === current} // 현재 배너를 보조기기에 알려요.
                                aria-label={`배너 ${index + 1}`}
                                className={`hero-banner-dot${index === current ? " is-active" : ""}`}
                                onClick={() => { // 점을 누르면 해당 배너로 이동해요.
                                    setCurrent(index);
                                    setPaused(false); // 선택 후 자동 전환을 재개해요.
                                }}
                            />
                        ))}
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
