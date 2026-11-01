/* eslint-disable @typescript-eslint/no-require-imports -- 설치 없이 Node에서 직접 실행하는 CommonJS 검사예요. */
const test = require("node:test"); // 기본 테스트 도구를 사용해요.
const assert = require("node:assert/strict"); // 허용·거부 결과를 확인해요.
const { readFileSync } = require("node:fs"); // 검증 함수의 소스만 읽어요.
const { resolve } = require("node:path"); // 실행 위치와 무관하게 소스를 찾아요.
const vm = require("node:vm"); // 브라우저나 네트워크가 없는 메모리에서 검사해요.
const ts = require("typescript"); // 이미 설치된 변환 도구를 사용해요.
const source = readFileSync(resolve(__dirname, "../app/lib/auth-validation.ts"), "utf8"); // 환경 파일이나 계정 정보는 읽지 않아요.
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText; // 디스크에 파일을 만들지 않고 함수만 변환해요.
const loadedModule = { exports: {} }; // 공개 함수만 담을 상자예요.
vm.compileFunction(code, ["exports", "require", "module"], { parsingContext: vm.createContext({ URLSearchParams }) })(loadedModule.exports, () => { throw new Error("외부 모듈은 허용하지 않습니다"); }, loadedModule); // 실제 fetch나 process를 제공하지 않아요.
const validation = loadedModule.exports; // UI가 사용하는 실제 검증 함수를 검사해요.
for (const email of ["person@example.com", "first.last+tag@sub.example.co.kr", "USER_1@example.test", "o'connor@example.com", `${"a".repeat(64)}@example.com`]) { // 흔한 별칭과 최대 길이의 주소를 확인해요.
    test(`가입 이메일 허용: ${email}`, () => { assert.equal(validation.validSignupEmail(email), true); assert.equal(new RegExp(`^(?:${validation.SIGNUP_EMAIL_PATTERN})$`, "v").test(email), true); }); // HTML과 제출 검사가 같은 정상 주소를 허용해야 해요.
} // 정상 이메일 검사를 마쳐요.
for (const email of ["", " name@example.com", "name@example.com ", "name@example.com\n", "na me@example.com", ".name@example.com", "name.@example.com", "first..last@example.com", "name@@example.com", "name@example", "name@-example.com", "name@example-.com", "name@exam_ple.com", "name@example..com", "name@example.c", "사용자@example.com", "name@예시.com", `${"a".repeat(65)}@example.com`, `a@${"b".repeat(64)}.com`]) { // 공백·점·도메인·ASCII·길이 경계를 검사해요.
    test(`가입 이메일 거부: ${JSON.stringify(email)}`, () => { assert.equal(validation.validSignupEmail(email), false); }); // 잘못된 주소로 가입 요청을 보내면 안 돼요.
} // 잘못된 이메일 검사를 마쳐요.
for (const password of ["Abcdefg1", "test1234!", `A1${"x".repeat(126)}`]) { // 영문과 숫자를 포함한 길이 경계를 확인해요.
    test(`가입 비밀번호 허용: 길이 ${password.length}`, () => { assert.equal(validation.validSignupPassword(password), true); }); // 정상 비밀번호에 임의로 더 강한 규칙을 요구하지 않아요.
} // 정상 비밀번호 검사를 마쳐요.
for (const password of ["", "Abc1234", "abcdefgh", "12345678", "가나다abc123", "Abcd123 ", "Abcd\t123", "Abcd123\n", "Abcd1234\n", "Abcd1234\r\n", "Abcd123😀", `A1${"x".repeat(127)}`]) { // 한글·공백·줄바꿈·너무 짧거나 긴 값을 확인해요.
    test(`가입 비밀번호 거부: 사례 ${JSON.stringify(password.slice(0, 12))}`, () => { assert.equal(validation.validSignupPassword(password), false); }); // 원래 비밀번호를 조용히 바꾸지 않고 명확히 거부해야 해요.
} // 잘못된 비밀번호 검사를 마쳐요.
test("닉네임은 저장할 값과 같은 앞뒤 공백 제외 길이로 검사한다", () => { // 화면과 서버에 보내는 닉네임 기준을 맞춰요.
    assert.equal(validation.validSignupNickname("  가상  "), true); assert.equal(validation.validSignupNickname(" 가 "), false); assert.equal(validation.validSignupNickname(" "), false); // 공백으로 최소 길이를 채울 수 없어야 해요.
    assert.equal(validation.validSignupNickname("가".repeat(16)), true); assert.equal(validation.validSignupNickname("가".repeat(17)), false); // 최대 길이 경계도 확인해요.
}); // 닉네임 검사를 마쳐요.
test("비밀번호 확인은 빈 값이나 다른 입력을 거부한다", () => { // 비밀번호 확인 규칙을 따로 확인해요.
    assert.equal(validation.validPasswordConfirmation("Abcd1234", "Abcd1234"), true); assert.equal(validation.validPasswordConfirmation("Abcd1234", "Abcd1234 "), false); assert.equal(validation.validPasswordConfirmation("", ""), false); // 비밀번호에서 공백을 임의로 제거하면 안 돼요.
}); // 비밀번호 확인 검사를 마쳐요.
test("부모님 목적지는 인증 화면을 오가도 보존된다", () => { // 가입과 로그인을 바꾸면서 선택한 대상을 잃지 않게 해요.
    const parent = "/my?subject=parent"; const login = validation.authEntryHref("login", parent); const signup = validation.authEntryHref("signup", parent); // 같은 목적지로 두 인증 링크를 만들어요.
    assert.equal(validation.authDestinationFromSearch(login.slice(login.indexOf("?"))), parent); assert.equal(validation.authDestinationFromSearch(signup.slice(signup.indexOf("?"))), parent); // 쿼리를 다시 해석해도 부모님 화면이어야 해요.
    assert.equal(validation.authDestinationFromSearch("?next=%2Fmy"), "/my"); assert.equal(validation.authDestinationFromSearch(""), "/my"); // 일반 가입과 직접 로그인은 내 추천으로 이동해요.
}); // 부모님 인증 흐름 검사를 마쳐요.
for (const next of ["https://outside.example/my", "//outside.example/my", "javascript:alert(1)", "/\\outside.example", "/my?subject=parent&next=https://outside.example", "/my#parent", "%2Fmy%3Fsubject%3Dparent", "/settings", null]) { // 외부 이동과 허용되지 않은 내부 목적지를 검사해요.
    test(`인증 목적지 차단: ${JSON.stringify(next)}`, () => { assert.equal(validation.safeNextDestination(next), "/my"); assert.equal(validation.authDestinationFromSearch(`?next=${encodeURIComponent(next || "")}`), "/my"); }); // 허용 목록 밖의 값은 모두 안전한 기본 화면으로 돌려요.
} // 인증 후 임의 이동 방어 검사를 마쳐요.
