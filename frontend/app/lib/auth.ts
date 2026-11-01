/** 인증 API 클라이언트 (POST /auth/signup·login·logout, GET /auth/me).
 *  세션은 서버가 HttpOnly 쿠키로 관리하므로 토큰을 직접 다루지 않아요.
 *  AGENTS.md §3: 키·토큰을 커밋하지 않는다 — API 주소만 환경변수로 받아요.
 */

import { api, ServiceError } from "./service-api"; // 세션과 같은 출처 요청·시간 제한·안전한 오류 처리를 함께 사용해요.

export class AuthError extends Error { // API 오류를 상태코드와 함께 전달해요.
    constructor(public readonly status: number, message: string) {
        super(message);
        this.name = "AuthError";
    }
}

// 내부 fetch 래퍼 — credentials: "include"로 HttpOnly 세션 쿠키를 주고받아요.
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    try { return (await api<T>(path, init)) ?? null as T; } // 느린 첫 기동에도 기다리되 빈 응답은 기존 계약대로 반환해요.
    catch (cause) { // 서버의 검증 객체나 입력값을 그대로 화면에 출력하지 않아요.
        if (!(cause instanceof ServiceError)) throw new AuthError(0, "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."); // 연결 오류를 사용자 안내로 바꿔요.
        const detail = cause.status === 401 && path === "/auth/login" ? "이메일 또는 비밀번호가 올바르지 않습니다." : cause.status === 409 ? "이미 사용 중인 이메일입니다. 로그인해 주세요." : cause.status === 429 ? "로그인 시도가 많습니다. 잠시 후 다시 시도해 주세요." : cause.message; // 인증 상황에 맞는 안내를 보여줘요.
        throw new AuthError(cause.status, detail); // 기존 폼이 처리하는 오류 형식을 유지해요.
    } // 인증 오류 처리를 마쳐요.
}

export interface MeResponse {
    account_id: string;
    email: string;
    user_id: string | null;
}

// 이메일·비밀번호로 계정을 만들고 세션 쿠키를 발급받아요.
export async function signup(email: string, password: string, nickname: string, consents: { terms: boolean; privacy: boolean }): Promise<{ account_id: string }> {
    return call("/auth/signup", { method: "POST", body: JSON.stringify({ email, password, nickname, consents }) }); // 닉네임과 필수 동의는 서버에 저장해요(동의 시각).
}

// 이메일·비밀번호로 로그인하고 세션 쿠키를 발급받아요.
export async function login(email: string, password: string): Promise<{ account_id: string }> {
    return call("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

// 현재 세션을 폐기하고 쿠키를 삭제해요.
export async function logout(): Promise<null> {
    return call("/auth/logout", { method: "POST" });
}

// 현재 세션의 계정 정보를 반환해요. 미로그인이면 AuthError(401)를 던져요.
export async function getMe(): Promise<MeResponse> {
    return call("/auth/me");
}

// 계정별 동의 내역과 닉네임을 안전하게 묶어 관리하는 데이터 규격이에요.
export interface AccountLocalData {
    // 계정별로 설정된 가상 닉네임이에요. 실명 대신 사용해요.
    nickname: string;
    // 회원가입 시 선택 및 동의한 약관과 민감정보·알림 선택 상태예요.
    consents: {
        // 서비스 이용약관 동의 여부예요.
        terms: boolean;
        // 개인정보 수집 및 이용 필수 동의 여부예요.
        privacy: boolean;
        // 이메일 알림 수신 선택 동의 여부예요.
        email: boolean;
        // 민감정보 처리 선택 동의 여부예요.
        sensitive: boolean;
    };
}

// 계정 식별자(account_id)별로 분리된 로컬스토리지 저장 키를 만들어요.
function accountKey(accountId: string): string {
    // 다른 계정과 닉네임 및 동의 정보가 섞이지 않도록 고유 키를 구성해요.
    return `zing_account_${accountId}`;
}

// 특정 계정에 저장된 닉네임과 선택 동의 정보를 안전하게 불러와요.
export function getAccountData(accountId: string): AccountLocalData | null {
    // 브라우저 로컬스토리지 접근 시 발생할 수 있는 보안 차단을 대비해요.
    try {
        // 계정 전용 키로 저장된 JSON 문자열을 가져와요.
        const raw = localStorage.getItem(accountKey(accountId));
        // 저장된 데이터가 없으면 비어있는 상태로 돌려줘요.
        if (!raw) return null;
        // JSON 문자열을 객체 형태로 변환하여 반환해요.
        return JSON.parse(raw) as AccountLocalData;
    } catch {
        // 스토리지 차단 환경에서는 안전하게 null을 반환해요.
        return null;
    }
}

// 특정 계정에 대한 닉네임과 선택 동의 정보를 계정별 키에 저장해요.
export function setAccountData(accountId: string, data: Partial<AccountLocalData>): void {
    // 브라우저 로컬스토리지 접근 시 발생할 수 있는 보안 차단을 대비해요.
    try {
        // 기존에 저장되어 있던 해당 계정의 데이터를 먼저 읽어와요.
        const prev = getAccountData(accountId) || {
            // 기본 닉네임은 빈 문자열로 초기화해요.
            nickname: "",
            // 기본 동의는 모두 false로 안전하게 시작해요.
            consents: { terms: false, privacy: false, email: false, sensitive: false },
        };
        // 새로 전달받은 데이터로 덮어써서 최신 상태 객체를 구성해요.
        const updated: AccountLocalData = {
            // 닉네임이 전달되었으면 갱신하고 아니면 기존 값을 유지해요.
            nickname: data.nickname !== undefined ? data.nickname : prev.nickname,
            // 동의 정보가 전달되었으면 갱신하고 아니면 기존 값을 유지해요.
            consents: data.consents ? { ...prev.consents, ...data.consents } : prev.consents,
        };
        // 계정 전용 고유 키에 JSON 문자열로 직렬화하여 저장해요.
        localStorage.setItem(accountKey(accountId), JSON.stringify(updated));
    } catch {
        // 스토리지 접근이 차단되어도 화면 동작이 멈추지 않도록 예외를 흡수해요.
    }
}
