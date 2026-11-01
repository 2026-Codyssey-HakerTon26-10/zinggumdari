"use client"; // 화면 이동은 브라우저에서 일어나서 클라이언트 컴포넌트로 만들어요.
import { useEffect, useRef } from "react"; // 주소가 바뀐 뒤 스크롤을 옮기고 첫 화면인지 기억해요.
import { usePathname } from "next/navigation"; // 다른 화면으로 옮겼는지 주소로 확인해요.

export function ScrollReset() { // 다른 화면으로 이동하면 맨 위부터 보여줘요.
    const pathname = usePathname(); // 지금 보고 있는 화면 주소예요.
    const first = useRef(true); // 처음 연 화면은 브라우저의 새로고침 위치 복원을 그대로 둬요.
    useEffect(() => { // 주소가 바뀔 때마다 실행해요.
        if (first.current) { first.current = false; return; } // 첫 로드는 건드리지 않아요.
        if (window.location.hash) return; // '/#how-it-works' 같은 해시 이동은 그 위치로 가야 해서 건드리지 않아요.
        window.scrollTo({ top: 0, left: 0, behavior: "instant" }); // sticky 헤더 때문에 Next가 남겨 둔 이전 화면의 스크롤 위치를 맨 위로 되돌려요.
    }, [pathname]); // 화면 주소가 바뀔 때만 실행해요.
    return null; // 화면에 그리는 것은 없어요.
} // 스크롤 초기화 컴포넌트를 마쳐요.
