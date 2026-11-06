import type { Problem } from "../../contracts/spec-types";
import { ContractError } from "./contract-validation";
export class NetworkError extends Error {
  constructor() {
    super("Network unavailable");
  }
}
/** Client-side request timeout (distinct from offline / 503). */
export class TimeoutError extends Error {
  constructor() {
    super("Request timed out");
  }
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public retryAfter = 0,
    public problem?: Problem,
  ) {
    super(code);
  }
}
export type ErrorDescription = {
  kind: string;
  titleKey: string;
  bodyKey?: string;
  /** Literal server copy when the Problem already has a clear title/detail. */
  message?: string;
  action: "retry" | "wait" | "none" | "back" | "refresh" | "request";
  retryAfterSec?: number;
};

/** Parse Retry-After as delta-seconds or HTTP-date. */
export function parseRetryAfter(value: string | null | undefined): number {
  if (!value) return 0;
  const trimmed = value.trim();
  if (!trimmed) return 0;
  const seconds = Number(trimmed);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.floor(seconds);
  const date = Date.parse(trimmed);
  if (!Number.isNaN(date))
    return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  return 0;
}

function isTimeout(error: unknown, code: unknown, status: unknown): boolean {
  if (error instanceof TimeoutError) return true;
  if (code === "timeout") return true;
  if (status === 408 || status === 504) return true;
  if (
    error &&
    typeof error === "object" &&
    "name" in error &&
    (error as { name?: string }).name === "TimeoutError"
  )
    return true;
  return false;
}

export function describeError(error: unknown, online = true): ErrorDescription {
  const e = (error ?? {}) as Partial<Problem> & {
    problem?: Problem;
    retryAfter?: number;
    status?: number;
    absence?: { reason: string };
    name?: string;
  };
  const code = e.problem?.code ?? e.code;
  const reason = e.problem?.absence?.reason ?? e.absence?.reason;
  const status = e.status ?? (error instanceof ApiError ? error.status : undefined);
  if (!online || error instanceof NetworkError)
    return { kind: "offline", titleKey: "errorOffline", action: "retry" };
  // Client-only remap of unauthorized OTP failures (not a Problem.code).
  if (error instanceof ApiError && error.code === "otp_invalid")
    return { kind: "otp_invalid", titleKey: "errorOtpInvalid", action: "none" };
  if (code === "unauthorized")
    return { kind: "unauthorized", titleKey: "", action: "none" };
  if (code === "busy")
    return { kind: "busy", titleKey: "errorBusy", action: "wait" };
  if (reason === "generation_paused")
    return { kind: "paused", titleKey: "generationPaused", action: "none" };
  if (reason === "not_generated")
    return {
      kind: "not_generated",
      titleKey: "notGenerated",
      action: "request",
    };
  if (code === "rate_limited" || status === 429) {
    const problem = e.problem ?? (e as Problem);
    const message =
      (typeof problem.detail === "string" && problem.detail.trim()) ||
      (typeof problem.title === "string" &&
      problem.title !== "Unable to complete request"
        ? problem.title.trim()
        : "");
    return {
      kind: "rate_limited",
      titleKey: "errorRateLimited",
      message: message || undefined,
      action: "retry",
      retryAfterSec: e.retryAfter ?? 0,
    };
  }
  if (isTimeout(error, code, status))
    return { kind: "timeout", titleKey: "errorTimeout", action: "retry" };
  if (
    status === 503 ||
    code === "upstream_unavailable" ||
    // Not yet in Problem.code union; still remap any 503-style alias.
    String(code ?? "") === "service_unavailable"
  )
    return {
      kind: "unavailable",
      titleKey: "errorUnavailable",
      action: "retry",
    };
  if (code === "generation_failed")
    return {
      kind: "generation_failed",
      titleKey: "errorGeneration",
      action: "retry",
    };
  if (code === "not_found")
    return { kind: "not_found", titleKey: "errorNotFound", action: "back" };
  if (code === "out_of_range")
    return { kind: "out_of_range", titleKey: "errorRange", action: "none" };
  if (code === "validation_error")
    return { kind: "invalid", titleKey: "errorInvalid", action: "none" };
  if (code === "conflict")
    return { kind: "conflict", titleKey: "errorConflict", action: "refresh" };
  if (code === "premium_required" || isPremiumRequired(error))
    return {
      kind: "premium_required",
      titleKey: "errorPremiumRequired",
      action: "retry",
    };
  if (error instanceof ContractError)
    return { kind: "server", titleKey: "errorServer", action: "retry" };
  return { kind: "server", titleKey: "errorServer", action: "retry" };
}

/** True when the API refused a premium-gated feature. */
export function isPremiumRequired(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const e = error as Partial<ApiError> & { problem?: Problem; code?: string };
  return (
    e.code === "premium_required" ||
    e.problem?.code === "premium_required" ||
    (error instanceof ApiError && error.code === "premium_required")
  );
}
