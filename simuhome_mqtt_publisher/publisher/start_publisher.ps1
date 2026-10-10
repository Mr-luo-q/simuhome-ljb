# 后台启动 SimuHome → MQTT 发布器
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "publisher.py"
$logDir = Join-Path $root "logs"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Error "找不到 python，请安装 Python 3.11+ 并加入 PATH"
    exit 1
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*publisher.py*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $python `
        -ArgumentList $script `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "publisher.console.log") `
        -RedirectStandardError (Join-Path $logDir "publisher.console.err.log")
    Start-Sleep -Seconds 5
}

$proc = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*publisher.py*" } |
    Select-Object -First 1

if ($proc) {
    Write-Output "发布器运行中：PID $($proc.ProcessId)，日志 $logDir\publisher.console.err.log"
} else {
    Write-Error "发布器未启动，请查看 $logDir\publisher.console.err.log"
}
