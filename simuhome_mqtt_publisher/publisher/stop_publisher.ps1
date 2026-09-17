# 停止后台运行的发布器
$procs = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*publisher\publisher.py*" }

if (-not $procs) {
    Write-Output "没有正在运行的发布器进程"
    exit 0
}

foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force
    Write-Output "已停止发布器：PID $($p.ProcessId)"
}
