// 시연 영상 자동 촬영: 헤드리스 크롬을 CDP로 조작하고 screencast 프레임을 모은다. 패키지 설치 없이 Node 내장 WebSocket만 쓴다.
// 사용: node scripts/demo/record.mjs <출력폴더> <자막 0|1>  (먼저 record_api.py와 next start -p 3031을 띄운다. README는 docs/demo-video.md)
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";

const OUT = process.argv[2];
const CAPTIONS = process.argv[3] === "1";
const BASE = "http://localhost:3031";
const API = "http://127.0.0.1:8031";
const PDF = new URL("../../data/notices/lh-0000061189.pdf", import.meta.url).pathname; // 캐시가 있는 시연 공고(안산신길2 신혼희망타운)
const SCENES = JSON.parse(readFileSync(new URL("./scenes.json", import.meta.url)));
const W = 393, H = 852, DPR = 2;

rmSync(OUT, { recursive: true, force: true });
mkdirSync(join(OUT, "frames"), { recursive: true });
await fetch(`${API}/_reset`, { method: "POST" });

const profileDir = join(OUT, "chrome");
const chrome = spawn(process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
    "--headless=new", "--remote-debugging-port=9333", `--user-data-dir=${profileDir}`, `--window-size=${W},${H}`,
    "--hide-scrollbars", "--mute-audio", "--no-first-run", "--no-default-browser-check", "--force-device-scale-factor=2", "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch("http://127.0.0.1:9333/json/list")).json(); if (targets.some((t) => t.type === "page")) break; } catch { /* 아직 안 떴다 */ } await sleep(200); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let seq = 0; const waiting = new Map(); const handlers = {};
ws.addEventListener("message", (ev) => { const msg = JSON.parse(ev.data); if (msg.id && waiting.has(msg.id)) { const { res, rej } = waiting.get(msg.id); waiting.delete(msg.id); msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result); } else if (msg.method && handlers[msg.method]) handlers[msg.method](msg.params); });
const send = (method, params = {}) => new Promise((res, rej) => { const id = ++seq; waiting.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + " " + expr.slice(0, 120)); return r.result.value; };

await send("Page.enable"); await send("Runtime.enable"); await send("DOM.enable");
await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: DPR, mobile: true });
await send("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1" });

// 화면 위 보조 레이어: 탭 표시, 자막, 제목 카드. 페이지를 옮겨도 다시 그린다.
await send("Page.addScriptToEvaluateOnNewDocument", { source: `
(() => {
  const CAPTIONS = ${CAPTIONS};
  const css = '#__cap{position:fixed;left:12px;right:12px;bottom:92px;z-index:100000;text-align:center;color:#fff;font-family:-apple-system,"Apple SD Gothic Neo",sans-serif;font-size:18px;font-weight:800;line-height:1.45;letter-spacing:-.03em;word-break:keep-all;-webkit-text-stroke:5px #000;paint-order:stroke fill;text-shadow:0 2px 6px rgba(0,0,0,.45);pointer-events:none}#__card{position:fixed;inset:0;z-index:99995;display:flex;flex-direction:column;justify-content:center;padding:36px;background:linear-gradient(160deg,#0b3b6e,#00809a 60%,#d9692e);color:#fff;font-family:-apple-system,"Apple SD Gothic Neo",sans-serif;transition:opacity .6s;pointer-events:none}#__card h1{margin:0;font-size:30px;line-height:1.35;letter-spacing:-.05em}#__card p{margin:16px 0 0;font-size:15px;line-height:1.7;color:#e2f3f6}#__card small{position:absolute;left:36px;bottom:48px;font-size:13px;opacity:.85}';
  const mount = () => { if (!document.getElementById('__style')) { const s = document.createElement('style'); s.id = '__style'; s.textContent = css; document.head.appendChild(s); } };
  window.__cap = (text) => { mount(); try { sessionStorage.setItem('__cap', JSON.stringify(text || '')); } catch {} if (!CAPTIONS) return; let el = document.getElementById('__cap'); if (!text) { el && el.remove(); return; } if (!el) { el = document.createElement('div'); el.id = '__cap'; document.body.appendChild(el); } el.textContent = text; };
  window.__card = (h, p, small) => { mount(); let el = document.getElementById('__card'); if (!h) { if (el) { el.style.opacity = 0; setTimeout(() => el.remove(), 650); } return; } if (!el) { el = document.createElement('div'); el.id = '__card'; document.body.appendChild(el); } el.innerHTML = '<h1></h1><p></p><small></small>'; el.querySelector('h1').innerHTML = h; el.querySelector('p').innerHTML = p || ''; el.querySelector('small').textContent = small || ''; };
  window.__tap = (x, y) => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;left:' + (x - 21) + 'px;top:' + (y - 21) + 'px;width:42px;height:42px;border-radius:50%;background:rgba(36,116,199,.28);border:2px solid rgba(36,116,199,.85);z-index:99999;pointer-events:none;transition:transform .5s,opacity .5s'; document.body.appendChild(d); requestAnimationFrame(() => { d.style.transform = 'scale(1.7)'; d.style.opacity = '0'; }); setTimeout(() => d.remove(), 600); };
  document.addEventListener('DOMContentLoaded', () => { try { const c = JSON.parse(sessionStorage.getItem('__cap') || 'null'); if (c) window.__cap(c); } catch {} });
})();` });

