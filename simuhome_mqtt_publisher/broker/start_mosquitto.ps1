# 启动 Mosquitto（需先安装官方 Windows 版；工作目录固定为本目录，相对路径配置才成立）
param(
    [string]$MosquittoExe = "C:\Program Files\mosquitto\mosquitto.exe"
)

$brokerDir = $PSScriptRoot
$conf = Join-Path $brokerDir "mosquitto.conf"

if (-not (Test-Path $MosquittoExe)) {
    Write-Error "未找到 $MosquittoExe，请先从 mosquitto.org 安装，或用 -MosquittoExe 指定路径"
    exit 1
}

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*mosquitto.exe*" -and $_.CommandLine -like "*mosquitto.conf*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $MosquittoExe -ArgumentList "-c", $conf -WorkingDirectory $brokerDir -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Error "找不到 python，请安装 Python 3.11+ 并加入 PATH"
    exit 1
}

& $python (Join-Path $brokerDir "health_check.py")
