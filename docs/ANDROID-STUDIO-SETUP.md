# 本机 Android Studio 开发环境

安装目录：`D:\tool\AndroidStudio\android-studio`。官方 Windows ZIP 安装，无需管理员权限；保留下载文件，未覆盖其他工具。

版本：Android Studio Rabbit 1 / 2026.2.1，build `262.9437.185.2621.16467767`。
来源：[Android 官方下载页](https://developer.android.com/studio)。ZIP SHA-256：`6e83e7ce3e0a76c4e8e78d98eb5ef538cbc9fb386c745bda425fc0bacb9de6d4`，已核对一致；`studio64.exe` 的 Google LLC Authenticode 签名有效。

检查发现旧的 AndroidStudio2026.1.1 配置和日志，但日志所指 `D:\tool\android` 的程序已不存在。未修改或删除旧配置。本次 IDE 配置、索引、插件、日志独立放在 `D:\tool\AndroidStudio` 下。

## 打开与编译

从仓库运行 `scripts/open-android-studio.ps1`，打开工程 `D:\Flie\Repository\AI-Story-Studio\android-native`。此脚本仅设置子进程环境，退出后恢复；未修改系统或用户的全局 PATH / JAVA_HOME。

- SDK：`D:\Flie\Repository\AI-Story-Studio\local-data\android-tools\sdk`，复用 Platform 36、Build Tools 36.0.0、Platform Tools 37.0.1 和已有许可证。
- Gradle：工程 Wrapper 8.14.3，复用 `local-data\android-tools\gradle-cache`，没有再装全局 Gradle。
- IDE 运行时：Android Studio 自带 JBR 25.0.3。
- 工程 Gradle JDK：复用 `local-data\android-tools\jdk\jdk-21.0.12.1+1`。自带 JBR 25 构建本项目失败，保留日志；JDK 21 构建通过。Gradle 运行时支持范围见[官方兼容表](https://docs.gradle.org/current/userguide/compatibility.html)。
- `local.properties` 指向已有 SDK，`.gradle/config.properties` 指向 JDK 21，`.idea/gradle.xml` 指定项目 JDK 和缓存；这些机器相关文件已被工程忽略规则排除。

首次出现 Trust Project 时由 Owner 确认当前工程，不需要信任整个父目录。不自动升级 AGP、Gradle 或 Kotlin。项目同步完成后右上角选择 `app`，选择已授权的 V2171A 手机，点击 Run。

命令行构建：`scripts/build-android.ps1 -Test`。交付 APK：`releases/android-native-preview/XY-Studio-Android-debug.apk`。

## 先看三个 Kotlin 文件

1. `app/src/main/java/cn/xiyi/xystudio/MainActivity.kt`：Compose 应用入口、连接、项目与素材页面；导航在 `StudioShell.kt`。
2. `app/src/main/java/cn/xiyi/xystudio/StudioViewModel.kt`：状态管理、连接恢复、项目业务调用和任务状态同步。
3. `app/src/main/java/cn/xiyi/xystudio/LanApi.kt`：HTTP、固定密码认证、Bearer 令牌、受限媒体地址与上传；WebSocket 监听在 `StudioViewModel.kt`。

随后可查看 `GenerationScreen.kt` 的生成参数确认、`CreationScreens.kt` 的任务与 Agent 界面，以及 `MediaDialog.kt` 的 Media3 视频播放。

## 中文界面与入门文档（2026-10-22）

已启用简体中文，使用 JetBrains 官方 IDEA 2026.2.1 档中的 `localization-zh` 插件（262.9437.185），未修改插件兼容声明。安装在 `D:\tool\AndroidStudio\plugins\localization-zh`，独立配置 `ide.general.xml` 的 selectedLocale 为 zh-CN。部分 Android 专用菜单仍为英文。

图文入口：[Android 中文学习手册](android-handbook/index.html)，含使用手册、14 个 Kotlin 文件的 Java 对照、源码快照和标准 Javadoc。使用同目录双击入口启动 IDE、编译或部署；不修改全局环境。

本次 IDE 重新同步于 21:20:27 成功，耗时 16.458 秒。Java 阅读模型编译和 11 项纯逻辑检查通过。ADB 当前未发现设备，本次未重新进行真机生成验收。此前验收记录保持原样并标明为历史。

## 最新客户端

当前 `1.2.1-native-preview.4` 已构建并覆盖安装到 iQOO 9。8 项单测、附件与资产操作真机测试、导航与视频播放回归通过。APK SHA-256：`5c4572d571872960fc0b7ad56f83202b8862bf2cfd375ea500c0435b07e197d8`，与手机一致。功能与未覆盖项见 [桌面功能对照](ANDROID-DESKTOP-PARITY.md)。先看 `StudioShell.kt`（导航）、`ChatAttachments.kt`（对话附件）和 `StudioViewModel.kt`（状态与 PC 交互）；生成表单在 `GenerationScreen.kt`。

## Android Studio 初次安装验证记录（历史）

- ADB 当前识别 `34387804570054R`，`V2171A / PD2171`，状态 device。
- JDK 21 下 `assembleDebug` 与 `testDebugUnitTest` 构建成功；4 项网络单测通过（增量构建复用已有结果）。
- APK SHA-256：`f8450b9c11def3df423f28e8e5291a783a2e911345f3ca536ed42dd0f4fdf641`；与已安装手机 base.apk 一致。
- 本次重复覆盖安装返回 `INSTALL_FAILED_ABORTED: User rejected permissions`，没有重装或绕过安装保护。之前已通过手机授权安装同一 APK；当前 `am start` 启动成功。
- Owner 确认 Trust Project 后，IDE Gradle Sync 于 2026-10-22 19:20:42 成功完成，耗时 4 分 34.682 秒。首次同步下载了依赖源码与文档；日志记录 `onSuccess`、`onImportFinished` 和 `Gradle sync finished`，见 `demo/evidence/android-studio-sync.txt`。
- IDE 已显示 `app` 运行配置和 `vivo V2171A` 手机，已打开并解析 `MainActivity.kt`。同步中的 SDK XML 版本警告未阻止成功；保留现有 AGP / Gradle / Kotlin 版本，没有执行 IDE 推荐的升级或迁移。

所有源码、Windows 预览包、APK、安装文件仅保存在本机，未上传 GitHub。
