$bridgeRoot = "D:\D_coderesource\simuhome\simuhome_bridge_project\bridge"
$pythonExe = "C:\ProgramData\anaconda3\python.exe"
$healthUrl = "http://127.0.0.1:8010/health"
$stdoutLog = "D:\D_coderesource\simuhome\simuhome_bridge_project\logs\simuhome-bridge.stdout.log"
$stderrLog = "D:\D_coderesource\simuhome\simuhome_bridge_project\logs\simuhome-bridge.stderr.log"

New-Item -ItemType Directory -Force -Path "D:\D_coderesource\simuhome\simuhome_bridge_project\logs" | Out-Null

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*simuhome_bridge_project\\bridge*" -and $_.CommandLine -like "*app.py*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $pythonExe `
        -ArgumentList "app.py" `
        -WorkingDirectory $bridgeRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog

    Start-Sleep -Seconds 5
}

try {
    $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
    Write-Output "SimuHome Bridge is ready: $($response.StatusCode)"
    Write-Output "Browser viewer: http://localhost:8010/logs"
} catch {
    Write-Error "SimuHome Bridge failed to start or is unreachable: $($_.Exception.Message)"
}
