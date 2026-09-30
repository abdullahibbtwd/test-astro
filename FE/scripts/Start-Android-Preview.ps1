$ErrorActionPreference = 'Stop'
$frontend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project = (Resolve-Path (Join-Path $frontend '..')).Path
$tools = Join-Path $project '.tooling'
$env:JAVA_HOME = (Get-ChildItem $tools -Directory -Filter 'jdk-*' | Select-Object -First 1).FullName
$env:ANDROID_HOME = Join-Path $tools 'android'
$env:ANDROID_AVD_HOME = Join-Path $tools 'avd'
$env:NODE_OPTIONS = '--dns-result-order=ipv4first'
$env:EXPO_PUBLIC_API_URL = 'http://127.0.0.1:4010/v1'
Remove-Item Env:CI -ErrorAction SilentlyContinue
$adb = Join-Path $env:ANDROID_HOME 'platform-tools/adb.exe'
$node = (Get-Command node.exe).Source
function Is-Listening([int]$port) { return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
function Is-MetroReady { try { return (Invoke-WebRequest -Uri 'http://127.0.0.1:8081/status' -TimeoutSec 2).StatusCode -eq 200 } catch { return $false } }

if (!(Is-Listening 4010)) {
 Start-Process -FilePath $node -ArgumentList 'node_modules/tsx/dist/cli.mjs','mock-api/server.ts' -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput "$tools/mock.log" -RedirectStandardError "$tools/mock-error.log"
}
if (!(Is-Listening 8081)) {
 Start-Process -FilePath $node -ArgumentList 'node_modules/expo/bin/cli','start','--dev-client','--localhost','--port','8081' -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput "$tools/metro.log" -RedirectStandardError "$tools/metro-error.log"
}
$devices = & $adb devices
if (!($devices -match 'emulator-\d+\s+device')) {
 Start-Process -FilePath "$env:ANDROID_HOME/emulator/emulator.exe" -ArgumentList '-avd','Astrology_Preview','-no-snapshot','-no-audio','-gpu','swiftshader','-feature','-Vulkan','-memory','4096','-cores','4' -WindowStyle Normal -RedirectStandardOutput "$tools/emulator.log" -RedirectStandardError "$tools/emulator-error.log"
}
Write-Host 'Opening Android preview. First boot can take a minute...'
& $adb wait-for-device
$deadline = (Get-Date).AddMinutes(3)
while ((& $adb shell getprop sys.boot_completed).Trim() -ne '1') {
 if ((Get-Date) -gt $deadline) { throw 'Android did not finish booting. See .tooling/emulator-error.log.' }
 Start-Sleep -Seconds 2
}
& $adb reverse tcp:8081 tcp:8081
& $adb reverse tcp:4010 tcp:4010
$apk = Join-Path $frontend 'android/app/build/outputs/apk/debug/app-debug.apk'
if (!(Test-Path -LiteralPath $apk)) { throw 'Run scripts/Build-Android-Preview.ps1 first.' }
& $adb install -r $apk
$deadline = (Get-Date).AddSeconds(60)
while (!(Is-MetroReady)) { if ((Get-Date) -gt $deadline) { throw 'Metro did not start. See .tooling/metro-error.log.' }; Start-Sleep -Seconds 1 }
& $adb shell am start -a android.intent.action.VIEW -d 'astrology-dev://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A8081' com.example.astrology.dev
Write-Host 'Preview ready. Sign in with demo@example.com and code 000000.'
