/* eslint-disable @typescript-eslint/no-require-imports -- Node가 직접 실행하는 CommonJS 검사 스크립트라 require를 사용해요. */
const test = require("node:test"); // Node 기본 테스트 도구로 API 요청 계약을 검사해요.
const assert = require("node:assert/strict"); // 실제 결과가 기대한 값과 같은지 확인해요.
const { readFileSync } = require("node:fs"); // 검사할 프런트 소스만 읽어요.
const { resolve } = require("node:path"); // 실행 위치와 상관없이 프런트 소스를 찾아요.
const vm = require("node:vm"); // 실제 서버 대신 격리한 메모리 안에서 코드를 실행해요.
const ts = require("typescript"); // 이미 설치된 TypeScript로 소스를 메모리에서 변환해요.
const root = resolve(__dirname, ".."); // 이 스크립트가 속한 프런트 폴더를 기준으로 삼아요.
function harness() { // 각 검사가 서로 다른 가짜 서버와 환경을 사용하게 해요.
    const calls = []; // 요청 주소와 옵션만 메모리에 모아요.
    let reply = () => { throw new Error("가짜 응답을 먼저 지정해야 합니다"); }; // 설정을 빠뜨려도 실제 네트워크로 나가지 않아요.
    const context = vm.createContext({ AbortSignal, FormData, URL, process: { env: {} }, fetch: async (...args) => { calls.push(args); return reply(...args); } }); // 환경 파일과 실제 fetch를 전달하지 않아요.
    function load(path, imports = {}) { // 지정한 TypeScript 모듈을 CommonJS 형태로 불러와요.
        const source = readFileSync(resolve(root, path), "utf8"); // 테스트 대상 소스만 읽고 환경 파일은 읽지 않아요.
        const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText; // 파일을 생성하지 않고 TypeScript 문법만 변환해요.
        const loadedModule = { exports: {} }; // 모듈이 내보내는 함수와 형식을 받을 상자예요.
        const requireMock = (name) => { if (!(name in imports)) throw new Error("예상하지 않은 모듈 요청"); return imports[name]; }; // 허용하지 않은 의존성이나 파일은 불러올 수 없어요.
        vm.compileFunction(code, ["exports", "require", "module"], { parsingContext: context })(loadedModule.exports, requireMock, loadedModule); // 격리한 fetch와 환경만 사용하는 모듈을 만들어요.
        return loadedModule.exports; // 변환한 모듈의 공개 함수를 돌려줘요.
    } // 메모리 모듈 로더를 마쳐요.
    const service = load("app/lib/service-api.ts"); // 공통 요청 코드를 실제 소스에서 가져와요.
    const auth = load("app/lib/auth.ts", { "./service-api": service }); // 인증 코드가 같은 공통 요청 모듈을 사용하게 해요.
    return { calls, auth, service, load, env: context.process.env, respond: (response) => { reply = typeof response === "function" ? response : () => response; } }; // 검사에 필요한 가짜 응답과 공개 함수만 제공해요.
} // 검사별 격리 환경을 마쳐요.
function json(status, body) { // HTTP 상태와 JSON 본문을 가진 가짜 응답을 만들어요.
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); // 실제 fetch의 Response 처리 경로를 그대로 검사해요.
} // JSON 응답 도우미를 마쳐요.
test("가입은 같은 출처에 쿠키와 필수 동의를 전송하고 응답을 캐시하지 않는다", async () => { // 가입 요청 계약이 바뀌는 회귀를 막아요.
    const h = harness(); h.respond(json(201, { account_id: "test-account" })); // 실제 계정을 만들지 않는 응답이에요.
    const result = await h.auth.signup("sample@example.test", "test-only-password", "가상사용자", { terms: true, privacy: true }); // 전부 가상 값으로 가입 함수를 호출해요.
    assert.equal(result.account_id, "test-account"); // 서버가 돌려준 계정 식별자를 보존해야 해요.
    const [url, init] = h.calls[0]; // 가짜 서버에 전달된 요청을 살펴봐요.
    assert.equal(url, "/api/backend/auth/signup"); assert.equal(init.method, "POST"); // 같은 출처 프록시로 가입 요청을 보내야 해요.
    assert.equal(init.credentials, "include"); assert.equal(init.cache, "no-store"); assert.equal(init.referrerPolicy, "no-referrer"); // 쿠키는 포함하고 계정 응답과 이전 주소는 남기지 않아요.
    assert.equal(init.headers["Content-Type"], "application/json"); assert.ok(init.signal instanceof AbortSignal); // 요청 형식과 시간 제한을 유지해야 해요.
    assert.deepEqual(JSON.parse(init.body), { email: "sample@example.test", password: "test-only-password", nickname: "가상사용자", consents: { terms: true, privacy: true } }); // 필수 동의와 닉네임을 빠뜨리지 않아야 해요.
}); // 가입 요청 검사를 마쳐요.
test("로그인 401은 계정 존재를 드러내지 않는 안내가 된다", async () => { // 잘못된 비밀번호를 세션 만료로 안내하지 않게 해요.
    const h = harness(); h.respond(json(401, { detail: "테스트 서버 원문" })); // 인증 거절 응답을 재현해요.
    await assert.rejects(h.auth.login("sample@example.test", "wrong-test-password"), (error) => error instanceof h.auth.AuthError && error.status === 401 && error.message === "이메일 또는 비밀번호가 올바르지 않습니다."); // 로그인 실패 전용 안내를 확인해요.
}); // 로그인 거절 검사를 마쳐요.
test("가입 409는 중복 이메일 안내가 된다", async () => { // 중복 계정을 프로필 중복으로 안내하지 않게 해요.
    const h = harness(); h.respond(json(409, { detail: "중복" })); // 중복 응답을 가짜 서버에서 돌려줘요.
    await assert.rejects(h.auth.signup("sample@example.test", "test-only-password", "가상사용자", { terms: true, privacy: true }), (error) => error instanceof h.auth.AuthError && error.status === 409 && error.message === "이미 사용 중인 이메일입니다. 로그인해 주세요."); // 가입 상황에 맞는 안내를 확인해요.
}); // 중복 가입 검사를 마쳐요.
test("로그인 429는 잠시 기다리도록 안내한다", async () => { // 반복 로그인 제한을 연결 오류로 숨기지 않게 해요.
    const h = harness(); h.respond(json(429, { detail: "반복 요청" })); // 요청 제한 상태를 재현해요.
    await assert.rejects(h.auth.login("sample@example.test", "test-only-password"), (error) => error instanceof h.auth.AuthError && error.status === 429 && error.message === "로그인 시도가 많습니다. 잠시 후 다시 시도해 주세요."); // 제한 안내와 상태를 보존해야 해요.
}); // 요청 제한 검사를 마쳐요.
test("422 검증 배열의 입력값은 오류 안내에 노출되지 않는다", async () => { // 서버가 돌려준 비밀번호 같은 원래 입력을 화면에 내보내지 않아요.
    const h = harness(); h.respond(json(422, { detail: [{ loc: ["body", "password"], msg: "invalid", input: "PRIVATE_TEST_MARKER" }] })); // 민감한 입력을 포함할 수 있는 검증 형식을 재현해요.
    await assert.rejects(h.auth.login("sample@example.test", "test-only-password"), (error) => error instanceof h.auth.AuthError && error.status === 422 && !/PRIVATE_TEST_MARKER|password|invalid/.test(error.message)); // 상태는 유지하면서 원래 입력과 검증 객체는 숨겨야 해요.
}); // 검증 정보 보호 검사를 마쳐요.
test("500 JSON의 내부 오류는 사용자에게 노출되지 않는다", async () => { // 서버 내부 메시지가 화면 안내로 새지 않게 해요.
    const h = harness(); h.respond(json(500, { detail: "PRIVATE_TEST_MARKER" })); // 서버 내부 오류를 가정한 응답이에요.
    await assert.rejects(h.auth.getMe(), (error) => error instanceof h.auth.AuthError && error.status === 500 && !error.message.includes("PRIVATE_TEST_MARKER")); // 내부 문자열을 제거한 안전한 오류여야 해요.
}); // 서버 오류 정보 보호 검사를 마쳐요.
test("500 HTML은 JSON 파싱 예외 대신 안전한 서버 오류가 된다", async () => { // 프록시가 HTML 오류 페이지를 반환하는 경우를 확인해요.
    const h = harness(); h.respond(new Response("<html>PRIVATE_TEST_MARKER</html>", { status: 500, headers: { "Content-Type": "text/html" } })); // 프록시 오류 페이지를 가짜로 만들어요.
    await assert.rejects(h.auth.getMe(), (error) => error instanceof h.auth.AuthError && error.status === 500 && !error.message.includes("PRIVATE_TEST_MARKER")); // HTML이나 파싱 오류를 화면에 그대로 보여주면 안 돼요.
}); // HTML 오류 응답 검사를 마쳐요.
test("깨진 성공 JSON을 로그인 성공으로 처리하지 않는다", async () => { // 응답이 깨졌는데도 성공 화면으로 이동하는 회귀를 막아요.
    const h = harness(); h.respond(new Response("{broken", { status: 200, headers: { "Content-Type": "application/json" } })); // 정상 상태코드와 깨진 본문을 조합해요.
    await assert.rejects(h.auth.getMe(), (error) => error instanceof h.auth.AuthError && error.status === 502); // 성공 상태여도 유효한 응답이 없으면 실패해야 해요.
}); // 깨진 응답 검사를 마쳐요.
test("로그아웃 204는 빈 응답을 null로 반환한다", async () => { // 정상 로그아웃을 JSON 파싱 실패로 오해하지 않게 해요.
    const h = harness(); h.respond(new Response(null, { status: 204 })); // 본문 없는 정상 응답을 만들어요.
    assert.equal(await h.auth.logout(), null); assert.equal(h.calls[0][0], "/api/backend/auth/logout"); assert.equal(h.calls[0][1].method, "POST"); // 빈 응답과 로그아웃 경로를 확인해요.
}); // 로그아웃 검사를 마쳐요.
test("네트워크 예외는 원문 없이 AuthError로 바뀐다", async () => { // 내부 주소나 토큰을 포함할 수 있는 예외를 그대로 노출하지 않아요.
    const h = harness(); h.respond(() => { throw new Error("PRIVATE_TEST_MARKER"); }); // 외부 네트워크를 사용하지 않고 연결 실패만 재현해요.
    await assert.rejects(h.auth.getMe(), (error) => error instanceof h.auth.AuthError && error.status === 0 && !error.message.includes("PRIVATE_TEST_MARKER")); // 안전한 연결 안내와 오류 형식을 확인해요.
}); // 연결 실패 검사를 마쳐요.
test("공개 API 별칭과 인증 프록시는 같은 원점의 실제 경로를 사용한다", async () => { // 서로 다른 서버나 잘못된 API 접두사로 연결되는 회귀를 막아요.
    const h = harness(); h.env.NEXT_PUBLIC_API_BASE = "https://backend.example.test/"; // 실제 환경변수 대신 공개 테스트 주소만 사용해요.
    const config = h.load("next.config.ts").default; const routes = await config.rewrites(); // Next 설정의 실제 rewrite 함수를 실행해요.
    const destinations = new Map(routes.map((route) => [route.source, route.destination])); // 선언한 경로를 이름으로 찾아요.
    assert.equal(destinations.get("/api/backend/:path*"), "https://backend.example.test/:path*"); // 세션 프록시는 원래 API 경로를 그대로 전달해야 해요.
    assert.equal(destinations.get("/api/health"), "https://backend.example.test/health"); assert.equal(destinations.get("/api/search"), "https://backend.example.test/search"); // 공개 별칭도 백엔드의 실제 루트 경로로 연결해야 해요.
}); // 프록시 계약 검사를 마쳐요.
test("검색 원문의 숫자 기준일을 표시하되 잘못된 날짜는 보정하지 않는다", () => { // 원문 날짜를 읽기 쉽게 표시하면서 사실을 바꾸지 않아요.
    const { formatSourceDate } = harness().load("app/search/search-api.ts"); // 네트워크 호출 없이 날짜 표시 함수만 가져와요.
    assert.equal(formatSourceDate("2026081413"), "2026-08-14"); assert.equal(formatSourceDate("20260814"), "2026-08-14"); // 실제 API의 숫자 날짜 형식을 확인해요.
    assert.equal(formatSourceDate("2026-08-14"), "2026-08-14"); assert.equal(formatSourceDate("20260230"), "20260230"); // 기존 날짜와 잘못된 원문은 그대로 유지해요.
    assert.equal(formatSourceDate(null), "원문에서 확인 필요"); // 결측 날짜를 임의로 만들지 않아요.
}); // 검색 기준일 검사를 마쳐요.
