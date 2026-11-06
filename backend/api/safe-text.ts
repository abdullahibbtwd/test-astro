/**
 * Sanitize user-authored text that may enter LLM prompts (labels, notes).
 * Does not log values.
 */
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;
const INJECTIONISH =
  /(ignore|disregard)\s+(all\s+)?(previous|prior|above|system)|system\s+prompt|you\s+are\s+now\b/i;

export function sanitizeLabel(raw: string, max = 40): string | null {
  const text = String(raw ?? "")
    .replace(CONTROL, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || text.length > max) return null;
  if (INJECTIONISH.test(text)) return null;
  return text;
}

export function scrubErrorPayload(body: unknown): boolean {
  if (body == null || typeof body !== "object") return true;
  const text = JSON.stringify(body);
  if (/at\s+\S+\s+\([^)]+:\d+:\d+\)/.test(text)) return false; // stack frame
  if (/\bSELECT\b.+\bFROM\b/i.test(text)) return false;
  if (/\bBearer\s+[A-Za-z0-9._\-]+/.test(text)) return false;
  if (/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/.test(text)) return false; // JWT
  return true;
}
