"use client"; // 추천 대상과 살펴볼 생활 단계를 직접 선택해요.
import { Icon } from "../../components/ui"; // 서비스에서 쓰던 아이콘을 그대로 사용해요.
import type { Stage } from "../../lib/service-api"; // 서버가 지원하는 단계 값만 선택해요.
import { LoadingState } from "../../components/loading-state"; // 단계 전환 중에도 같은 로딩 표시를 보여줘요.
const stages: { value: Stage; label: string; description: string; icon: string }[] = [ // 저장 값과 화면에 보이는 안내를 함께 정의해요.
    { value: "", label: "지금의 나", description: "현재 정보로 살펴보기", icon: "leaf" }, // 실제 프로필로 확인하는 기본 선택이에요.
    { value: "newlywed", label: "결혼하면", description: "둘이 시작하는 생활", icon: "heart" }, // 신혼을 가정한 추천을 보여줘요.
    { value: "child", label: "아이가 생기면", description: "새 가족과 함께하는 일상", icon: "baby" }, // 자녀가 있는 단계를 가정해요.
    { value: "multi_child", label: "가족이 늘면", description: "다자녀 가정을 위한 준비", icon: "family" }, // 다자녀 단계를 가정해요.
]; // 지원하지 않는 단계나 날짜는 만들지 않아요.
type Props = { subject: "self" | "parent"; stage: Stage; busy: boolean; error: string; onSubject: (subject: "self" | "parent") => void; onStage: (stage: Stage) => void }; // 기존 화면의 선택과 요청 상태를 전달받아요.
export function RecommendationControls({ subject, stage, busy, error, onSubject, onStage }: Props) { // 대상 선택과 생활 단계를 한 흐름으로 묶어요.
    return <section className="recommendation-controls" aria-label="추천 설정"> {/* 추천 설정을 하나의 영역으로 안내해요. */}
        <div className="recommendation-subjects" role="group" aria-label="누구를 위한 추천인가요?"> {/* 두 대상 중 현재 선택을 알려줘요. */}
            <button type="button" aria-pressed={subject === "self"} onClick={() => onSubject("self")}><Icon name="user" /><span>나의 추천</span></button> {/* 나의 추천을 여는 넓은 탭이에요. */}
            <button type="button" aria-pressed={subject === "parent"} onClick={() => onSubject("parent")}><Icon name="family" /><span>부모님 챙기기</span></button> {/* 부모님 추천을 독립적으로 선택해요. */}
        </div> {/* 대상 선택 탭을 마쳐요. */}
        <p className="recommendation-subject-note">{subject === "self" ? "오늘 필요한 제도부터, 다음 생활의 준비까지 함께 살펴보세요." : "부모님에게 필요한 제도도 한곳에서 챙겨보세요."}</p> {/* 선택한 대상에 맞는 안내만 보여줘요. */}
        {subject === "self" && <div className="recommendation-journey"> {/* 본인의 생활 단계는 본인 추천에서만 보여줘요. */}
            <div className="recommendation-journey-heading"><span className="recommendation-eyebrow"><Icon name="sparkles" /> 나의 다음 걸음</span><h2>다음 생활도 미리 둘러보세요</h2><p>궁금한 단계를 선택해 보세요. 저장된 내 정보는 바뀌지 않아요.</p></div> {/* 실제 프로필을 바꾸지 않는 미리보기임을 안내해요. */}
            <div className="recommendation-stages" role="group" aria-label="미리 살펴볼 생활 단계"> {/* 단계 선택을 카드 형태로 배치해요. */}
                {stages.map((item) => <button key={item.value} type="button" className="recommendation-stage" aria-pressed={stage === item.value} disabled={busy} onClick={() => onStage(item.value)}><span className="recommendation-stage-icon"><Icon name={item.icon} /></span><span className="recommendation-stage-copy"><strong>{item.label}</strong><small>{item.description}</small></span><span className="recommendation-stage-check" aria-hidden="true">{stage === item.value && <Icon name="check" />}</span></button>)} {/* 아이콘과 체크 표시로 선택한 단계를 구분해요. */}
            </div> {/* 단계 선택을 마쳐요. */}
            {stage && <p className="recommendation-preview-note"><Icon name="info" /> 선택한 생활을 가정한 미리보기예요. 실제 신청 조건은 달라질 수 있어요.</p>} {/* 모의 결과를 현재 자격으로 오해하지 않게 해요. */}
        </div>} {/* 생활 단계 영역을 마쳐요. */}
        {busy && <LoadingState label="맞춤 정보를 불러오고 있습니다." hint="공고 조건과 입력하신 정보를 맞춰 보고 있어요. 잠시만 기다려 주세요." />} {/* 처리 상태를 내부 용어 없이 알려줘요. */}
        {error && <p role="alert">{error}</p>} {/* 요청이 실패하면 기존 오류를 그대로 안내해요. */}
    </section>; // 선택만 바꾸며 실제 정보 저장은 기존 폼에서 처리해요.
} // 추천 선택 영역을 마쳐요.
