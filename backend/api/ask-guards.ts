/** Input safeguards for Ask Astrology (no secrets, no PII logged). */

export const ASK_MESSAGE_MAX_CHARS = 1000;

/** Patterns that try to break the astrology-only system role. */
const ABUSE_PATTERNS: RegExp[] = [
  /ignore\s+(all\s+)?(previous|prior|above)\s+instructions/i,
  /disregard\s+(the\s+)?(system|developer)\s+(prompt|message)/i,
  /you\s+are\s+now\s+(a|an)\s+(general|unrestricted|jailbreak)/i,
  /act\s+as\s+(dan|developer\s+mode|unfiltered)/i,
  /reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions)/i,
  /do\s+not\s+follow\s+astrology/i,
  /new\s+instructions?\s*:/i,
  /<\/?\s*system\s*>/i,
  /\[\[\s*system\s*\]\]/i,
];

export type AskGuardResult =
  | { ok: true; text: string }
  | { ok: false; code: "validation_error" | "abuse_rejected" };

export function guardAskMessage(raw: string): AskGuardResult {
  const text = String(raw ?? "").trim();
  if (!text || text.length > ASK_MESSAGE_MAX_CHARS)
    return { ok: false, code: "validation_error" };
  if (ABUSE_PATTERNS.some((re) => re.test(text)))
    return { ok: false, code: "abuse_rejected" };
  return { ok: true, text };
}
