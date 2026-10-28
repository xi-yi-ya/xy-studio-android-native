# XY Studio · Android Native + Windows LAN

Kotlin + Jetpack Compose 原生 Android 创作客户端，通过 HTTP / WebSocket 连接 Windows 上的 XY Studio Python 服务。PC 保留 Vue 3 / PySide6 桌面界面，复用同一套项目、Agent 和 ComfyUI 工作流。Android 不使用 WebView，也不保存 DeepSeek / Pixstag API Key。

这是个人毕业设计与 Vibe Coding 实践项目，当前版本为 **Android native preview.5 + Windows LAN / Pixstag 预览版**。功能仍在完善，后续更新没有固定计划。

## 下载与运行

在 [Releases](https://github.com/xi-yi-ya/xy-studio-android-native/releases) 下载：

- **XY-Studio-Android-debug.apk**：Android 8.0+ 原生 Debug APK。
- **XY-Studio-Windows-LAN-Pixstag-preview.zip**：Windows 桌面程序，完整解压后运行 `XY-Studio/XY-Studio.exe`，保留 `_internal`。
- **XY-Studio-Android-Handbook.zip**：中文使用手册与 Java 阅读文档，解压后打开 `docs/android-handbook/index.html`。
- **SHA256SUMS.txt**：各附件的 SHA-256 校验值。

PC 桌面点“手机连接”启动 LAN 服务；手机与 PC 在同一局域网，首次输入面板的地址和固定连接密码，之后自动连接。PC 登记的全部可访问项目显示在手机列表，切换项目会同步到另一端；素材按需读取，原文件留在 PC。

本地图片 / 视频生成需要你自行准备 ComfyUI、节点与模型。Pixstag 云端视频在 PC 设置中填写自己的 Key，再在生成视频中切换来源；确认提交可能消耗平台积分，参考素材会上传至该平台。作者不提供共享密钥或免费额度。

## 当前功能

- 项目、角色、场景、分镜、图片库 / 视频库、素材导入、回收站和预览。
- 原生图片 / 视频生成表单、参考图 / 视频选择、参数确认、PC 队列、真实阶段或节点进度、历史记录、Media3 视频播放。
- DeepSeek 全屏 AI 对话、素材引用、PC 项目上下文、Skill 加载及原有操作审阅。
- Pixstag V2：H3、Seedance 2 / 2.5；文生视频、图生视频、首尾帧和多模态参考；查询、结果下载入库与任务 ID 恢复。
- 密钥保存在 PC Windows 凭据管理器。LAN 使用认证和项目路径约束；不会把 ComfyUI 8188 直接暴露成手机业务接口。

AI 附件目前提供文字和素材引用，不能据此声称模型读取了视频画面 / 音轨。Pixstag 没有已提交任务取消接口或整体百分比，停止本机查询不会停止云端计费。

## 文档与 Java 阅读入口

- [中文学习入口](docs/android-handbook/index.html) / [Android Studio 使用手册](docs/android-handbook/manual.html)：下载后离线打开 HTML，GitHub 文件页面显示源码。
- [Java 思路与文件地图](docs/android-handbook/java-guide.html) / [可编译 Java 教学模型](docs/android-handbook/java-src/StudioJavaGuide.java) / [Javadoc](docs/android-handbook/javadoc/index.html)。Java 文件用于解释 Kotlin 职责和调用链，不替换生产应用。
- [Android 安装连接](docs/ANDROID-NATIVE.md)、[Pixstag 用法与边界](docs/PIXSTAG-VIDEO.md)、[验收清单](docs/ANDROID-ACCEPTANCE.md)、[演示录制顺序](demo/README.md)。
- [2026-10-28 公开交付记录](docs/PUBLIC-RELEASE-20261028.md)：实际测试与未验证项、发布范围。

建议先看 `StudioViewModel.kt`（业务调度）、`GenerationScreen.kt`（生成表单）和 `LanApi.kt`（网络层），再跟到 PC 的 `studio/service.py`、`workflows.py` / `pixstag.py`。

## 构建

Android Studio 打开 **android-native/**。已验证 JDK 21、SDK Platform 36 / Build Tools 36.0.0、Gradle Wrapper 8.14.3、AGP 8.13.0、Kotlin 2.3.0。新电脑使用自己的 SDK / JDK 路径，不要照抄文档里的本机绝对路径。

```powershell
.\scripts\build-android.ps1 -JavaHome '你的JDK21目录' -SdkRoot '你的AndroidSDK目录' -Test
.\scripts\deploy-android.ps1 -Adb '你的AndroidSDK目录\platform-tools\adb.exe'
```

APK 输出 `releases/android-native-preview/XY-Studio-Android-debug.apk`。不要清除手机数据；覆盖安装时在手机系统提示中允许。

PC 使用 Python 3.12，安装 `requirements.txt` 和 `requirements-lan.txt`；执行 `npm --prefix frontend ci`、`npm --prefix frontend run build` 后运行 `python main.py`。独立 LAN 启动脚本是 `scripts/start-lan.ps1`，桌面包构建是 `scripts/build-lan-preview.ps1`。

本次历史测试：181 项 Python、10 项 Android 单测通过；模拟器真实连接 PC，完成云端参数 / 参考素材 / 暂停队列与既有视频播放回归。**Owner 选择不消耗积分，本次没有真实付费 Pixstag 视频生成成功记录**。本次未重新完成实体手机 Wi-Fi 验收；此前 iQOO 9 本地 ComfyUI 验收与新云端验收分开记录。

## 源码与发布范围

`android-native/` 是交付的原生客户端；`studio/`、`frontend/` 是 PC 业务和桌面界面；`tests/`、`scripts/` 为测试和构建；`docs/` 为使用与开发文档。`mobile/` 是停止维护的 Capacitor 试作，仅留开发记录，不是本次 APK。

此仓库起初为私人归档，现经作者授权公开；保留原始历史，原桌面仓库仍位于 [ai-story-studio](https://github.com/xi-yi-ya/ai-story-studio)。没有上传用户项目、生成素材、密钥、连接密码、签名私钥、SDK/JDK、Android Studio 安装器或含个人内容的原始运行日志 / 测试截图。历史文档中的“仅本地 / 未上传”描述对应当时状态。

原创代码使用 [0BSD](LICENSE)。第三方组件、ComfyUI、模型与素材保持各自许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。
