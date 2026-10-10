# 生成 MQTT 账号密码：broker / 发布器 / HA 三处共用同一组
# 默认写入本目录：mosquitto.passwd（Mosquitto 读）与 mosquitto.credentials.txt（发布器读、HA 手填）
param(
    [string]$User = "simuhome",
    [string]$Password,
    [string]$PasswdPath,
    [string]$CredentialsPath,
    [string]$MosquittoPasswdExe = "C:\Program Files\mosquitto\mosquitto_passwd.exe",
    [switch]$Force
)

$brokerDir = $PSScriptRoot
if (-not $PasswdPath) { $PasswdPath = Join-Path $brokerDir "mosquitto.passwd" }
if (-not $CredentialsPath) { $CredentialsPath = Join-Path $brokerDir "mosquitto.credentials.txt" }

if ((Test-Path $PasswdPath) -and (-not $Force)) {
    Write-Output "已存在 $PasswdPath；需要重设时加 -Force（HA 与发布器要同步更新）"
    exit 0
}
if (-not (Test-Path $MosquittoPasswdExe)) {
    Write-Error "未找到 mosquitto_passwd.exe：$MosquittoPasswdExe；请先安装 Mosquitto，或用 -MosquittoPasswdExe 指定"
    exit 1
}
if (-not $Password) {
    $chars = (48..57) + (65..90) + (97..122)
    $Password = -join ($chars | Get-Random -Count 16 | ForEach-Object { [char]$_ })
}

& $MosquittoPasswdExe -c -b $PasswdPath $User $Password
if ($LASTEXITCODE -ne 0) {
    Write-Error "mosquitto_passwd 执行失败（退出码 $LASTEXITCODE）"
    exit 1
}

# 不带 BOM 的 UTF-8：发布器按 utf-8 读取，BOM 会粘在用户名上导致认证失败
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($CredentialsPath, @($User, $Password), $utf8NoBom)

Write-Output "已写入：$PasswdPath"
Write-Output "已写入：$CredentialsPath"
Write-Output "用户名：$User"
Write-Output "密码：  $Password"
Write-Output "下一步：重启 broker（start_mosquitto.ps1），并在 HA 的 MQTT 集成里填同一组账号密码。"
