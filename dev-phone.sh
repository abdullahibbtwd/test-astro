#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
if [[ ! -x "$ADB" ]]; then
  echo "adb not found at $ADB — set ADB=... or install Android platform-tools" >&2
  exit 1
fi
"$ADB" reverse tcp:8081 tcp:8081
"$ADB" reverse tcp:4020 tcp:4020
"$ADB" reverse --list
cd "$ROOT/frontend"
exec env EXPO_PUBLIC_API_URL=http://127.0.0.1:4020/v1 npx expo start --dev-client "$@"
