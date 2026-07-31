param(
    [string]$ModelPath = "",
    [string]$ServerPath = "",
    [string]$PythonPath = "",
    [int]$Port = 8083,
    [string]$ModelAlias = "librarian-shadow",
    [string]$OutputPath = "",
    [string]$StatusPath = "",
    [int]$GpuLayers = -1,
    [switch]$NoThink
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)

$serverWasExplicit = [bool](
    $ServerPath -or $env:TORMENT_NEXUS_LIBRARIAN_SERVER_PATH
)
$pythonWasExplicit = [bool](
    $PythonPath -or
    $env:TORMENT_NEXUS_LIBRARIAN_PYTHON -or
    $env:TORMENT_NEXUS_PYTHON
)

if (-not $ModelPath) {
    $ModelPath = $env:TORMENT_NEXUS_LIBRARIAN_MODEL_PATH
}
if (-not $ModelPath) {
    throw (
        "No librarian model is selected by default. Supply -ModelPath or " +
        "TORMENT_NEXUS_LIBRARIAN_MODEL_PATH explicitly."
    )
}
$effectiveNoThink = [bool]$NoThink

if (-not $ServerPath) {
    $ServerPath = $env:TORMENT_NEXUS_LIBRARIAN_SERVER_PATH
}
if (-not $ServerPath) {
    $ServerPath = Join-Path $root (
        "llama.cpp\build\bin\Release\llama-server.exe"
    )
}
if (
    -not $serverWasExplicit -and
    -not (Test-Path -LiteralPath $ServerPath -PathType Leaf)
) {
    $developerServer = Join-Path $root (
        "llama.cpp\runtime\desktop-cuda-12.4-b9637\llama-server.exe"
    )
    if (Test-Path -LiteralPath $developerServer -PathType Leaf) {
        $ServerPath = $developerServer
    }
}

if (-not $PythonPath) {
    $PythonPath = $env:TORMENT_NEXUS_LIBRARIAN_PYTHON
}
if (-not $PythonPath) {
    $PythonPath = $env:TORMENT_NEXUS_PYTHON
}
if (-not $PythonPath) {
    $PythonPath = Join-Path $root "python\python.exe"
}
if (
    -not $pythonWasExplicit -and
    -not (Test-Path -LiteralPath $PythonPath -PathType Leaf) -and
    $env:LocalAppData
) {
    $developerPython = Join-Path $env:LocalAppData (
        "Python\pythoncore-3.14-64\python.exe"
    )
    if (Test-Path -LiteralPath $developerPython -PathType Leaf) {
        $PythonPath = $developerPython
    }
}

if (-not $OutputPath) {
    $OutputPath = Join-Path $root (
        "assistant\logs\researchc_librarian_probe.json"
    )
}
if (-not $StatusPath) {
    $StatusPath = Join-Path $root (
        "assistant\logs\researchc_librarian_probe_status.json"
    )
}

$ModelPath = [System.IO.Path]::GetFullPath($ModelPath)
$ServerPath = [System.IO.Path]::GetFullPath($ServerPath)
$PythonPath = [System.IO.Path]::GetFullPath($PythonPath)
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$StatusPath = [System.IO.Path]::GetFullPath($StatusPath)
$logDirectory = Join-Path $root "assistant\logs"
[System.IO.Directory]::CreateDirectory($logDirectory) | Out-Null
[System.IO.Directory]::CreateDirectory(
    [System.IO.Path]::GetDirectoryName($OutputPath)
) | Out-Null
[System.IO.Directory]::CreateDirectory(
    [System.IO.Path]::GetDirectoryName($StatusPath)
) | Out-Null

function Quote-ProbeArgument {
    param([string]$Value)
    if ($Value.Contains('"')) {
        throw "A probe process argument contains an unsupported quote."
    }
    return '"' + $Value + '"'
}

function Write-ProbeStatus {
    param(
        [string]$State,
        [string]$Detail = "",
        [string]$ModelSha256 = "",
        [string]$ServerBundleSha256 = ""
    )
    $record = [ordered]@{
        schema = 1
        state = $State
        detail = $Detail
        recorded_utc = [DateTime]::UtcNow.ToString("o")
        model_sha256 = $ModelSha256
        server_bundle_sha256 = $ServerBundleSha256
        output = $OutputPath
    }
    $temporary = $StatusPath + ".tmp"
    [System.IO.File]::WriteAllText(
        $temporary,
        ($record | ConvertTo-Json -Compress),
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporary -Destination $StatusPath -Force
}

$serverProcess = $null
$keyFile = $null
$modelDigest = ""
$serverDigest = ""
$environmentNames = @(
    "TORMENT_NEXUS_LIBRARIAN_SHADOW",
    "TORMENT_NEXUS_LIBRARIAN_URL",
    "TORMENT_NEXUS_LIBRARIAN_KEY",
    "TORMENT_NEXUS_LIBRARIAN_MODEL_ID",
    "TORMENT_NEXUS_LIBRARIAN_MODEL_SHA256",
    "TORMENT_NEXUS_LIBRARIAN_SERVER_SHA256",
    "TORMENT_NEXUS_LIBRARIAN_NO_THINK",
    "TORMENT_NEXUS_PROBE_SERVER_PATH"
)
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = (
        [Environment]::GetEnvironmentVariable($name, "Process")
    )
}

