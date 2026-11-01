export const SIGNUP_EMAIL_PATTERN = String.raw`(?=.{1,64}@)[A-Za-z0-9!#$%&'*+\/=?^_\x60\{\|\}~\-]+(?:\.[A-Za-z0-9!#$%&'*+\/=?^_\x60\{\|\}~\-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}`; // 점으로 빈 부분을 만들지 않는 ASCII 이메일과 올바른 도메인 이름만 받아요.
export const SIGNUP_PASSWORD_PATTERN = String.raw`(?=.*[A-Za-z])(?=.*[0-9])[\x21-\x7E]{8,128}`; // 공백이나 한글 없이 영문과 숫자가 들어간 8~128자 비밀번호를 받아요.
export function validSignupEmail(value: string): boolean { // 가입할 이메일의 길이와 점·도메인 형식을 검사해요.
    return value.length <= 254 && value.split("@")[0].length <= 64 && new RegExp(`^(?:${SIGNUP_EMAIL_PATTERN})$`, "v").exec(value)?.[0] === value; // 전체 입력이 일치해야 하므로 마지막 줄바꿈도 허용하지 않아요.
} // 가입 이메일 검사를 마쳐요.
export function validSignupPassword(value: string): boolean { // 새 가입에만 엄격한 비밀번호 규칙을 적용해요.
    return new RegExp(`^(?:${SIGNUP_PASSWORD_PATTERN})$`, "v").exec(value)?.[0] === value; // 기존 계정 로그인은 그대로 두고 새 비밀번호의 마지막 줄바꿈까지 거부해요.
} // 비밀번호 검사를 마쳐요.
export function validSignupNickname(value: string): boolean { // 앞뒤 공백을 제외한 닉네임 길이를 확인해요.
    const length = value.trim().length; return length >= 2 && length <= 16; // 서버에 보낼 닉네임과 같은 값으로 검사해요.
} // 닉네임 검사를 마쳐요.
export function validPasswordConfirmation(password: string, confirmation: string): boolean { // 비밀번호 확인은 빈 값이 아니고 원래 입력과 같아야 해요.
    return confirmation.length > 0 && password === confirmation; // 공백을 임의로 지우거나 비밀번호를 다른 값으로 바꾸지 않아요.
} // 비밀번호 확인 검사를 마쳐요.
export type AuthDestination = "/my" | "/my?subject=parent"; // 인증 뒤 이동 가능한 내부 화면 두 개만 허용해요.
export function safeNextDestination(next: string | null | undefined): AuthDestination { // 임의 URL이나 실행 코드를 인증 뒤 이동에 사용하지 않아요.
    return next === "/my?subject=parent" ? next : "/my"; // 부모님 추천을 명시한 경우만 보존하고 나머지는 내 추천으로 이동해요.
} // 안전한 다음 화면 선택을 마쳐요.
export function authDestinationFromSearch(search: string): AuthDestination { // 화면을 제출하는 순간의 next 값을 안전하게 읽어요.
    return safeNextDestination(new URLSearchParams(search).get("next")); // 정적 렌더링에서 URL 훅을 읽지 않아도 돼요.
} // 인증 주소 해석을 마쳐요.
export function authEntryHref(mode: "login" | "signup", destination: string): string { // 로그인과 가입을 오가도 선택한 추천 대상을 유지해요.
    return `/${mode}?next=${encodeURIComponent(safeNextDestination(destination))}`; // 허용된 내부 주소만 쿼리에 넣어요.
} // 인증 화면 링크 생성을 마쳐요.
