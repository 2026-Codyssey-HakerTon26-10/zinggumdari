import { LoadingState } from "./components/loading-state"; // 화면 전환에도 같은 로딩 표시를 사용해요.
export default function Loading() { // 다음 페이지의 코드나 내용을 기다릴 때 보여줘요.
    return <main id="main-content" className="container" style={{ paddingBlock: 48 }}><LoadingState label="화면을 불러오고 있습니다." /></main>; // 빈 화면 대신 다음 화면을 준비 중이라고 알려줘요.
} // 페이지 전환 로딩을 마쳐요.
