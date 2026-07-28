$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

function ConvertTo-ProcessArguments {
    param([string[]]$Arguments)

    return (($Arguments | ForEach-Object {
        '"' + $_.Replace('"', '\"') + '"'
    }) -join ' ')
}

function Invoke-ExternalProcess {
    param(
        [string]$Command,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 0
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Command
    $startInfo.Arguments = ConvertTo-ProcessArguments $Arguments
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    [void]$process.Start()
    $standardOutput = $process.StandardOutput.ReadToEndAsync()
    $standardError = $process.StandardError.ReadToEndAsync()

    $timedOut = $false
    if ($TimeoutSeconds -gt 0 -and -not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $timedOut = $true
        $process.Kill()
    }

    $process.WaitForExit()
    $stopwatch.Stop()

    return [PSCustomObject]@{
        ExitCode = $process.ExitCode
        TimedOut = $timedOut
        StandardOutput = $standardOutput.GetAwaiter().GetResult()
        StandardError = $standardError.GetAwaiter().GetResult()
        ElapsedSeconds = $stopwatch.Elapsed.TotalSeconds
    }
}

function Write-ProcessOutput {
    param($Result)

    if ($Result.StandardOutput) {
        Write-Host $Result.StandardOutput.TrimEnd()
    }

    if ($Result.StandardError) {
        [Console]::Error.Write($Result.StandardError)
    }
}

function Test-ExecutableFile {
    param([string]$Path)

    try {
        return Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction Stop
    }
    catch {
        return $false
    }
}

function Test-PythonCandidate {
    param(
        [string]$Command,
        [string[]]$Arguments = @(),
        [bool]$RequiresFile = $false
    )

    $display = ("$Command " + ($Arguments -join " ")).Trim()
    Write-Host "Checking Python candidate: $display"

    if ($RequiresFile -and -not (Test-ExecutableFile $Command)) {
        Write-Host "not found"
        return $null
    }

    try {
        $result = Invoke-ExternalProcess $Command ($Arguments + @(
            "-c",
            "import sys; print(sys.version); print(sys.executable)"
        )) 5
    }
    catch {
        Write-Host "not found"
        return $null
    }

    if ($result.TimedOut) {
        Write-Host "timed out"
        return $null
    }

    if ($result.ExitCode -ne 0) {
        Write-Host "failed with exit code $($result.ExitCode)"
        return $null
    }

    $lines = @($result.StandardOutput -split "`r?`n" | Where-Object { $_ })
    if ($lines.Count -lt 2 -or $lines[0] -notmatch "^3\.12\.") {
        Write-Host "wrong version"
        return $null
    }

    Write-Host "accepted"
    return [PSCustomObject]@{
        Command = $Command
        Arguments = $Arguments
        Version = $lines[0]
        Executable = $lines[1]
    }
}

function Select-Python312 {
    if ($env:ANALYZER_PYTHON) {
        $selected = Test-PythonCandidate $env:ANALYZER_PYTHON @() $true
        if ($selected) {
            return $selected
        }
    }

    $codexVenvPython = Join-Path $RepoRoot ".codex-venv\Scripts\python.exe"
    $selected = Test-PythonCandidate $codexVenvPython @() $true
    if ($selected) {
        return $selected
    }

    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $selected = Test-PythonCandidate $venvPython @() $true
    if ($selected) {
        return $selected
    }

    $toolsPython = Join-Path $RepoRoot ".tools\python312\python.exe"
    $selected = Test-PythonCandidate $toolsPython @() $true
    if ($selected) {
        return $selected
    }

    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $selected = Test-PythonCandidate $launcher.Source @("-3.12") $false
    }
    else {
        Write-Host "Checking Python candidate: py -3.12"
        Write-Host "not found"
        $selected = $null
    }
    if ($selected) {
        return $selected
    }

    $python312 = Get-Command python3.12 -ErrorAction SilentlyContinue
    if ($python312) {
        $selected = Test-PythonCandidate $python312.Source @() $false
    }
    else {
        Write-Host "Checking Python candidate: python3.12"
        Write-Host "not found"
        $selected = $null
    }
    if ($selected) {
        return $selected
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $selected = Test-PythonCandidate $python.Source @() $false
    }
    else {
        Write-Host "Checking Python candidate: python"
        Write-Host "not found"
    }

    return $selected
}

$selectedPython = Select-Python312
if (-not $selectedPython) {
    throw "No usable Python 3.12 interpreter was found."
}

Write-Host "Repository root: $RepoRoot"
Write-Host "Selected Python: $($selectedPython.Command) $($selectedPython.Arguments -join ' ')"
Write-Host "Python version: $($selectedPython.Version)"
Write-Host "sys.executable: $($selectedPython.Executable)"

Push-Location $RepoRoot

Write-Host "Running py_compile..."
$compileResult = Invoke-ExternalProcess $selectedPython.Command (
    $selectedPython.Arguments + @(
        "-m",
        "py_compile",
        "Analyzer/squashfs.py",
        "Analyzer/test_squashfs.py"
    )
)
Write-ProcessOutput $compileResult
Write-Host "py_compile completed in $([Math]::Round($compileResult.ElapsedSeconds, 2)) seconds, exit code $($compileResult.ExitCode)"
if ($compileResult.ExitCode -ne 0) {
    Pop-Location
    exit $compileResult.ExitCode
}

Write-Host "Running unittest..."
$unittestResult = Invoke-ExternalProcess $selectedPython.Command (
    $selectedPython.Arguments + @(
        "-m",
        "unittest",
        "discover",
        "-s",
        "Analyzer",
        "-p",
        "test_*.py",
        "-v"
    )
)
Write-ProcessOutput $unittestResult
Write-Host "unittest completed in $([Math]::Round($unittestResult.ElapsedSeconds, 2)) seconds, exit code $($unittestResult.ExitCode)"
Pop-Location
exit $unittestResult.ExitCode
