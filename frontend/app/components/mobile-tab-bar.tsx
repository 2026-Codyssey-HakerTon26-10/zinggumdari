"use client"; // 현재 주소를 읽어 선택된 탭을 표시해야 해서 브라우저에서 동작해요.
import Link from "next/link"; // 페이지를 새로 불러오지 않고 탭 사이를 이동해요.
import { usePathname } from "next/navigation"; // 지금 보고 있는 화면 주소를 읽어요.
import type { ReactNode } from "react"; // 바깥에서 받은 아이콘의 형식이에요.

type Tab = { href: string; label: string; icon: ReactNode }; // 탭 하나의 주소, 이름, 아이콘이에요.

function isActive(pathname: string, href: string): boolean { // 지금 주소가 이 탭에 속하는지 판단해요.
    return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`); // 홈은 정확히 같을 때만, 나머지는 하위 화면까지 같은 탭으로 봐요.
} // 선택 판단을 마쳐요.

export function MobileTabBar({ tabs }: { tabs: Tab[] }) { // 휴대전화 화면 아래에 고정되는 주요 메뉴예요.
    const pathname = usePathname(); // 현재 화면 주소예요.
    return <nav className="mobile-tab-bar" aria-label="하단 주요 메뉴"> {/* 엄지로 누르기 쉬운 화면 아래쪽에 메뉴를 둬요. */}
        {tabs.map((tab) => { const active = isActive(pathname, tab.href); return <Link key={tab.href} href={tab.href} aria-current={active ? "page" : undefined}>{tab.icon}<span>{tab.label}</span></Link>; })} {/* 선택된 탭은 aria-current로 보조기기에도 알려요. */}
    </nav>; // 하단 메뉴를 마쳐요.
} // 하단 탭 메뉴 컴포넌트를 마쳐요.
