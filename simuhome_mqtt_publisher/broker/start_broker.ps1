# 后台启动 MQTT broker（隐藏窗口），并把输出写入 logs 目录
$root = "D:\D_coderesource\simuhome\simuhome_mqtt_publisher"
$python = "C:\ProgramData\anaconda3\python.exe"
$script = "$root\broker\run_broker.py"
$logDir = "$root\logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*run_broker.py*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $python `
        -ArgumentList $script `
        -WorkingDirectory "$root\broker" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$logDir\broker.console.log" `
        -RedirectStandardError "$logDir\broker.console.err.log"
    Start-Sleep -Seconds 4
}

# 用真正的 MQTT 连接做健康检查
& $python "$root\broker\health_check.py"
if ($LASTEXITCODE -eq 0) {
    Write-Output "MQTT broker 就绪：127.0.0.1:1883（日志 $logDir\broker.log）"
} else {
    Write-Error "MQTT broker 健康检查失败，请查看 $logDir\broker.log"
}
