# 停止 Mosquitto
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "mosquitto.exe" }
if (-not $procs) {
    Write-Output "Mosquitto 未在运行"
    exit 0
}
foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force
    Write-Output "已停止 Mosquitto：PID $($p.ProcessId)"
}
