# ACG full test run: 1979-03-30 06:30 Sofia
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File .\test_acg_1979.ps1
# Add -DryRun to build everything except the model calls (no cost).
# Add -IstanbulOnly to run just the map + the Istanbul city screen.
# Every run gets an English summary: acg_run\<run_id>\english.md
param([switch]$DryRun, [switch]$IstanbulOnly)

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$py = ".\.venv\Scripts\python.exe"
$B  = @("--date", "1979-03-30", "--time", "06:30", "--location", "Sofia, Bulgaria")
$D  = @(); if ($DryRun) { $D = @("--dry-run") }

function Run($label, $extra) {
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    & $py run_acg.py @B @extra @D
    $en = & $py acg_english.py          # English summary of the run just made
    Write-Host "English: $en" -ForegroundColor Yellow
}

# 1. Map (lines + city scan + goal scan + heat layers). Computed once, then cached.
Run "map" @()

# 2. City screens
Run "city: Istanbul"                  @("--city", "Istanbul")
if ($IstanbulOnly) { exit 0 }
Run "city: Sofia"                     @("--city", "Sofia")
Run "city: Izmir (focus love)"        @("--city", "Izmir", "--focus-goal", "love")
Run "city: Berlin (focus career)"     @("--city", "Berlin", "--focus-goal", "career")
Run "city: London"                    @("--city", "London")
Run "manual point: Bodrum"            @("--lat", "37.0344", "--lon", "27.4305")

# 3. Country screens
Run "country: BG" @("--country", "BG")
Run "country: TR" @("--country", "TR")
Run "country: DE" @("--country", "DE")

# 4. Where Should I Go? (all 11 goals, world scope; the Turkey block is included automatically)
$goals = "love","career","business","money","family","education","creativity","spirituality","rest","travel","relocation"
foreach ($g in $goals) { Run "recommend: $g / world" @("--recommend", $g, "--scope", "world") }

# 5. Scoped recommendations + the free-text path
Run "recommend: career / TR"    @("--recommend", "career", "--scope", "TR")
Run "recommend: love / BG"      @("--recommend", "love", "--scope", "BG")
Run "free text (TR)"            @("--query-text", "Aşk için en iyi yer neresi?")
Run "free text (off-topic)"     @("--query-text", "What is the weather tomorrow?")

Write-Host "`nDone. Outputs: .\acg_run\<run_id>\ (one folder per command)" -ForegroundColor Green
