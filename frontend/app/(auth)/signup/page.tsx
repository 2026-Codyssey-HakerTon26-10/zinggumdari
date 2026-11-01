import type { Metadata } from "next"; // 회원가입 화면의 제목과 설명 형식을 가져옵니다.
import { AuthForm } from "../../components/auth-form"; // 로그인과 회원가입이 함께 사용하는 폼을 가져옵니다.
export const metadata: Metadata = { title: "회원가입", description: "징검다리에 가입하고 나에게 맞는 공공 제도를 살펴보세요." }; // 브라우저에 회원가입 화면의 이름을 표시합니다.
export default function SignupPage() { // 회원가입 주소에서 보여줄 화면을 정합니다.
    return <AuthForm mode="signup" />; // 공통 폼을 회원가입 방식으로 표시합니다.
} // 회원가입 화면을 마칩니다.
