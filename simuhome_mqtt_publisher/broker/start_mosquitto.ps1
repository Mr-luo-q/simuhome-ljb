# 启动 Mosquitto（需先安装官方 Windows 版）
$exe = "C:\Program Files\mosquitto\mosquitto.exe"
$conf = "D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\mosquitto.conf"

if (-not (Test-Path $exe)) {
    Write-Error "未找到 $exe，请先安装 _tools\mqtt\mosquitto-2.0.20-install-windows-x64.exe"
    exit 1
}

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*mosquitto.exe*" -and $_.CommandLine -like "*mosquitto.conf*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $exe -ArgumentList "-c", $conf -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

& "C:\ProgramData\anaconda3\python.exe" "D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\health_check.py"
