#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
if [[ ! -x "$ADB" ]]; then
  echo "adb not found at $ADB — set ADB=... or install Android platform-tools" >&2
  exit 1
fi
# Prefer LAN so the phone can reach the API over Wi-Fi without relying on adb reverse.
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
API_URL="${EXPO_PUBLIC_API_URL:-}"
if [[ -z "$API_URL" ]]; then
  if [[ -n "$LAN_IP" ]]; then
    API_URL="http://${LAN_IP}:4020/v1"
  else
    API_URL="http://127.0.0.1:4020/v1"
  fi
fi
"$ADB" reverse tcp:8081 tcp:8081 || true
"$ADB" reverse tcp:4020 tcp:4020 || true
"$ADB" reverse --list || true
echo "EXPO_PUBLIC_API_URL=$API_URL"
cd "$ROOT/frontend"
exec env EXPO_PUBLIC_API_URL="$API_URL" npx expo start --dev-client "$@"
