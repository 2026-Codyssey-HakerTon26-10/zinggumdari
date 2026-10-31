"use client"; // 부모님 영역과 동의 상태를 현재 화면에서만 관리해요.
import { useState } from "react"; // 확인 여부와 선택한 가상 사례를 기억해요.
type ParentPreview = { relation: "모"; birth_year: number; sido: string; sigungu: string }; // 민감한 건강 정보와 기본 정보를 분리해요.
const parentExample: ParentPreview = { relation: "모", birth_year: 1966, sido: "경기", sigungu: "고양시" }; // SPEC §2.2의 가상 어머니 사례예요.
export function DemoParent() { // 본인 카드에 섞이지 않는 부모님 전용 영역이에요.
    const [open, setOpen] = useState(false); // 처음에는 부모님 정보를 표시하지 않아요.
    const [parentConsent, setParentConsent] = useState(false); // 부모님 동의 안내는 미확인 상태로 시작해요.
    const [sensitiveConsent, setSensitiveConsent] = useState(false); // 건강 관련 정보 표시는 별도로 선택해요.
    const [profile, setProfile] = useState<ParentPreview | null>(null); // 안내 확인 전에는 가상 프로필도 선택하지 않아요.
    function clear() { // 동의 철회나 탭 닫기 때 관련 상태를 함께 지워요.
        setParentConsent(false); setSensitiveConsent(false); setProfile(null); // 가상 프로필과 건강 표시 권한을 모두 초기화해요.
    } // 초기화를 마쳐요.
    return ( // 부모님 점검 영역을 그려요.
        <section className="demo-results" aria-labelledby="demo-parent-title"> {/* 본인 추천과 구분되는 제목을 연결해요. */}
            <h2 id="demo-parent-title">부모님도 함께 살펴보기</h2> {/* 부모님 점검이 선택 기능임을 알려줘요. */}
            <button type="button" className="button button-secondary" aria-expanded={open} aria-controls="demo-parent-content" onClick={() => { if (open) clear(); setOpen((value) => !value); }}>부모님 탭 {open ? "닫기" : "열기"}</button> {/* 닫을 때 동의와 프로필을 남기지 않아요. */}
            {open && <div id="demo-parent-content" className="demo-panel"> {/* 탭을 열어야 안내와 입력 선택이 보여요. */}
                <p className="demo-notice">가상 사례 체험입니다. 실제 부모님 정보는 입력받거나 서버에 저장하지 않습니다.</p> {/* 실제 동의를 수집하는 서비스와 구분해요. */}
                <p id="demo-parent-consent-note">부모님 동의 하에 입력해 주세요. 이름·연락처는 받지 않습니다. 언제든 삭제할 수 있습니다.</p> {/* 명세의 필수 고지를 그대로 표시해요. */}
                <label className="demo-search-mode"><input type="checkbox" checked={parentConsent} aria-describedby="demo-parent-consent-note" onChange={(event) => { if (!event.target.checked) clear(); else setParentConsent(true); }} />부모님 동의 안내를 확인했습니다 · 화면 체험용</label> {/* 체크 해제 시 프로필과 민감정보 동의도 지워요. */}
                <label className="demo-search-mode"><input type="checkbox" checked={sensitiveConsent} disabled={!parentConsent} aria-describedby="demo-parent-sensitive-note" onChange={(event) => setSensitiveConsent(event.target.checked)} />건강 관련 가상 정보 표시에도 별도로 동의합니다</label> {/* 부모님 동의와 민감정보 동의를 합치지 않아요. */}
                <p id="demo-parent-sensitive-note">선택 사항입니다. 미동의 시 장기요양등급·돌봄 정보는 표시하지 않고 관련 조건은 확인 필요로 남깁니다.</p> {/* 동의를 거부해도 기본 흐름을 사용할 수 있어요. */}
                <div className="demo-actions"><button type="button" className="button button-primary" disabled={!parentConsent} onClick={() => { if (parentConsent) setProfile({ ...parentExample }); }}>가상 어머니 사례 선택</button><button type="button" className="button button-secondary" onClick={clear}>동의 철회 · 가상 정보 지우기</button></div> {/* 안내를 확인한 뒤에만 예시를 불러와요. */}
                <p role="status">{profile ? "부모님 가상 사례를 표시했습니다. 본인 프로필은 변경하지 않았습니다." : "선택된 부모님 정보가 없습니다."}</p> {/* 삭제 이후에도 현재 상태를 알려줘요. */}
                {profile && parentConsent && <div> {/* 동의가 있는 동안만 부모님 결과를 그려요. */}
                    <h3>어머니 · 가상 사례</h3><p>{profile.birth_year}년생 · {profile.sido} {profile.sigungu}</p> {/* 실명·연락처가 없는 기본 정보예요. */}
                    <article className="demo-panel demo-card"> {/* 부모 제도는 부모님 영역에서만 표시해요. */}
                        <p className="demo-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 카드 머리에 필수 고지를 붙여요. */}
                        <span className="demo-verdict">부모님 대상 · 확인 필요 · 문서 예시</span><h4>기초연금</h4> {/* 신청 가능으로 확정하지 않아요. */}
                        <p>명세의 가상 사례에서는 2031년 만 65세 도달을 안내합니다. 출생월을 받지 않아 실제 신청 시작월은 확정하지 않습니다.</p> {/* 실제 원문 기반 날짜 계산을 수행한 척하지 않아요. */}
                        <p>소득인정액: 확인 필요 · 재산 환산 필요</p> {/* 기초연금의 소득인정액은 항상 확인 필요로 남겨요. */}
                        <p>공식 공고 원문 미연결 · 예시 데이터 기준일: 2026-10-31</p> {/* 기준일과 원문 미연결 상태를 함께 표시해요. */}
                    </article> {/* 기초연금 예시를 마쳐요. */}
                    <article className="demo-panel demo-card"> {/* 건강 동의에 따른 표시 차이를 별도 카드로 보여줘요. */}
                        <p className="demo-disclaimer">참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정</p> {/* 돌봄 카드에도 같은 고지를 붙여요. */}
                        <span className="demo-verdict">부모님 대상 · 확인 필요 · 문서 예시</span><h4>장기요양등급 신청 안내</h4> {/* 장기요양 서비스 이용 자격을 확정하지 않아요. */}
                        {sensitiveConsent ? <p>가상 사례: 장기요양등급 없음 · 돌봄 희망. 공식 등급 판정과 원문 조건을 확인해야 합니다.</p> : <p>건강 관련 정보 미표시 · 별도 동의가 없어 관련 조건은 확인 필요입니다.</p>} {/* 동의를 해제하면 건강 관련 가상 내용도 즉시 사라져요. */}
                        <p>공식 공고 원문 미연결 · 예시 데이터 기준일: 2026-10-31</p> {/* 공식 발급처나 근거를 임의로 만들지 않아요. */}
                    </article> {/* 돌봄 예시를 마쳐요. */}
                </div>} {/* 부모님 결과를 마쳐요. */}
            </div>} {/* 선택 영역을 마쳐요. */}
        </section> // 부모님 탭을 마쳐요.
    ); // 화면 반환을 마쳐요.
} // 부모님 컴포넌트를 마쳐요.
