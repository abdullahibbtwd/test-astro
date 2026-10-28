import type { Problem } from "../../contracts/spec-types";
import { ContractError } from "./contract-validation";
export class NetworkError extends Error {
  constructor() {
    super("Network unavailable");
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
export function describeError(error: unknown, online = true): ErrorDescription {
  const e = (error ?? {}) as Partial<Problem> & {
    problem?: Problem;
    retryAfter?: number;
    absence?: { reason: string };
  };
  const code = e.problem?.code ?? e.code;
  const reason = e.problem?.absence?.reason ?? e.absence?.reason;
  if (!online || error instanceof NetworkError)
    return { kind: "offline", titleKey: "errorOffline", action: "retry" };
  if (code === "otp_invalid")
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
  if (code === "rate_limited" || e.status === 429) {
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
  if (error instanceof ContractError)
    return { kind: "server", titleKey: "errorServer", action: "retry" };
  return { kind: "server", titleKey: "errorServer", action: "retry" };
}
