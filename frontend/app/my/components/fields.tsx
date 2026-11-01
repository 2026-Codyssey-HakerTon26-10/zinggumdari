import type { Fields } from "../../lib/service-api"; // 서버가 받는 원값 모양을 공유해요.
export type Field = { key: string; label: string; type?: "number" | "date" | "month" | "email"; options?: string[]; min?: number | string; max?: number | string; step?: number | "any" }; // 시트 칸을 폼 요소에 매핑해요.
export function FieldsForm({ fields, values }: { fields: Field[]; values: Record<string, unknown> }) { // 저장된 원값으로 입력을 초기화해요.
    return <>{fields.map((field) => <label key={field.key}>{field.label}{field.options ? <select name={field.key} defaultValue={String(values[field.key] ?? "")}><option value="">모름·미입력</option>{field.options.map((value) => <option key={value} value={value}>{value === "Y" ? "예" : value === "N" ? "아니오" : value}</option>)}</select> : <input name={field.key} type={field.type || "text"} defaultValue={typeof values[field.key] === "string" || typeof values[field.key] === "number" ? String(values[field.key]) : ""} min={field.min} max={field.max} step={field.type === "number" ? field.step ?? "any" : undefined} maxLength={field.type ? undefined : 100} />}</label>)}</>; // 빈 숫자는 0으로 바꾸지 않아요.
} // 필드 표시를 마쳐요.
export function readFields(form: FormData, fields: Field[]): Fields { // 화면에 선언한 칸만 서버로 보내요.
    return Object.fromEntries(fields.map((field) => { const raw = String(form.get(field.key) ?? "").trim(); if (field.type === "number" && raw && !Number.isFinite(Number(raw))) throw new Error("숫자 입력을 확인해 주세요."); return [field.key, raw === "" ? null : field.type === "number" ? Number(raw) : raw]; })); // 결측과 실제 숫자 0을 구분해요.
} // 폼 값 변환을 마쳐요.
