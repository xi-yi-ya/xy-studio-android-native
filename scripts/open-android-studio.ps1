param([string]$StudioHome = 'D:\tool\AndroidStudio\android-studio')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskExe = Join-Path $StudioHome 'bin\studio64.exe'
if (-not (Test-Path -LiteralPath $taskExe)) { throw "Android Studio missing: $taskExe" }
$oldProperties=$env:STUDIO_PROPERTIES; $oldSdk=$env:ANDROID_HOME; $oldGradle=$env:GRADLE_USER_HOME
try {
    $env:STUDIO_PROPERTIES = Join-Path (Split-Path $StudioHome -Parent) 'studio-local.properties'
    $env:ANDROID_HOME = Join-Path $taskRoot 'local-data\android-tools\sdk'
    $env:GRADLE_USER_HOME = Join-Path $taskRoot 'local-data\android-tools\gradle-cache'
    # This is the interactive IDE the user requested; keep its window visible.
    Start-Process -FilePath $taskExe -ArgumentList ('"' + (Join-Path $taskRoot 'android-native') + '"') -WorkingDirectory $taskRoot
} finally { $env:STUDIO_PROPERTIES=$oldProperties; $env:ANDROID_HOME=$oldSdk; $env:GRADLE_USER_HOME=$oldGradle }
