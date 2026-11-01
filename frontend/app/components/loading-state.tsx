import "./loading-state.css"; // 모든 요청에서 같은 로딩 표시를 사용해요.
export function LoadingState({ label = "정보를 불러오고 있습니다.", compact = false }: { label?: string; compact?: boolean }) { // 실제 요청이 진행되는 동안 표시할 안내를 받아요.
    return <div className={`loading-state${compact ? " loading-state--compact" : ""}`} role="status" aria-live="polite"> {/* 보조기기에도 처리 중임을 알려줘요. */}
        <div className="loading-state-heading"><span className="loading-state-spinner" aria-hidden="true" /><span>{label}</span></div> {/* 회전 표시와 현재 작업 이름을 함께 보여줘요. */}
        {!compact && <div className="loading-state-placeholder" aria-hidden="true"><span /><span /><span /></div>} {/* 기다리는 영역의 형태만 보여주고 진행률은 만들지 않아요. */}
    </div>; // 요청 완료나 실패 시 부모가 로딩 영역을 없애요.
} // 공통 로딩 표시를 마쳐요.
