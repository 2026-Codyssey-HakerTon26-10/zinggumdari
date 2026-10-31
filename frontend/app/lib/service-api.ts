export const API_BASE = "/api/backend"; // 기존 API 주소 설정을 모든 서비스에서 사용해요.
export class ServiceError extends Error { constructor(public status: number, message: string) { super(message); } } // 화면에서 인증·연결 실패를 구분해요.
export async function api<T>(path: string, init: RequestInit = {}, timeoutMs = 90000): Promise<T> { // 배포 서버의 첫 기동을 기다리는 시간과 세션 요청을 함께 관리해요.
    const timeout = AbortSignal.timeout(timeoutMs); // 응답이 없는 요청을 무한히 기다리지 않아요.
    let response: Response; // HTTP 응답을 받아요.
    try { response = await fetch(`${API_BASE}${path}`, { ...init, credentials: "include", cache: "no-store", referrerPolicy: "no-referrer", signal: init.signal ? AbortSignal.any([init.signal, timeout]) : timeout, headers: init.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init.headers } }); } // 파일의 multipart 경계는 브라우저가 만들어요.
    catch (error) { if (init.signal?.aborted) throw error; throw new ServiceError(0, "서버에 연결하지 못했습니다. 첫 연결은 시간이 걸릴 수 있어요. 잠시 후 다시 시도해 주세요."); } // 입력값이나 내부 설정을 오류 안내에 넣지 않아요.
    if (response.status === 204) return undefined as T; // 삭제·로그아웃의 빈 응답을 처리해요.
    const body = await response.json().catch(() => null); // HTML 오류 페이지를 결과로 오해하지 않아요.
    if (!response.ok) throw new ServiceError(response.status, response.status === 401 ? "로그인이 필요합니다. 다시 로그인해 주세요." : response.status === 404 ? "정보를 찾지 못했습니다. 새로고침해 주세요." : response.status === 409 ? "이미 프로필이 있습니다. 새로고침해 주세요." : typeof body?.detail === "string" && response.status < 500 ? body.detail : "서버에서 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."); // 서버 내부 메시지·검증 입력값을 그대로 노출하지 않아요.
    if (!body || typeof body !== "object") throw new ServiceError(502, "서버 응답을 확인할 수 없습니다."); // 깨진 응답은 성공으로 표시하지 않아요.
    return body as T; // API 계약에 따라 호출한 화면에 전달해요.
} // 공통 요청을 마쳐요.
export type Fields = Record<string, string | number | boolean | null>; // 시트 칸에 해당하는 원값만 저장해요.
export type Qualification = { qual_code: string; target: string; verified: string; has?: string }; // 자격은 코드표의 한 줄로 저장해요.
export type FullProfile = { user_id: string; self: Record<string, unknown> & { nickname?: string; qualifications?: Qualification[] }; parents: Fields[]; consents: { sensitive: boolean; parent: boolean }; stages_done: string[] }; // 배열 자격을 포함한 실제 프로필을 보존해요.
export type Me = { account_id: string; email: string; user_id: string | null; nickname?: string | null }; // 계정 토큰 없이 세션 소유 정보만 받아요.
export type Evidence = { id: string; page: number | null; bbox: number[] | null; text: string | null }; // 근거 위치는 서버 응답만 사용해요.
export type Condition = { read_as: string; grade: string; ok: boolean | null; why?: string; evidence: Evidence[]; checks?: Record<string, string> }; // 카드 조건과 검증 상태예요.
export type DocumentInfo = { name: string; status: string; who_provides?: string; issuer?: string; online?: string; offline?: string; fee?: string }; // 발급처를 서버에서 받아요.
export type Card = { rule_id: string; subject: "self" | "parent"; relation?: string; name: string; verdict: string; ai_extracted?: boolean; review?: string; conditions: Condition[]; detail_url?: string | null; updated?: string | null; explain?: string; documents?: DocumentInfo[]; deadline?: string | null }; // 실제 판정 카드의 표시 필드예요.
export type Todo = { action: string; read_as?: string; status?: string; evidence: string[] }; // 근거 없는 해둘 일은 표시하지 않아요.
export type TimelineStep = { step: string; assume?: Fields; opens: string[]; closes?: string[]; todo?: Todo[]; relation?: string; year?: number; why?: string; apply_from?: string }; // 본인·부모님 타임라인의 공통 모양이에요.
export type QuestionOption = { label: string; value: string | number | null; set?: Fields | null; unit?: string; add_qualification?: Qualification }; // 서버가 제공하는 답변만 매핑해요.
export type Question = { subject: "self" | "parent"; relation?: string; field: string; question: string; why?: string; rule_id?: string; options: QuestionOption[] }; // 공고별 한 칸 질문의 계약이에요.
export type Judge = { cards: Card[]; ask: Question | null; timeline: { self: TimelineStep[]; parent: TimelineStep[]; dated?: { what: string; year?: number; date?: string }[] }; disclaimer?: string; similar?: { basis: string; label: string; neighbors: number; items: { rule_id: string; name: string; prevalence: number; blocking_fields: string[] }[] } | null }; // 추천과 타임라인은 한 응답으로 갱신해요.
export type Stage = "" | "newlywed" | "child" | "multi_child"; // 모의 단계와 현재 프로필을 구분해요.
export const me = (signal?: AbortSignal) => api<Me>("/auth/me", { signal }); // 매번 서버 세션으로 본인 계정을 확인해요.
export const getProfile = (id: string, signal?: AbortSignal) => api<FullProfile>(`/profiles/${encodeURIComponent(id)}`, { signal }); // 세션 소유 프로필만 조회해요.
export const patchProfile = (id: string, data: object) => api<FullProfile>(`/profiles/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(data) }); // 화면의 명시적 저장만 서버에 반영해요.
export const judge = (step: Stage, rule_id?: string, signal?: AbortSignal) => api<Judge>("/judge", { method: "POST", body: JSON.stringify({ step: step || null, rule_id: rule_id || null }), signal }); // 클라이언트 사용자 ID로 판정 대상을 바꾸지 않아요.
export function message(error: unknown) { return error instanceof ServiceError ? error.message : "요청을 완료하지 못했습니다. 다시 시도해 주세요."; } // 알 수 없는 오류의 내부 정보는 숨겨요.
export function safeLink(value?: string | null) { try { const url = new URL(value || ""); return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null; } catch { return null; } } // 외부 링크는 HTTP(S)만 허용해요.
