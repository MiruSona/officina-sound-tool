# SoundTool setup (Windows PowerShell 5.1)
#
#   powershell -NoProfile -File <path>\SoundTool\setup.ps1
#
# Makes .venv if missing, installs soundtool in editable mode with test extras,
# then runs a smoke test. Run it after every checkout / submodule update.
# Text is English on purpose: PowerShell 5.1 mangles non-ASCII in script files.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

# README asks for Python 3.14 through the py launcher.
$py = Get-Command py -ErrorAction SilentlyContinue
if ($null -eq $py) {
    Write-Host "python launcher 'py' not found. Install Python 3.14 from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}
& py -3.14 --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.14 not found (py -3.14). Install it first, see the Install section of README.md." -ForegroundColor Red
    exit 1
}

$venv = Join-Path $root '.venv'
$python = Join-Path $venv 'Scripts\python.exe'
if (Test-Path $python) {
    # An old venv built on another Python breaks the install in confusing ways.
    # This script never deletes it by itself: say what is wrong and stop.
    $venvVer = ''
    try { $venvVer = (& $python -c "import sys; print('{}.{}'.format(sys.version_info[0], sys.version_info[1]))") } catch { $venvVer = '' }
    if ($LASTEXITCODE -ne 0) { $venvVer = '' }
    $global:LASTEXITCODE = 0
    $venvVer = ($venvVer | Out-String).Trim()
    if ($venvVer -ne '3.14') {
        if ($venvVer -eq '') { $venvVer = 'unknown (it did not run)' }
        Write-Host ("Existing .venv runs Python {0}, not 3.14 : {1}" -f $venvVer, $venv) -ForegroundColor Red
        Write-Host "Delete the .venv folder by hand, then run this script again." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "Creating venv : $venv"
    & py -3.14 -m venv $venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installing soundtool (editable, with test extras)"
& $python -m pip install -e "$root[test]"
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed (offline?). Fix the network, or install by hand as the Install section of README.md shows." -ForegroundColor Red
    exit 1
}

# External programs are not downloaded here: they are large and have their own licenses.
$externals = @(
    @{ Path = 'external\rfxgen.exe'; Name = 'rfxgen' },
    @{ Path = 'external\fluidsynth\bin\fluidsynth.exe'; Name = 'FluidSynth' },
    @{ Path = 'external\soundfont\GeneralUser-GS.sf2'; Name = 'GeneralUser GS soundfont' }
)
foreach ($ext in $externals) {
    if (-not (Test-Path (Join-Path $root $ext.Path))) {
        Write-Host ("Missing external program: {0} ({1}). Put it there by hand, see the table in the Install section of README.md." -f $ext.Name, $ext.Path) -ForegroundColor Yellow
    }
}

Write-Host "Smoke test : python -m soundtool --help"
& $python -m soundtool --help | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Smoke test failed." -ForegroundColor Red
    exit 1
}

# Stamp the finish time. A -Check run elsewhere reads this file to tell whether .venv is stale;
# the .venv folder mtime does not change on a pip reinstall, so it cannot be used for that.
$stamp = Join-Path $venv '.setup-stamp'
Set-Content -LiteralPath $stamp -Value ((Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')) -Encoding ASCII

Write-Host "Done. Use $python -m soundtool ..." -ForegroundColor Green
exit 0
