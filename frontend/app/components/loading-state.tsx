import "./loading-state.css"; // 모든 요청에서 같은 로딩 표시를 사용해요.
export function LoadingState({ label = "정보를 불러오고 있습니다.", hint = "잠시만 기다려 주세요. 첫 연결은 시간이 조금 걸릴 수 있어요.", compact = false }: { label?: string; hint?: string; compact?: boolean }) { // 실제 요청이 진행되는 동안 표시할 안내를 받아요.
    if (compact) return <div className="loading-state loading-state--compact" role="status" aria-live="polite"><span className="loading-state-spinner" aria-hidden="true" /><span>{label}</span></div>; // 버튼 옆 같은 좁은 자리에는 작은 회전 표시와 문구만 보여줘요.
    return <div className="loading-state" role="status" aria-live="polite"> {/* 보조기기에도 처리 중임을 알려줘요. */}
        <span className="loading-state-spinner" aria-hidden="true" /> {/* 요청이 끝날 때까지 가운데에서 도는 동그라미예요. */}
        <p className="loading-state-label">{label}</p> {/* 지금 하고 있는 작업을 알려줘요. */}
        {hint && <p className="loading-state-hint">{hint}</p>} {/* 기다리는 이유를 짧게 안내하고 걸리는 시간은 약속하지 않아요. */}
    </div>; // 요청 완료나 실패 시 부모가 로딩 영역을 없애요.
} // 공통 로딩 표시를 마쳐요.
