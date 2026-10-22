# XY Studio Android Native

Kotlin + Jetpack Compose 原生 Android 客户端，通过局域网控制 Windows 上的 XY Studio / ComfyUI。此仓库为 Owner 授权创建的**私有开发归档**，基于 XY Studio v1.2.1 的当前本地工作副本；未修改原仓库的远端或推送其历史。

手机负责界面与交互，PC 是唯一项目数据源，并负责模型推理、素材保存和 DeepSeek 调用。Android 不保存 DeepSeek API Key，没有 WebView 包装 Vue。

## 先阅读

- [中文学习入口](docs/android-handbook/index.html)：下载仓库后双击此 HTML 离线阅读，GitHub 页面只显示源码。
- [Android Studio 使用手册](docs/android-handbook/manual.html)：打开工程、编译、USB 安装、图片与视频、AI 附件操作。
- [Java 对照源码文档](docs/android-handbook/java-guide.html)：全部 14 个生产 Kotlin 文件与业务调用链。
- [可编译的 Java 阅读模型](docs/android-handbook/java-src/StudioJavaGuide.java) / [Javadoc](docs/android-handbook/javadoc/index.html)：帮助理解，不替换生产 Kotlin 应用。
- [Android 安装与连接](docs/ANDROID-NATIVE.md)、[功能与真机验收记录](docs/ANDROID-DESKTOP-PARITY.md)、[演示方案](demo/README.md)。

## 目录

| 目录 | 内容 |
| --- | --- |
| `android-native/` | Kotlin / Compose 工程、Gradle Wrapper、单元和真机测试 |
| `studio/lan/` | Python LAN API、授权、媒体访问和桌面业务适配 |
| `studio/`、`frontend/` | 原 PC 业务与 Vue 桌面界面，用于复用工作流和“手机连接”入口 |
| `docs/android-handbook/` | 中文手册、Java 对照、离线源码快照 |
| `scripts/` | 构建、部署、IDE 启动和 LAN 启动脚本 |
| `tests/` | PC 业务与 LAN 自动化测试 |

## 开发环境

当前已验证环境：JDK 21、Android SDK Platform 36、Build Tools 36.0.0、Gradle Wrapper 8.14.3、AGP 8.13.0、Kotlin 2.3.0。

Android Studio 打开 **android-native** 目录。新电脑需自行安装 SDK / JDK，并在 IDE 选择 JDK 21；不要把作者电脑的绝对路径照抄到另一台电脑。SDK、JDK、Gradle 缓存和 local.properties 不在仓库内。

Windows 构建（仓库根目录 PowerShell）：

```powershell
.\scripts\build-android.ps1 -JavaHome '你的JDK21目录' -SdkRoot '你的AndroidSDK目录' -Test
```

APK 输出：`releases/android-native-preview/XY-Studio-Android-debug.apk`。已构建 Debug APK 通过此私有仓库的 Release 附件归档，不把大文件或 debug 签名私钥提交进源码历史。

手机连接 USB 后，在手机允许调试与系统安装：

```powershell
.\scripts\deploy-android.ps1 -Adb '你的AndroidSDK目录\platform-tools\adb.exe'
```

PC 使用 Python 环境安装 `requirements.txt` 和 `requirements-lan.txt`，按 [Android 安装与连接说明](docs/ANDROID-NATIVE.md) 启动桌面或 LAN 服务。ComfyUI、模型和用户项目需在 PC 单独准备，仓库不携带它们。

## 当前功能与边界

- 局域网固定密码认证、真实项目/素材、图片与视频生成表单、真实任务状态、原生视频播放。
- 角色/场景/分镜管理、素材回收站、AI 全屏对话、图片视频引用、手机文件导入与原有操作审阅。
- 当前 Agent 接收文字和素材引用，不直接接收图像像素或视频音轨；“可加视频附件”不等于“视频理解”。
- 不承诺桌面全部功能已逐项真机验收，详细通过项、历史失败与未覆盖项见验收记录。

## 本次归档验证

IDE 已启用官方中文语言资源并成功同步；Java 阅读模型编译及 11 项纯逻辑检查通过；50 个 HTML 文件的本地链接检查通过，桌面与手机宽度无横向溢出。客户端构建结果见 `docs/android-handbook/verification.json`。

本轮文档制作时 ADB 无设备，没有重新提交 ComfyUI 生成任务。之前的真实手机验收明确记为历史记录。完整运行日志和含个人素材的截图只保留原电脑，未放进本仓库；保留不含凭证的汇总。

## 归档范围

不含本机密码/令牌/API Key、用户项目与生成素材、SDK/JDK、Android Studio 安装包、构建缓存、签名私钥，以及停止维护的 Capacitor 客户端。文档中的绝对路径是 Owner 本机操作说明。原有 PC 源码许可保留，第三方说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
