import type { Metadata } from "next"; // 로그인 화면의 제목과 설명 형식을 가져옵니다.
import { AuthForm } from "../../components/auth-form"; // 로그인과 회원가입이 함께 사용하는 폼을 가져옵니다.
export const metadata: Metadata = { title: "로그인 | 징검다리", description: "로그인하고 나에게 맞는 제도와 다음 걸음을 이어서 확인하세요." }; // 브라우저에 로그인 화면의 이름을 표시합니다.
export default function LoginPage() { // 로그인 주소에서 보여줄 화면을 정합니다.
    return <AuthForm mode="login" />; // 공통 폼을 로그인 방식으로 표시합니다.
} // 로그인 화면을 마칩니다.
