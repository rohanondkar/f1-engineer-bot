# Bypass execution policy for this process only, then run the app.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating virtualenv..."
    python -m venv .venv
    & $py -m pip install -U pip
    & $py -m pip install -e .
}

$env:PYTHONPATH = (Join-Path $PSScriptRoot "src") + ";" + ($env:PYTHONPATH ?? "")

try {
    & $py -c "import f1_engineer.__main__" 2>$null | Out-Null
} catch {
    Write-Host "Refreshing package install..."
    & $py -m pip install -e . -q
}

& $py -m f1_engineer @args
