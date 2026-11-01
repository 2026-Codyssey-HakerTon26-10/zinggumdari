import snapshotData from "./search-snapshot.json"; // 서버가 응답하지 않을 때 보여줄, 배포 서버에서 저장해 둔 실제 검색 결과예요.
import { checkHit, type SearchResponse, type SearchSubject } from "./search-api"; // 서버 응답과 같은 형식 검사를 저장 결과에도 써요.
const snapshot = snapshotData as { saved_at: string; queries: Record<string, unknown[]> }; // 저장 날짜와 추천 검색어별 결과예요.
export function snapshotSearch(query: string, subject: SearchSubject): SearchResponse { // 서버가 실패했을 때 저장해 둔 결과에서 찾아요.
    const normalize = (text: string) => text.replace(/[#\s]/g, "").toLowerCase(); // 띄어쓰기와 # 차이를 무시해요.
    const key = Object.keys(snapshot.queries).find((name) => normalize(name) === normalize(query)); // 추천 검색어와 같으면 그 결과를 그대로 써요.
    const pool = key ? snapshot.queries[key] : Object.values(snapshot.queries).flat(); // 다른 검색어는 저장된 전체 결과에서 찾아요.
    const tokens = query.split(/\s+/).map(normalize).filter(Boolean); // 검색어를 낱말로 나눠요.
    const seen = new Set<string>(); // 여러 검색어에 겹친 공고를 한 번만 보여줘요.
    const results = pool.flatMap((raw) => { try { return [checkHit(structuredClone(raw))]; } catch { return []; } }).filter((hit) => { // 저장 파일도 같은 형식 검사를 거쳐요.
        if (seen.has(hit.service_id)) return false; seen.add(hit.service_id); // 중복을 빼요.
        if (subject !== "all" && hit.subject !== subject) return false; // 선택한 대상만 남겨요.
        const text = normalize(`${hit.name} ${hit.snippet} ${hit.org ?? ""}`); // 이름·요약·기관에서 찾아요.
        return Boolean(key) || tokens.some((token) => text.includes(token)); // 추천 검색어가 아니면 낱말이 들어간 공고만 남겨요.
    }); // 저장 결과 걸러내기를 마쳐요.
    return { q: query, results, judge: "engine", snapshot: snapshot.saved_at }; // 개인화 배지 없이 저장 날짜와 함께 돌려줘요.
} // 저장 결과 검색을 마쳐요.
