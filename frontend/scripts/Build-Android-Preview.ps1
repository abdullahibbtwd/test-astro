$ErrorActionPreference='Stop'
$frontend=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project=(Resolve-Path (Join-Path $frontend '..')).Path
$env:JAVA_HOME=(Get-ChildItem "$project/.tooling" -Directory -Filter 'jdk-*' | Select-Object -First 1).FullName
$env:ANDROID_HOME="$project/.tooling/android"
Set-Location $frontend
& npx.cmd expo prebuild --platform android --no-install
if ($LASTEXITCODE -ne 0) { throw 'Expo prebuild failed.' }
$sdkProperty=$env:ANDROID_HOME.Replace('\','/').Replace(':','\:')
Set-Content -LiteralPath android/local.properties -Value "sdk.dir=$sdkProperty"
& ./android/gradlew.bat -p android assembleDebug -PreactNativeArchitectures=x86_64 --max-workers=4 --console=plain
if ($LASTEXITCODE -ne 0) { throw 'Android build failed.' }
