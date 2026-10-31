"use client"; // 생애 단계 버튼을 눌렀을 때 미리보기 내용을 바꿀 수 있게 해요.

import { useState } from "react"; // 현재 선택한 단계를 화면 안에서 기억해요.
import Link from "next/link"; // 부모님 화면으로 이동하는 링크를 가져와요.
import { Icon } from "./ui"; // 서비스 공통 아이콘을 가져와요.

const stages = [ // 생애 흐름을 설명하는 다섯 개의 화면 예시를 준비해요.
    { name: "청년", icon: "leaf", title: "첫 독립의 시작도 든든하게", description: "주거와 생활에 필요한 제도를 살펴봐요.", className: "stone-youth" }, // 첫 독립과 청년의 단계를 소개해요.
    { name: "신혼", icon: "heart", title: "둘이 시작하는 새로운 일상", description: "함께하는 다음 단계의 제도를 미리 살펴봐요.", className: "stone-marriage" }, // 신혼으로 넘어가는 단계를 소개해요.
    { name: "출산", icon: "baby", title: "새로운 가족을 맞이할 때", description: "가족이 늘어나는 시기의 제도를 살펴봐요.", className: "stone-birth" }, // 출산과 가족의 변화를 소개해요.
    { name: "육아", icon: "home", title: "함께 자라는 매일을 위해", description: "아이를 돌보는 일상에 필요한 제도를 살펴봐요.", className: "stone-care" }, // 육아 단계의 흐름을 소개해요.
    { name: "다자녀", icon: "family", title: "더 커진 가족의 다음 걸음", description: "가구의 변화에 맞는 제도를 함께 살펴봐요.", className: "stone-family" }, // 다자녀 단계의 흐름을 소개해요.
]; // 단계 소개 목록을 마쳐요.

export function JourneyPreview() { // 랜딩에서 직접 눌러볼 수 있는 생애주기 그림을 만들어요.
    const [selected, setSelected] = useState(0); // 실제 프로필을 바꾸지 않고 미리보기 단계만 기억해요.
    const current = stages[selected]; // 선택한 단계의 소개를 가져와요.
    return <div className="journey-preview" aria-label="다섯 단계 생애주기 미리보기"><div className="journey-topline"><span><span className="live-dot" />나의 생애주기 미리보기</span><span>단계를 눌러보세요</span></div><div className="journey-summary" aria-live="polite"><span className="journey-summary-icon"><Icon name={current.icon} /></span><div><span className="journey-summary-kicker">나의 {selected + 1}번째 징검다리</span><h2>{current.title}</h2><p>{current.description}</p></div><span className="journey-page">0{selected + 1}<span> / 05</span></span></div><div className="river-map"><svg className="river-lines" viewBox="0 0 500 280" fill="none" aria-hidden="true"><path d="M-45 250C50 330 110 40 225 128S380 250 545 15" stroke="#f0f1f3" strokeWidth="104" strokeLinecap="round" /><path d="M-45 250C50 330 110 40 225 128S380 250 545 15" stroke="#fafafa" strokeWidth="84" strokeLinecap="round" /><path d="M-45 250C50 330 110 40 225 128S380 250 545 15" stroke="#dde1e6" strokeWidth="1.5" strokeDasharray="4 8" /><path d="M-35 270C65 350 120 60 230 148S390 270 555 35" stroke="white" strokeWidth="2" strokeLinecap="round" opacity=".8" /></svg>{stages.map((stage, index) => <button key={stage.name} type="button" className={`journey-stone ${stage.className} ${selected === index ? "is-selected" : ""}`} onClick={() => setSelected(index)} aria-pressed={selected === index} aria-label={`${stage.name} 단계 미리보기`}><span className="stone-shape"><Icon name={stage.icon} /><span className="stone-number">0{index + 1}</span></span><span className="stone-label">{stage.name}</span></button>)}<span className="river-caption">지금의 나에서, 다음의 나로</span></div><Link className="parent-preview" href="/my?subject=parent"><span className="parent-preview-icon"><Icon name="family" /></span><span><strong>부모님의 일상도 함께</strong><small>따로 살펴보고, 꼼꼼하게 챙겨요</small></span><Icon name="arrow-up-right" /></Link><p className="journey-disclaimer">서비스 흐름을 보여주는 예시입니다. 실제 자격 판정과는 다릅니다.</p></div>; // 돌을 선택하면 소개만 바뀌고 실제 자격이나 개인 정보는 처리하지 않아요.
} // 생애주기 미리보기를 마쳐요.
