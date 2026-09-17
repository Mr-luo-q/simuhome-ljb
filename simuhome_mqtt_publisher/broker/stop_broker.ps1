# 停止后台运行的 MQTT broker
$procs = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*run_broker.py*" }

if (-not $procs) {
    Write-Output "没有正在运行的 broker 进程"
    exit 0
}

foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force
    Write-Output "已停止 broker：PID $($p.ProcessId)"
}