try {
    if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) {
        throw "The requested librarian model does not exist."
    }
    if (-not (Test-Path -LiteralPath $ServerPath -PathType Leaf)) {
        throw "The requested llama-server runtime does not exist."
    }
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw (
            "The bundled Python interpreter was not found. Supply " +
            "-PythonPath or TORMENT_NEXUS_LIBRARIAN_PYTHON explicitly."
        )
    }
    if ($Port -lt 1024 -or $Port -gt 65535) {
        throw "The librarian port must be between 1024 and 65535."
    }
    if (Get-NetTCPConnection -State Listen -LocalPort $Port `
            -ErrorAction SilentlyContinue) {
        throw "The requested librarian port is already in use."
    }
    if ($Port -in @(8080, 8082, 8084, 8093)) {
        throw "The librarian must not reuse a project model-service port."
    }
    if ($ModelAlias -notmatch '^[A-Za-z0-9._-]{1,120}$') {
        throw "The librarian model alias is invalid."
    }

    Write-ProbeStatus -State "hashing"
    $modelDigest = (
        Get-FileHash -LiteralPath $ModelPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    $env:TORMENT_NEXUS_PROBE_SERVER_PATH = $ServerPath
    Push-Location (Join-Path $root "assistant")
    try {
        $serverDigest = (
            & $PythonPath -B -c (
                "import os; from core import research_c; " +
                "print(research_c.server_bundle_digest(" +
                "os.environ['TORMENT_NEXUS_PROBE_SERVER_PATH']) or '')"
            )
        ).Trim()
        $serverDigestExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if (
        $serverDigestExitCode -ne 0 -or
        $serverDigest -notmatch '^[0-9a-f]{64}$'
    ) {
        throw "The llama-server inference closure could not be hashed."
    }

    $random = New-Object byte[] 32
    $randomSource = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $randomSource.GetBytes($random)
    }
    finally {
        $randomSource.Dispose()
    }
    $apiKey = (
        [BitConverter]::ToString($random) -replace "-", ""
    ).ToLowerInvariant()
    $keyFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText(
        $keyFile,
        $apiKey,
        [System.Text.UTF8Encoding]::new($false)
    )

    $stdoutLog = Join-Path $logDirectory "librarian_server.stdout.log"
    $stderrLog = Join-Path $logDirectory "librarian_server.stderr.log"
    if ($GpuLayers -lt 0) {
        $cudaBackend = Join-Path (
            [System.IO.Path]::GetDirectoryName($ServerPath)
        ) "ggml-cuda.dll"
        $GpuLayers = if (
            Test-Path -LiteralPath $cudaBackend -PathType Leaf
        ) { 99 } else { 0 }
    }
    $arguments = @(
        "-m", (Quote-ProbeArgument $ModelPath),
        "-c", "4096",
        "-np", "1",
        "-b", "512",
        "-ub", "128",
        "--host", "127.0.0.1",
        "--port", [string]$Port,
        "--alias", $ModelAlias,
        "--api-key-file", (Quote-ProbeArgument $keyFile),
        "--cache-ram", "0",
        "-ngl", [string]$GpuLayers
    )

    Write-ProbeStatus `
        -State "loading" `
        -ModelSha256 $modelDigest `
        -ServerBundleSha256 $serverDigest
    $serverProcess = Start-Process `
        -FilePath $ServerPath `
        -ArgumentList $arguments `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru

    $headers = @{ Authorization = "Bearer $apiKey" }
    $ready = $false
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serverProcess.HasExited) {
            throw "The dedicated librarian server exited while loading."
        }
        try {
            $models = Invoke-RestMethod `
                -Uri "http://127.0.0.1:$Port/v1/models" `
                -Headers $headers `
                -TimeoutSec 2
            $ids = @($models.data | ForEach-Object { [string]$_.id })
            if ($ids.Count -eq 1 -and $ids[0] -eq $ModelAlias) {
                $ready = $true
                break
            }
        }
        catch {
            # Loading is expected to refuse connections for a while.
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) {
        throw "The dedicated librarian server did not become ready in time."
    }

    $env:TORMENT_NEXUS_LIBRARIAN_SHADOW = "1"
    $env:TORMENT_NEXUS_LIBRARIAN_URL = "http://127.0.0.1:$Port"
    $env:TORMENT_NEXUS_LIBRARIAN_KEY = $apiKey
    $env:TORMENT_NEXUS_LIBRARIAN_MODEL_ID = $ModelAlias
    $env:TORMENT_NEXUS_LIBRARIAN_MODEL_SHA256 = $modelDigest
    $env:TORMENT_NEXUS_LIBRARIAN_SERVER_SHA256 = $serverDigest
    if ($effectiveNoThink) {
        $env:TORMENT_NEXUS_LIBRARIAN_NO_THINK = "1"
    }
    else {
        $env:TORMENT_NEXUS_LIBRARIAN_NO_THINK = "0"
    }

    Write-ProbeStatus `
        -State "running" `
        -ModelSha256 $modelDigest `
        -ServerBundleSha256 $serverDigest
    Push-Location $root
    try {
        & $PythonPath -B tools\researchc_library_probe.py `
            --with-librarian `
            --enforce `
            --output $OutputPath | Out-Null
        $probeExitCode = $LASTEXITCODE
        if ($probeExitCode -ne 0) {
            throw "The librarian probe returned a failure."
        }
    }
    finally {
        Pop-Location
    }

    Write-ProbeStatus `
        -State "complete" `
        -ModelSha256 $modelDigest `
        -ServerBundleSha256 $serverDigest
}
catch {
    Write-ProbeStatus `
        -State "failed" `
        -Detail $_.Exception.Message `
        -ModelSha256 $modelDigest `
        -ServerBundleSha256 $serverDigest
    exit 1
}
finally {
    if ($null -ne $serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $serverProcess.Id -Timeout 10 `
            -ErrorAction SilentlyContinue
    }
    if ($keyFile -and (Test-Path -LiteralPath $keyFile)) {
        [System.IO.File]::Delete($keyFile)
    }
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            "Process"
        )
    }
}
