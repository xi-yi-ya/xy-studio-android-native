param([string]$JavaHome, [string]$SdkRoot, [switch]$Test, [switch]$DeviceTests)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$taskTools=Join-Path $taskRoot 'local-data\android-tools'
if (-not $JavaHome) { $JavaHome=(Get-ChildItem "$taskTools\jdk" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }
if (-not $JavaHome) { $JavaHome=$env:JAVA_HOME }
if (-not $SdkRoot) { $SdkRoot=Join-Path $taskTools 'sdk' }
if (-not (Test-Path "$JavaHome\bin\java.exe")) { throw '需要 JDK 21，请通过 -JavaHome 指定；不修改全局环境' }
if (-not (Test-Path "$SdkRoot\platforms\android-36\android.jar")) { throw '需要 Android SDK Platform 36，请通过 -SdkRoot 指定' }
$taskOldJava=$env:JAVA_HOME; $taskOldSdk=$env:ANDROID_HOME; $taskOldGradle=$env:GRADLE_USER_HOME
try {
    $env:JAVA_HOME=$JavaHome; $env:ANDROID_HOME=$SdkRoot; $env:GRADLE_USER_HOME=Join-Path $taskTools 'gradle-cache'
    $taskArgs=@('-p',(Join-Path $taskRoot 'android-native'),':app:assembleDebug','--no-daemon','--console=plain')
    if($Test){$taskArgs += ':app:testDebugUnitTest'}
    if($DeviceTests){$taskArgs += ':app:assembleDebugAndroidTest'}
    & "$taskRoot\android-native\gradlew.bat" @taskArgs
    if($LASTEXITCODE -ne 0){throw 'Android 构建失败，请查看上方日志'}
    $taskDestination=Join-Path $taskRoot 'releases\android-native-preview'
    New-Item -ItemType Directory -Force $taskDestination | Out-Null
    $taskApk=Join-Path $taskDestination 'XY-Studio-Android-debug.apk'
    if(Test-Path $taskApk){Copy-Item -LiteralPath $taskApk -Destination "$taskApk.$(Get-Date -Format yyyyMMdd-HHmmss).bak"}
    Copy-Item -LiteralPath "$taskRoot\android-native\app\build\outputs\apk\debug\app-debug.apk" -Destination $taskApk
    Get-FileHash -LiteralPath $taskApk -Algorithm SHA256
} finally { $env:JAVA_HOME=$taskOldJava; $env:ANDROID_HOME=$taskOldSdk; $env:GRADLE_USER_HOME=$taskOldGradle }
