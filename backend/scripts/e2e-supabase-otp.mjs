/**
 * Interactive E2E helper: request an email OTP, wait for the code on stdin,
 * verify with Supabase, then call GET /v1/me with the access token.
 * Never prints keys or tokens — only email, user id, and HTTP status.
 *
 * Usage (from repo root, with .env loaded):
 *   set -a && source .env && set +a
 *   node backend/scripts/e2e-supabase-otp.mjs you@example.com
 */
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

function env(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    console.error(`Missing ${name}`);
    process.exit(1);
  }
  return value;
}

const email = (process.argv[2] || "").trim().toLowerCase();
if (!email.includes("@")) {
  console.error("Usage: node backend/scripts/e2e-supabase-otp.mjs you@example.com");
  process.exit(1);
}

const url = env("SUPABASE_URL").replace(/\/$/, "");
const publishable = env("SUPABASE_PUBLISHABLE_KEY");
const api = (process.env.EXPO_PUBLIC_API_URL || "http://127.0.0.1:4020/v1").replace(
  /\/$/,
  "",
);
const authBase = url + "/auth/v1";

async function authPost(path, body) {
  const response = await fetch(authBase + path, {
    method: "POST",
    headers: {
      apikey: publishable,
      Authorization: "Bearer " + publishable,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  return { ok: response.ok, status: response.status, json };
}

console.log(`Requesting email code for ${email}…`);
const started = await authPost("/otp", { email, create_user: true });
if (!started.ok && started.status !== 204) {
  console.error("OTP request failed with status", started.status);
  process.exit(1);
}
console.log("Code sent. Enter the 6-digit code:");

const rl = createInterface({ input, output });
const code = (await rl.question("> ")).replace(/\D/g, "").slice(0, 6);
rl.close();
if (code.length !== 6) {
  console.error("Expected 6 digits");
  process.exit(1);
}

const verified = await authPost("/verify", {
  email,
  token: code,
  type: "email",
});
if (!verified.ok || !verified.json?.access_token || !verified.json?.user?.id) {
  console.error("Verify failed with status", verified.status);
  process.exit(1);
}

const userId = verified.json.user.id;
const userEmail = verified.json.user.email;
console.log(`Supabase user id: ${userId}`);
console.log(`Supabase email: ${userEmail}`);

const me = await fetch(`${api}/me`, {
  headers: { Authorization: `Bearer ${verified.json.access_token}` },
});
const body = await me.text();
console.log(`Backend GET /me status: ${me.status}`);
if (!me.ok) {
  console.error("Backend rejected the token. Is the API running with JWKS auth?");
  process.exit(1);
}
let parsed;
try {
  parsed = JSON.parse(body);
} catch {
  console.error("Backend returned non-JSON");
  process.exit(1);
}
console.log(`Backend user_id: ${parsed.user_id}`);
console.log(`Backend email: ${parsed.email}`);
if (parsed.user_id !== userId) {
  console.error("Mismatch: backend user_id does not equal Supabase sub");
  process.exit(1);
}
console.log("OK — backend sees the same user id as Supabase.");
