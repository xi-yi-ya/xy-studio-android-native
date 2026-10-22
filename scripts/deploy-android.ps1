param(
    [string]$Serial,
    [string]$Adb,
    [switch]$Build,
    [string]$LanReadyFile,
    [switch]$Generate
)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
if(-not $Adb){$Adb=Join-Path $taskRoot 'local-data\android-tools\sdk\platform-tools\adb.exe'}
if(-not(Test-Path -LiteralPath $Adb)){throw '找不到 ADB；请用 -Adb 指定已有 adb.exe'}
if($Generate -and -not $LanReadyFile){throw '-Generate 需要 -LanReadyFile；测试会在当前 PC 项目创建真实生成任务并使用 GPU'}
if($Build){& "$PSScriptRoot\build-android.ps1" -Test -DeviceTests:([bool]$LanReadyFile)}
$taskListing=& $Adb devices -l
$taskListing | Write-Output
$taskDevices=@($taskListing | Where-Object {$_ -match '^\S+\s+device(?:\s|$)'} | ForEach-Object {($_ -split '\s+')[0]})
if(-not $Serial){
    if($taskDevices.Count -ne 1){throw '需要恰好一台已授权设备；保持手机解锁并允许 USB 调试。多设备请指定 -Serial'}
    $Serial=$taskDevices[0]
}
if($Serial -notin $taskDevices){throw '指定设备尚未处于 device 状态；不执行安装'}
$taskApk=Join-Path $taskRoot 'releases\android-native-preview\XY-Studio-Android-debug.apk'
if(-not(Test-Path -LiteralPath $taskApk)){throw '请先运行 build-android.ps1'}
$taskStamp=Get-Date -Format yyyyMMdd-HHmmss
$taskEvidence=Join-Path $taskRoot "local-data\android-device-$taskStamp"
New-Item -ItemType Directory -Force $taskEvidence | Out-Null
$taskModel=(& $Adb -s $Serial shell getprop ro.product.model).Trim()
$taskAndroid=(& $Adb -s $Serial shell getprop ro.build.version.release).Trim()
@{model=$taskModel;android=$taskAndroid;apkSha256=(Get-FileHash $taskApk -Algorithm SHA256).Hash;started=(Get-Date -Format o)} |
    ConvertTo-Json | Set-Content -LiteralPath "$taskEvidence\device.json" -Encoding UTF8
& $Adb -s $Serial install --no-streaming -r $taskApk
if($LASTEXITCODE -ne 0){throw '安装失败；请查看手机是否显示安装确认。不会卸载或清除应用数据'}
& $Adb -s $Serial shell am start -W -n 'cn.xiyi.xystudio.nativeapp/cn.xiyi.xystudio.MainActivity'
if($LASTEXITCODE -ne 0){throw '应用启动失败'}
try {
    if($LanReadyFile){
        $taskReady=Get-Content -LiteralPath $LanReadyFile -Raw | ConvertFrom-Json
        if(-not $taskReady.base -or -not $taskReady.code){throw 'LAN ready 文件缺少地址或连接密码'}
        $taskTestApk=Join-Path $taskRoot 'android-native\app\build\outputs\apk\androidTest\debug\app-debug-androidTest.apk'
        & $Adb -s $Serial install --no-streaming -r $taskTestApk
        if($LASTEXITCODE -ne 0){throw '设备测试包安装失败'}
        # Restart only this app to test the pairing screen; preferences and user data remain.
        & $Adb -s $Serial shell am force-stop cn.xiyi.xystudio.nativeapp
        & $Adb -s $Serial shell am start -W -n 'cn.xiyi.xystudio.nativeapp/cn.xiyi.xystudio.MainActivity'
        $taskArgs=@('-s',$Serial,'shell','am','instrument','-w','-r','-e','class','cn.xiyi.xystudio.RealLanSmokeTest','-e','base',$taskReady.base,'-e','code',$taskReady.code)
        if($Generate){$taskArgs+=@('-e','generate','true')}
        $taskArgs+='cn.xiyi.xystudio.nativeapp.test/androidx.test.runner.AndroidJUnitRunner'
        $taskOutput=& $Adb @taskArgs 2>&1
        $taskTestExit=$LASTEXITCODE
        # Never print or persist the connection password, including unexpected runner diagnostics.
        $taskText=($taskOutput -join "`r`n").Replace([string]$taskReady.code,'[connection password redacted]')
        $taskText | Set-Content -LiteralPath "$taskEvidence\instrumentation.txt" -Encoding UTF8
        Write-Output $taskText
        & $Adb -s $Serial pull '/sdcard/Android/data/cn.xiyi.xystudio.nativeapp/files/qa' "$taskEvidence\screenshots"
        if($taskTestExit -ne 0 -or $taskText -notmatch 'OK \(1 test\)' -or $taskText -match 'FAILURES|INSTRUMENTATION_FAILED|INSTRUMENTATION_STATUS_CODE: -[234]'){
            throw "真机测试未通过；检查 $taskEvidence。不要盲目重新生成，请先检查 PC 任务状态"
        }
    }
} finally {
    # Read existing logs only; never clear the phone log buffers.
    $taskAppPid=(& $Adb -s $Serial shell pidof cn.xiyi.xystudio.nativeapp) -join ''
    if($taskAppPid.Trim() -match '^\d+$'){
        & $Adb -s $Serial logcat -d -t 2000 --pid=$($taskAppPid.Trim()) |
            Set-Content -LiteralPath "$taskEvidence\app-logcat.txt" -Encoding UTF8
    }
    & $Adb -s $Serial logcat -b crash -d -t 300 | Select-String -Pattern 'cn.xiyi.xystudio|AndroidRuntime|FATAL EXCEPTION' -Context 2,8 |
        Out-String | Set-Content -LiteralPath "$taskEvidence\crash-logcat.txt" -Encoding UTF8
    Write-Output "部署记录：$taskEvidence"
}