// 프레임 수집
const frames = [];
handlers["Page.screencastFrame"] = (p) => { const n = frames.length; writeFileSync(join(OUT, "frames", `f${String(n).padStart(5, "0")}.jpg`), Buffer.from(p.data, "base64")); frames.push(p.metadata.timestamp); send("Page.screencastFrameAck", { sessionId: p.sessionId }).catch(() => {}); };

const go = async (path) => { await send("Page.navigate", { url: BASE + path }); await sleep(400); for (let i = 0; i < 60; i++) { if (await js("document.readyState") === "complete") break; await sleep(100); } };
const until = async (expr, ms = 15000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await js(`!!(${expr})`)) return; await sleep(120); } throw new Error("시간 초과: " + expr); };
const findEl = (sel, text) => `[...document.querySelectorAll(${JSON.stringify(sel)})].find((e) => e.offsetParent !== null && ${text ? `e.textContent.includes(${JSON.stringify(text)})` : "true"})`;
const scrollTo = async (sel, text, block = "center") => { await js(`(${findEl(sel, text)})?.scrollIntoView({ behavior: "smooth", block: "${block}" })`); await sleep(700); };
const tap = async (sel, text, { scroll = true } = {}) => {
    await until(findEl(sel, text));
    if (scroll) { const visible = await js(`(() => { const r = (${findEl(sel, text)}).getBoundingClientRect(); return r.top > 70 && r.bottom < ${H - 90}; })()`); if (!visible) await scrollTo(sel, text); }
    const { x, y } = await js(`(() => { const r = (${findEl(sel, text)}).getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    await js(`window.__tap(${x}, ${y})`); await sleep(220);
    for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
    await sleep(250);
};
const type = async (selector, text) => { await js(`document.querySelector(${JSON.stringify(selector)}).focus()`); await send("Input.insertText", { text }); await sleep(120); };
const smooth = async (top) => { await js(`window.scrollTo({ top: ${top}, behavior: "smooth" })`); await sleep(800); };

let t0 = Date.now();
const at = async (sec) => { const wait = t0 + sec * 1000 - Date.now(); if (wait > 0) await sleep(wait); else console.log(`  (장면이 ${(-wait / 1000).toFixed(1)}초 늦음)`); };
const scene = async (n) => { const s = SCENES[n - 1]; await at(s.start); console.log(`장면 ${n} ${s.title}`); };
// 자막 = 나레이션 조각(cues.json). 시간표대로 바꾸고, 페이지를 옮겨도 다시 그린다.
const CUES = JSON.parse(readFileSync(new URL("./cues.json", import.meta.url)));
let shown = null, ticking = true;
const ticker = (async () => { while (ticking) { const t = (Date.now() - t0) / 1000; const cue = CUES.find((c) => c.start <= t && t < c.end); const text = cue ? cue.text : ""; try { if (text !== shown || Math.random() < 0.1) { await js(`window.__cap && window.__cap(${JSON.stringify(text)})`); shown = text; } } catch { /* 페이지 이동 중 */ } await sleep(100); } })();

await go("/");
await send("Page.startScreencast", { format: "jpeg", quality: 88, maxWidth: W * DPR, maxHeight: H * DPR, everyNthFrame: 1 });
t0 = Date.now();

// 1. 문제
await scene(1);
await js(`window.__card("결혼, 출산,<br>부모님의 노후.", "필요한 제도는<br>늘 지나고 나서 알게 됩니다.", "징검다리 · 생애주기 맞춤 제도 추천")`);
await sleep(5600); await js(`window.__card(null)`);

// 2. 가입(선택 정보) → 프리셋
await scene(2);
await go("/signup"); await until(`document.querySelector("#auth-nickname")`);
await type("#auth-nickname", "지원"); await type("#auth-email", "demo@zinggum.test");
await type("#auth-password", "zinggum2026"); await type("#auth-confirm-password", "zinggum2026");
await tap(".auth-optional summary"); await tap(".auth-optional-chips button", "결혼 준비 중");
await tap("label, button, input", "필수 항목 전체 동의");
await tap("button[type=submit]");
await until(`document.querySelector(".profile-setup")`);
await sleep(900); await scrollTo(".profile-seeded", null, "center"); await sleep(900);
await tap(".profile-presets button");

// 3. 브리핑
await scene(3);
await until(`document.querySelector(".briefing-item")`);
await smooth(0); await sleep(6500);
await scrollTo(".briefing-events", null, "end"); await sleep(3000); await smooth(0);

// 4. 결혼하면 미리 보기
await scene(4);
await tap(".briefing-action", "미리 보기"); await until(`document.querySelector(".briefing-eyebrow")?.textContent.includes("가정")`);
await sleep(5200);
await tap(".briefing-action", "카드 보기"); await sleep(1200);
await scrollTo(".recommendation-card", null, "start"); await sleep(2500);

// 5. 원문 근거
await scene(5);
await js(`document.querySelector(".recommendation-card-details").open = true`); await sleep(700);
await scrollTo(".recommendation-card-details", null, "center"); await sleep(800);
await tap(".recommendation-card-details button", "근거 보기");
await until(`document.querySelector(".work-pdf-mark")`, 20000); await sleep(8500);
await tap(".notice-sheet-close"); await sleep(400);

// 6. 부모님
await scene(6);
await smooth(0); await tap(".briefing-action", "지금으로");
await until(`[...document.querySelectorAll(".briefing-action")].some((e) => e.textContent.includes("부모님"))`);
await scrollTo(".briefing-item", "만 65세", "center"); await sleep(1800);
await tap(".briefing-action", "부모님"); await sleep(1500);
await scrollTo(".recommendation-card", null, "start"); await sleep(3200);

// 7. 결혼했어요
await scene(7);
await tap(".recommendation-subjects button", "나의 추천"); await sleep(700);
await scrollTo(".briefing-events", null, "center"); await sleep(900);
await tap(".briefing-chips button", "결혼했어요"); await sleep(2600);
await tap(".briefing-confirm button", "반영하기");
await until(`document.querySelector(".briefing h2")?.textContent.includes("새 생활")`);
await smooth(0); await sleep(3600);
await tap(".briefing-action", "카드 보기"); await sleep(900);

// 8. 공고 투입
await scene(8);
await scrollTo(".ingest-heading", null, "start"); await sleep(1200);
const { root } = await send("DOM.getDocument", { depth: -1, pierce: true });
const { nodeId } = await send("DOM.querySelector", { nodeId: root.nodeId, selector: "input[type=file]" });
await send("DOM.setFileInputFiles", { nodeId, files: [PDF] }); await sleep(700);
await tap(".ingest-replay"); await sleep(400);
await tap("button.ingest-submit");
await until(`document.querySelector(".ingest-result")`, 30000); await sleep(300);
await scrollTo(".ingest-result", null, "start"); await sleep(1800);
await tap(".ingest-result-details summary"); await sleep(300);
await scrollTo(".ingest-rule", null, "start"); await sleep(2600);
await smooth(0); await sleep(400);
await scrollTo(".recommendation-card", "안산신길2", "start"); await sleep(2600);

// 9. 알림함 → 리포트
await scene(9);
await tap(".mobile-tab-bar a, nav a", "알림", { scroll: false }).catch(async () => go("/notifications"));
await until(`document.querySelector(".notice-item")`); await sleep(4200);
await go("/api/backend/notify/report"); shown = null;
await sleep(1500); await smooth(520); await sleep(2000);

// 10. 마무리
await scene(10);
await js(`window.__card("나의 오늘도,<br>부모님의 내일도.", "묻기 전에 다음 생애 단계와 부모님 것까지<br>먼저 챙겨 주는 서비스", "징검다리")`);
await at(120);

ticking = false; await ticker; await send("Page.stopScreencast"); await sleep(300);
writeFileSync(join(OUT, "frames.json"), JSON.stringify({ t0: t0 / 1000, end: 120, frames }));
ws.close(); chrome.kill();
console.log(`프레임 ${frames.length}개, ${((Date.now() - t0) / 1000).toFixed(1)}초`);
