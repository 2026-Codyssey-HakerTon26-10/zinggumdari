"use client"; // 추천 카드의 상세 조건은 사용자가 펼쳐서 확인해요.
import { Icon } from "../../components/ui"; // 서비스에서 쓰던 문서와 이동 아이콘을 사용해요.
import { safeLink, type Card, type Evidence } from "../../lib/service-api"; // 자격 상태와 근거는 서버가 보낸 값만 사용해요.
import "./recommendation-card.css"; // 추천 목록에만 적용하는 카드 스타일을 가져와요.
type Props = { card: Card; fresh?: boolean; busy: boolean; onEvidence: (evidence: Evidence[]) => void; onQuestion: () => void }; // 기존 원문 보기와 질문 요청을 부모 화면에 전달해요.
export function RecommendationCard({ card, fresh, busy, onEvidence, onQuestion }: Props) { // 긴 조건을 접어 목록에서 제도 이름과 상태를 먼저 보여줘요.
    const source = safeLink(card.detail_url); // 원문은 안전한 웹 주소일 때만 링크로 보여줘요.
    const short = (text: string) => text.replace(/\(.*?\)/g, "").replace(/\s+/g, " ").trim().slice(0, 26) + (text.length > 26 ? "…" : ""); // 카드 앞면에는 조건을 짧게 보여줘요.
    const merge = (items: string[]) => { const groups = new Map<string, string[]>(); for (const item of items) { const [head, ...rest] = item.split(" "); groups.set(head, [...(groups.get(head) || []), rest.join(" ")]); } return [...groups].map(([head, rests]) => `${head} ${[...new Set(rests)].join(", ")}`.trim()); }; // 「나이 만 19세 이상 · 나이 만 39세 이하」처럼 같은 주제는 한 줄로 묶어요.
    const pick = (ok: boolean | null) => merge(card.conditions.filter((c) => c.ok === ok).map((c) => short(c.read_as))); // 서버 판정 그대로 나눠요.
    const fit = { matched: pick(true), blocked: pick(false), left: pick(null) }; // 맞는 조건·안 맞는 조건·남은 확인이에요.
    const label = card.verdict === "eligible" ? "신청할 수 있어요" : card.verdict === "opens_later" ? "다음 조건에서 열려요" : "확인 필요"; // 서버의 자격 상태를 기존 문구 그대로 표시해요.
    return <article className="recommendation-card"> {/* 각 제도의 요약과 상세 정보를 독립된 카드로 묶어요. */}
        <div className="recommendation-card-body"> {/* 카드 본문에 일관된 여백을 적용해요. */}
            <div className="recommendation-card-badges">{fresh && <span className="recommendation-card-fresh">새로 열림</span>}<span className={`recommendation-card-verdict ${card.verdict === "eligible" ? "is-eligible" : ""}`}>{label}</span>{card.ai_extracted && <span className="recommendation-card-ai">AI 추출</span>}{card.subject === "parent" && card.relation && <span className="recommendation-card-relation">{card.relation === "모" ? "어머니" : "아버지"}</span>}</div> {/* 자격 상태와 추출 방식, 부모 대상을 서로 구분해요. */}
            <h2>{card.name}</h2> {/* 긴 제도 이름도 카드 안에서 자연스럽게 줄바꿈해요. */}
            {fit.matched.length || fit.left.length || fit.blocked.length ? <div className="recommendation-card-fit"> {/* 왜 추천했는지 내 정보와 맞는 조건으로 보여줘요. */}
                {fit.matched.length > 0 && <p><span className="fit-label is-match"><Icon name="check" />내 정보와 맞아요</span>{fit.matched.slice(0, 3).join(" · ")}{fit.matched.length > 3 ? ` 외 ${fit.matched.length - 3}개` : ""}</p>}
                {fit.blocked.length > 0 && <p><span className="fit-label is-later"><Icon name="clock" />{card.verdict === "opens_later" ? "이때 열려요" : "맞지 않아요"}</span>{fit.blocked.slice(0, 2).join(" · ")}</p>}
                {fit.left.length > 0 && <p><span className="fit-label is-left"><Icon name="info" />남은 확인 {fit.left.length}개</span>{fit.left.slice(0, 2).join(" · ")}{fit.left.length > 2 ? " …" : ""}</p>}
            </div> : <p className="recommendation-card-intro">조건 {card.conditions.length}개와 공고 원문을 함께 확인해 보세요.</p>} {/* 조건 개수와 상태는 실제 응답에서 세고 자격 가능성을 임의로 높이지 않아요. */}
            <details className="recommendation-card-details"><summary>조건과 근거 보기<span>{card.conditions.length}개<Icon name="chevron-down" /></span></summary><div className="recommendation-card-detail-body">{card.explain && <p>{card.explain}</p>}<ul>{card.conditions.map((condition, index) => <li key={index}><div className="recommendation-card-condition"><span>{condition.read_as}</span><strong>{condition.grade}{condition.ok === false ? " · 불충족" : ""}</strong></div><button type="button" className="recommendation-card-evidence" onClick={() => onEvidence(condition.evidence || [])}><Icon name="file" />근거 보기</button></li>)}</ul></div></details> {/* 처음에는 접어 두고 펼쳤을 때 서버 조건과 기존 근거 뷰어를 연결해요. */}
            {card.documents && <details className="recommendation-card-details"><summary>구비서류·발급처<Icon name="chevron-down" /></summary><div className="recommendation-card-detail-body"><ul>{card.documents.map((document, index) => <li key={index}><strong>{document.name}</strong><p>{document.who_provides === "official" ? "공무원이 확인" : document.status === "self_held" ? "본인이 가진 서류" : document.issuer || "발급처 확인 필요"}</p>{safeLink(document.online) && <a href={safeLink(document.online)!} target="_blank" rel="noopener noreferrer">발급처 열기<Icon name="arrow-up-right" /></a>}</li>)}</ul></div></details>} {/* 서류와 발급처도 필요할 때 펼치고 서버가 준 정보만 보여줘요. */}
            <div className="recommendation-card-source"><span>기준일 {card.updated || "확인 필요"}</span>{source ? <a href={source} target="_blank" rel="noopener noreferrer">공식 원문<Icon name="arrow-up-right" /></a> : <span>원문 연결 확인 필요</span>}</div> {/* 원문 링크와 기준일은 상세를 열지 않아도 확인할 수 있어요. */}
            {card.verdict === "needs_check" && (card.blocking_fields?.length ?? 0) > 0 && <button className="recommendation-card-question" type="button" disabled={busy} onClick={onQuestion}>이 공고의 확인 질문 보기<Icon name="arrow-right" /></button>} {/* 서버가 질문을 고를 수 있는 카드(확인 필요 + 비어 있는 칸)에만 질문 버튼을 보여줘요. */}
        </div> {/* 카드 본문을 마쳐요. */}
    </article>; // 제도 자격과 데이터는 바꾸지 않고 표시 방식만 정돈해요.
} // 추천 카드를 마쳐요.
