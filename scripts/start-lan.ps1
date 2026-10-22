param([string]$Bind, [int]$Port = 8765, [string]$Project)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
if (-not $Bind) {
    $Bind = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker'
    } | Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $Bind) { throw '未找到局域网地址，请使用 -Bind 指定 PC 的局域网 IPv4' }
}
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $taskPython)) { throw '请先创建项目 .venv 并安装 requirements-lan.txt' }
if (-not (Test-Path (Join-Path $taskRoot 'frontend\dist\index.html'))) { throw '请先运行 npm --prefix frontend run build' }
Push-Location $taskRoot
try {
    $taskArgs = @('-m','studio.lan','--bind',$Bind,'--port',"$Port")
    if ($Project) { $taskArgs += @('--project',$Project) }
    & $taskPython @taskArgs
} finally { Pop-Location }
