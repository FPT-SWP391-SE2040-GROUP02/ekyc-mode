param([string]$PythonPath = '', [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot

function Get-CompatiblePython {
    param([string]$Candidate, [string[]]$PrefixArgs = @())
    $ProbeCode = "import sys,struct,platform; print(sys.executable if sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8 and platform.machine().upper() in ('AMD64','X86_64') else '')"
    try {
        $ProbeOutput = & $Candidate @PrefixArgs -c $ProbeCode 2>$null
        if ($LASTEXITCODE -eq 0 -and $ProbeOutput) { return ([string]$ProbeOutput).Trim() }
    } catch { }
    return ''
}

if ($PythonPath) {
    $PythonPath = Get-CompatiblePython -Candidate $PythonPath
} else {
    if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
        $PythonPath = Get-CompatiblePython -Candidate '.\.venv\Scripts\python.exe'
    }
    foreach ($Launcher in @('py', 'pymanager')) {
        if (-not $PythonPath -and (Get-Command $Launcher -ErrorAction SilentlyContinue)) {
            $PythonPath = Get-CompatiblePython -Candidate $Launcher -PrefixArgs @('-3.12')
        }
    }
    if (-not $PythonPath -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $PythonPath = Get-CompatiblePython -Candidate 'python'
    }
}
if (-not $PythonPath) {
    throw 'Python 3.12 x64 was not found. Read HUONG_DAN_CHAY.txt, install Python 3.12, then run setup.cmd again.'
}
Write-Host "Python 3.12 x64: $PythonPath"
if ($CheckOnly) { Write-Host 'Python check passed. No packages were installed.'; exit 0 }

if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    if (-not (Get-CompatiblePython -Candidate '.\.venv\Scripts\python.exe')) {
        throw 'The .venv is incompatible or copied from another computer. Rename it to .venv-old and run setup.cmd again.'
    }
} else {
    & $PythonPath -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. Use a writable folder such as C:\eKYC.' }
}
$RequirementsPath = 'requirements.lock.txt'
if (-not (Test-Path -LiteralPath $RequirementsPath)) { $RequirementsPath = 'requirements.txt' }
Write-Host '[1/4] Installing Python packages. Internet is required on first setup.'
& '.\.venv\Scripts\python.exe' -m pip install -r $RequirementsPath
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check Internet access and the message above.' }
Write-Host '[2/4] Installing PyTorch and torchvision CPU.'
& '.\.venv\Scripts\python.exe' -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'PyTorch CPU installation failed. Check Internet access.' }
Write-Host '[3/4] Checking bundled models; downloading only missing files.'
& '.\.venv\Scripts\python.exe' download_models.py
if ($LASTEXITCODE -ne 0) { throw 'Model preparation failed. See the message above.' }
Write-Host '[4/4] Checking the installation.'
& '.\.venv\Scripts\python.exe' -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Some Python packages are incompatible. See the message above.' }
& '.\.venv\Scripts\python.exe' check_installation.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime check failed. Read HUONG_DAN_CHAY.txt.' }
Write-Host 'SETUP COMPLETE. Run START.cmd and open http://127.0.0.1:8879'
