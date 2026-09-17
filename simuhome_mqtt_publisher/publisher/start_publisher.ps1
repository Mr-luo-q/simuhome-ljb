# 后台启动 SimuHome → MQTT 发布器
$root = "D:\D_coderesource\simuhome\simuhome_mqtt_publisher"
$python = "C:\ProgramData\anaconda3\python.exe"
$script = "$root\publisher\publisher.py"
$logDir = "$root\logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*publisher\publisher.py*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $python `
        -ArgumentList $script `
        -WorkingDirectory "$root\publisher" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$logDir\publisher.console.log" `
        -RedirectStandardError "$logDir\publisher.console.err.log"
    Start-Sleep -Seconds 5
}

$proc = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*publisher\publisher.py*" } |
    Select-Object -First 1

if ($proc) {
    Write-Output "发布器运行中：PID $($proc.ProcessId)，日志 $logDir\publisher.console.err.log"
} else {
    Write-Error "发布器未启动，请查看 $logDir\publisher.console.err.log"
}
