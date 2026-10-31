"use client"; // 설정 화면들이 세션 소유 프로필을 함께 사용해요.
import { useEffect, useState } from "react"; // 요청이 끝난 뒤에만 계정 정보를 표시해요.
import { me, getProfile, message, type FullProfile } from "../../lib/service-api"; // 서버가 선택한 본인 프로필만 가져와요.
export function useProfile() { // 설정 화면의 공통 읽기 흐름이에요.
    const [profile, setProfile] = useState<FullProfile | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(true); // 오류와 프로필 없음은 구분해요.
    useEffect(() => { const controller = new AbortController(); void me(controller.signal).then((account) => account.user_id ? getProfile(account.user_id, controller.signal) : null).then((data) => { if (!controller.signal.aborted) setProfile(data); }).catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, []); // 화면 이탈 시 이전 계정 응답을 반영하지 않아요.
    return { profile, setProfile, error, loading }; // 저장 성공 후 응답으로 현재 화면을 갱신해요.
} // 프로필 조회 훅을 마쳐요.
