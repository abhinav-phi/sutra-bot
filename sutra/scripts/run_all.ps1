# ============================================================
# ONE-COMMAND full run for Windows PowerShell (no bash needed):
#   fresh server -> load dataset -> judge simulator -> cleanup
# Usage:  powershell -ExecutionPolicy Bypass -File sutra/scripts/run_all.ps1
# ============================================================
$ErrorActionPreference = "Continue"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$SUTRA_DIR  = Join-Path $SCRIPT_DIR ".."
$ROOT       = Join-Path $SCRIPT_DIR "..\.."
$PORT       = if ($env:PORT) { $env:PORT } else { "8081" }
$BOT_URL    = "http://127.0.0.1:$PORT"

Write-Host "== [1/5] Freeing port $PORT =="
try {
    $conns = Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Write-Host "   killing PID $($c.OwningProcess)"
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
} catch { }
Start-Sleep -Seconds 1

Write-Host "== [2/5] Starting Sutra on $BOT_URL =="
$server = Start-Process -FilePath "python" -ArgumentList @("-m", "uvicorn", "bot:app", "--host", "127.0.0.1", "--port", $PORT, "--log-level", "warning") -WorkingDirectory $SUTRA_DIR -PassThru -WindowStyle Hidden

$up = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-WebRequest -Uri "$BOT_URL/v1/healthz" -UseBasicParsing -TimeoutSec 3 | Out-Null; $up = $true; break } catch { }
}
if (-not $up) {
    Write-Host "   server failed to start"; Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue; exit 1
}
Write-Host "   server up"

Write-Host "== [3/5] Fresh state (judge pushes its own contexts) =="
try { Invoke-RestMethod -Method Post -Uri "$BOT_URL/v1/teardown" -ContentType "application/json" -Body "{}" | Out-Null } catch { }
# NOTE: no pre-load here — judge_simulator pushes the base contexts itself
# during its warmup. Pre-loading caused 409 stale_version conflicts (contexts
# already at version 1), which the judge marks as [FAIL].

Write-Host "== [4/5] Running judge simulator =="
# load .env values safely
$envFile = Join-Path $SUTRA_DIR ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $k = $line.Substring(0, $idx).Trim()
            $v = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
            if ($k) { Set-Item -Path "env:$k" -Value $v }
        }
    }
}
if (-not $env:LLM_API_KEY)  { $env:LLM_API_KEY  = $env:OPENROUTER_API_KEY }
if (-not $env:LLM_API_KEY)  { $env:LLM_API_KEY  = $env:CUSTOM_LLM_API_KEY }
if (-not $env:LLM_PROVIDER) { $env:LLM_PROVIDER = "openrouter" }
if (-not $env:LLM_MODEL)    { $env:LLM_MODEL    = $env:LLM_OPENROUTER_MODEL }
$env:BOT_URL = $BOT_URL
$scenario = if ($env:TEST_SCENARIO) { $env:TEST_SCENARIO } else { "all" }
python (Join-Path $ROOT "challenge-pack/judge_simulator.py") $scenario

Write-Host "== [5/5] Cleaning up (PID $($server.Id)) =="
Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
Write-Host "Done."
