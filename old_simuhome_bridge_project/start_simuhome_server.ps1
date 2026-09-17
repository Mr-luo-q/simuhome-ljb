$repoRoot = "D:\D_coderesource\simuhome\simuprocject\Simuhome_experiment"
$pythonExe = "C:\ProgramData\anaconda3\python.exe"
$healthUrl = "http://127.0.0.1:8000/api/__health__"

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*src.simulator.api.app*" } |
    Select-Object -First 1

if (-not $running) {
    Start-Process $pythonExe `
        -ArgumentList "-m", "src.simulator.api.app" `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden

    Start-Sleep -Seconds 5
}

try {
    $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
    Write-Output "SimuHome API is ready: $($response.StatusCode)"
} catch {
    Write-Error "SimuHome API failed to start or is unreachable: $($_.Exception.Message)"
}
