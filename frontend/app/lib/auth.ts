/** 인증 API 클라이언트 (POST /auth/signup·login·logout, GET /auth/me).
 *  세션은 서버가 HttpOnly 쿠키로 관리하므로 토큰을 직접 다루지 않아요.
 *  AGENTS.md §3: 키·토큰을 커밋하지 않는다 — API 주소만 환경변수로 받아요.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"; // 환경변수가 없으면 로컬 기본값을 사용해요.

export class AuthError extends Error { // API 오류를 상태코드와 함께 전달해요.
    constructor(public readonly status: number, message: string) {
        super(message);
        this.name = "AuthError";
    }
}

// 내부 fetch 래퍼 — credentials: "include"로 HttpOnly 세션 쿠키를 주고받아요.
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
        credentials: "include", // cross-origin 세션 쿠키 전송에 필수예요.
        headers: { "Content-Type": "application/json", ...init.headers },
        ...init,
    });
    if (res.status === 204) return null as T; // 빈 응답(logout 등)은 null을 반환해요.
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new AuthError(res.status, body.detail ?? "오류가 발생했습니다.");
    return body as T;
}

export interface MeResponse {
    account_id: string;
    email: string;
    user_id: string | null;
}

// 이메일·비밀번호로 계정을 만들고 세션 쿠키를 발급받아요.
export async function signup(email: string, password: string): Promise<{ account_id: string }> {
    return call("/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) });
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
