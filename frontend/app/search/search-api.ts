export type SearchHit = { service_id: string; rule_id: string | null; name: string; org: string | null; region: { sido?: string | null; sigungu?: string | null; unknown?: boolean } | string | null; subject: "self" | "parent"; snippet: string; badge: "eligible" | "similar" | "needs_check" | "ineligible" | "no_rule" | null; detail_url: string | null; updated: string | null }; // 검색 API에서 화면이 사용하는 결과 모양이에요.
export type SearchResponse = { q: string; results: SearchHit[]; judge: "engine" | "fake"; snapshot?: string }; // snapshot이 있으면 서버 대신 저장해 둔 결과예요. // 검색어와 판정 연결 상태를 결과와 함께 받아요.
export type SearchSubject = "all" | "self" | "parent"; // 서버가 지원하는 대상 필터만 사용해요.
export function formatSourceDate(value: string | null): string { // 원문의 숫자 날짜를 읽기 쉬운 형식으로 표시해요.
    if (!value) return "원문에서 확인 필요"; // 기준일이 없으면 날짜를 지어내지 않아요.
    const compact = /^(\d{4})(\d{2})(\d{2})(?:\d{2})?$/.exec(value); // API의 연월일과 연월일시 표기만 변환해요.
    if (!compact) return value; // 이미 표시 가능한 날짜나 다른 원문 값은 그대로 남겨요.
    const date = `${compact[1]}-${compact[2]}-${compact[3]}`; // 원문의 연월일 순서를 유지해 구분선을 넣어요.
    const parsed = new Date(`${date}T00:00:00Z`); // 실제 달력에 있는 날짜인지 확인해요.
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date ? date : value; // 잘못된 원문 날짜를 임의로 보정하지 않아요.
} // 기준일 표시를 마쳐요.
export function safeSourceUrl(value: string | null): string | null { // 외부 공고 링크를 클릭하기 전에 주소 형식을 제한해요.
    try { // 잘못된 URL 때문에 카드 렌더링이 중단되지 않게 해요.
        const url = new URL(value ?? ""); // 절대 URL만 허용해요.
        return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null; // 스크립트·파일 주소와 인증정보가 포함된 링크는 표시하지 않아요.
    } catch { return null; } // 주소가 없거나 형식이 틀리면 원문 미연결로 표시해요.
} // 원문 주소 확인을 마쳐요.
function parseResponse(value: unknown): SearchResponse { // 서버 응답을 신뢰하기 전에 표시할 필드를 확인해요.
    if (!value || typeof value !== "object") throw new Error("검색 응답 형식을 확인할 수 없습니다."); // 객체가 아닌 응답은 거절해요.
    const data = value as Record<string, unknown>; // 확인할 필드를 알 수 없는 값으로 다뤄요.
    if (typeof data.q !== "string" || !Array.isArray(data.results) || !["engine", "fake"].includes(String(data.judge))) throw new Error("검색 응답 형식이 변경되었습니다."); // 결과 배열과 판정 모드를 필수로 확인해요.
    const results = data.results.flatMap((raw: unknown) => { try { return [checkHit(raw)]; } catch { return []; } }); // 형식이 어긋난 항목 하나 때문에 전체 결과를 버리지 않고 그 항목만 빼요.
    return { q: data.q, results, judge: data.judge as SearchResponse["judge"] }; // 개인화 정보 갱신 제안은 이번 공개 검색에서 사용하지 않아요.
} // 응답 확인을 마쳐요.
export function checkHit(raw: unknown): SearchHit { // 검색 결과 한 항목의 표시 필드를 확인해요.
    if (!raw || typeof raw !== "object") throw new Error("검색 결과 형식이 올바르지 않습니다."); // 항목은 객체여야 해요.
    const hit = raw as Record<string, unknown>; // 각 필드를 하나씩 확인해요.
    if (typeof hit.service_id !== "string" || !hit.service_id || typeof hit.name !== "string" || !["self", "parent"].includes(String(hit.subject)) || !(hit.badge === null || ["eligible", "similar", "needs_check", "ineligible", "no_rule"].includes(String(hit.badge)))) throw new Error("검색 결과 필드를 확인할 수 없습니다."); // 임의 배지나 알 수 없는 대상자는 표시하지 않아요.
    for (const field of ["rule_id", "org", "detail_url", "updated"]) if (hit[field] !== null && typeof hit[field] !== "string") throw new Error("검색 결과의 원문 정보를 확인할 수 없습니다."); // 원문 정보가 누락되면 오류로 구분해요.
    if (hit.region !== null && typeof hit.region !== "string") { // 지역은 API 구현의 시도·시군구 객체도 허용해요.
        if (!hit.region || typeof hit.region !== "object" || Array.isArray(hit.region)) throw new Error("지역 응답 형식이 올바르지 않습니다."); // 배열이나 다른 값을 지역명으로 출력하지 않아요.
        const region = hit.region as Record<string, unknown>; // 지역 객체의 표시 필드를 확인해요.
        for (const field of ["sido", "sigungu"]) if (region[field] != null && typeof region[field] !== "string") throw new Error("지역 이름을 확인할 수 없습니다."); // 지역명은 문자열만 허용해요.
        if (region.unknown !== undefined && typeof region.unknown !== "boolean") throw new Error("지역 상태를 확인할 수 없습니다."); // 지역 미상 여부는 불리언이어야 해요.
    } // 지역 검증을 마쳐요.
    if (hit.snippet === null || hit.snippet === undefined) hit.snippet = ""; // 요약이 비어 있는 공고는 빈 요약으로 보여줘요.
    if (typeof hit.snippet !== "string") throw new Error("검색 요약을 확인할 수 없습니다."); // HTML이 아닌 일반 문자열을 받아요.
    return hit as SearchHit; // 확인한 필드만 화면 계약으로 반환해요.
} // 한 항목 확인 함수를 마쳐요.
export async function searchPolicies(query: string, subject: SearchSubject, signal: AbortSignal): Promise<SearchResponse> { // 공개 검색의 네트워크 경계를 한 곳에 모아요.
    const base = `${window.location.origin}/api/backend`; // README에 정해진 공개 API 주소를 사용해요.
    const url = new URL(`${base.replace(/\/$/, "")}/search`); // 프론트 페이지 주소와 백엔드 경로를 구분해요.
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("검색 API 주소 설정을 확인해 주세요."); // 공개 설정에 비밀정보를 넣지 못하게 해요.
    url.searchParams.set("q", query); url.searchParams.set("limit", "20"); // 사용자 ID를 전달하지 않고 검색어를 안전하게 인코딩해요.
    if (subject !== "all") url.searchParams.set("subject", subject); // 전체 선택에서는 대상 조건을 보내지 않아요.
    const response = await fetch(url, { signal, credentials: "include", cache: "no-store", referrerPolicy: "no-referrer" }); // 로그인 세션 쿠키는 브라우저가 보내고 캐시·참조 주소는 남기지 않아요.
    if (!response.ok) throw new Error(response.status === 422 ? "검색 조건을 확인해 주세요." : "검색 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."); // 서버 내부 오류나 검색어를 로그에 출력하지 않아요.
    return parseResponse(await response.json()); // 정상 HTTP라도 응답 모양이 다르면 실패로 처리해요.
} // 공개 검색 호출을 마쳐요.
