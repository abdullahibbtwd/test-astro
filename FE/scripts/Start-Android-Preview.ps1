param([switch]$RealCharts, [switch]$EnableReadings, [switch]$RestartApi, [switch]$EnableAstrologist)
$ErrorActionPreference = 'Stop'
if ($EnableReadings -and !$RealCharts) { throw 'EnableReadings requires RealCharts' }
$frontend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project = (Resolve-Path (Join-Path $frontend '..')).Path
$env:ASTRO_PA_ROOT = $project
$env:ASTRO_ASK_ENABLED = if ($EnableAstrologist) { '1' } else { '0' }
if ($EnableAstrologist) {
 if (!$RealCharts -or !$EnableReadings) { throw 'EnableAstrologist requires RealCharts and EnableReadings.' }
 $missingAgentFiles = @('ask_bridge.py', 'astrologist/pa_engine.py') | Where-Object { !(Test-Path -LiteralPath (Join-Path $project $_)) }
 if ($missingAgentFiles) { throw "Astro agent is incomplete in ${project}: missing $($missingAgentFiles -join ', '). Copy the completed backend before enabling chat." }
 if ((Get-NetTCPConnection -LocalPort 4020 -State Listen -ErrorAction SilentlyContinue) -and !$RestartApi) { throw 'Use RestartApi when enabling the Astro agent so the running API receives its configuration.' }
}
$tools = Join-Path $project '.tooling'
$env:JAVA_HOME = (Get-ChildItem $tools -Directory -Filter 'jdk-*' | Select-Object -First 1).FullName
$env:ANDROID_HOME = Join-Path $tools 'android'
$env:ANDROID_AVD_HOME = Join-Path $tools 'avd'
$env:NODE_OPTIONS = '--dns-result-order=ipv4first'
$apiPort = if ($RealCharts) { 4020 } else { 4010 }
$metroPort = if ($RealCharts) { 8082 } else { 8081 }
$apiEntry = if ($RealCharts) { 'local-api/server.ts' } else { 'mock-api/server.ts' }
$env:EXPO_PUBLIC_API_URL = "http://127.0.0.1:$apiPort/v1"
$env:EXPO_PUBLIC_BACKEND_MODE = if ($RealCharts) { 'local' } else { 'demo' }
$authFile = Join-Path $frontend '.local-data/auth-config.json'
$realAuth = $RealCharts -and (Test-Path -LiteralPath $authFile) -and ((Get-Content -Raw -LiteralPath $authFile | ConvertFrom-Json).enabled -eq $true)
$env:EXPO_PUBLIC_AUTH_MODE = if ($realAuth) { 'supabase' } else { 'demo' }
$env:ASTRO_ALLOW_PAID = if ($EnableReadings) { '1' } else { '0' } # Shared durable US$20 cap remains enforced.
$env:ASTRO_GUEST_ONBOARDING = if ($RealCharts) { '1' } else { '0' }
Remove-Item Env:CI -ErrorAction SilentlyContinue
$adb = Join-Path $env:ANDROID_HOME 'platform-tools/adb.exe'
$node = (Get-Command node.exe).Source
$expoCli = Join-Path $frontend 'node_modules/expo/bin/cli'
# Expo's typed-route file is shared by both previews. Keep one generator per checkout.
$otherMetroPort = if ($RealCharts) { 8081 } else { 8082 }
$otherListener = Get-NetTCPConnection -LocalPort $otherMetroPort -State Listen -ErrorAction SilentlyContinue
if ($otherListener) {
 $otherProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($otherListener.OwningProcess)"
 if ($otherProcess.CommandLine -and $otherProcess.CommandLine.Contains($expoCli) -and $otherProcess.CommandLine -like "*--port $otherMetroPort*") {
  Stop-Process -Id $otherProcess.ProcessId
 }
}
function Is-Listening([int]$port) { return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
function Is-MetroReady { try { return (Invoke-WebRequest -Uri "http://127.0.0.1:$metroPort/status" -TimeoutSec 2).StatusCode -eq 200 } catch { return $false } }

$existingApi = Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction SilentlyContinue
if ($existingApi -and $RestartApi) {
 $apiProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($existingApi.OwningProcess)"
 if (!$apiProcess.CommandLine.Contains($frontend) -or !$apiProcess.CommandLine.Contains($apiEntry)) {
  throw 'The API port belongs to an unexpected process; not stopping it.'
 }
 Stop-Process -Id $apiProcess.ProcessId
} elseif ($existingApi -and $EnableReadings) {
 throw 'Use -RestartApi to apply EnableReadings to the running API. Wait for active readings to finish first.'
}
if (!(Is-Listening $apiPort)) {
 Start-Process -FilePath $node -ArgumentList 'node_modules/tsx/dist/cli.mjs',$apiEntry -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput "$tools/api-$apiPort.log" -RedirectStandardError "$tools/api-$apiPort-error.log"
}
if (!(Is-Listening $metroPort)) {
 Start-Process -FilePath $node -ArgumentList ('"' + $expoCli + '"'),'start','--dev-client','--localhost','--port',"$metroPort" -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput "$tools/metro-$metroPort.log" -RedirectStandardError "$tools/metro-$metroPort-error.log"
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
& $adb reverse "tcp:$metroPort" "tcp:$metroPort"
& $adb reverse "tcp:$apiPort" "tcp:$apiPort"
$apk = Join-Path $frontend 'android/app/build/outputs/apk/debug/app-debug.apk'
if (!(Test-Path -LiteralPath $apk)) { throw 'Run scripts/Build-Android-Preview.ps1 first.' }
& $adb install -r $apk
$deadline = (Get-Date).AddSeconds(60)
while (!(Is-MetroReady)) { if ((Get-Date) -gt $deadline) { throw 'Metro did not start. See .tooling/metro-error.log.' }; Start-Sleep -Seconds 1 }
& $adb shell am start -a android.intent.action.VIEW -d "astrology-dev://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A$metroPort" com.example.astrology.dev
if ($realAuth) { Write-Host 'Preview ready. Sign in with your configured owner email.' } else { Write-Host 'Preview ready. Sign in with demo@example.com and code 000000.' }

Write-Host 'To change live reading generation, use -RestartApi; add -EnableReadings to enable it. Never restart during an active reading.'
