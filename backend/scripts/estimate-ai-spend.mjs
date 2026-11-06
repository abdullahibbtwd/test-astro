#!/usr/bin/env node
/**
 * Estimate daily / monthly AI spend from simple inputs.
 * Usage:
 *   node backend/scripts/estimate-ai-spend.mjs \
 *     --cost-per-reading=0.04 \
 *     --readings-per-user-day=2 \
 *     --users=50
 *
 * No network, no secrets, no personal data.
 */
function num(flag, fallback) {
  const arg = process.argv.find((a) => a.startsWith(`--${flag}=`));
  if (!arg) return fallback;
  const v = Number(arg.slice(flag.length + 3));
  if (!Number.isFinite(v) || v < 0) {
    console.error(`Invalid --${flag}`);
    process.exit(1);
  }
  return v;
}

const cost = num("cost-per-reading", 0.05);
const perUser = num("readings-per-user-day", 2);
const users = num("users", 10);
const days = num("days", 30);

const daily = cost * perUser * users;
const monthly = daily * days;

console.log(
  JSON.stringify(
    {
      assumptions: {
        cost_per_reading_usd: cost,
        readings_per_user_per_day: perUser,
        users,
        days_in_month: days,
      },
      expected_daily_usd: Number(daily.toFixed(4)),
      expected_monthly_usd: Number(monthly.toFixed(2)),
      note: "Compare against ASTRO_BUDGET_LIMIT (code ceiling US$20 unless changed).",
    },
    null,
    2,
  ),
);
