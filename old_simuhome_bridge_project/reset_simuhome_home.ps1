$configPath = "D:\D_coderesource\simuhome\simuprocject\Simuhome_experiment\home_full.json"
$resetUrl = "http://127.0.0.1:8000/api/simulation/reset"

$body = Get-Content $configPath -Raw
$response = Invoke-RestMethod `
    -Method Post `
    -Uri $resetUrl `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 6
