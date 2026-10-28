# 第三方组件与素材

XY Studio 的 0BSD 许可适用于本项目原创代码，不替代第三方组件和内容的许可。

- Python、PySide6 / Qt / Qt WebEngine（包含 Chromium）、Requests、websocket-client、keyring、Pillow、PyAV / FFmpeg 及其依赖保持各自原有许可。Windows 公开包附带从安装环境收集的第三方许可与包元数据，位于 `THIRD_PARTY_LICENSES`。
- PySide6 包元数据列明 LGPL-3.0-only / GPL 可选许可；本项目采用适用的 LGPL 路径使用动态库。用户可以依其许可替换相应库、调试其修改。项目不对这种修改或调试施加额外限制。构建脚本公开在 `scripts/build.ps1`。
- Qt/PySide 源码与许可：[Qt for Python](https://code.qt.io/cgit/pyside/pyside-setup.git/)、[Qt](https://code.qt.io/cgit/)、[Qt WebEngine](https://code.qt.io/cgit/qt/qtwebengine.git/)。发布包元数据记录具体组件版本；再分发时应遵守所用组件的源代码和通知义务。Qt 中文翻译资源 `studio/assets/qtbase_zh_CN.qm` 同样属于 Qt 第三方资源。
- Vue、Pinia、Reka UI、Lucide、Tailwind、Vite 及前端构建依赖保留各自许可；前端依赖版本见 `frontend/package-lock.json`。
- ComfyUI 和作者提供的夸克配套包为外部运行环境，未包含在本仓库或 Studio 下载包中。模型、LoRA、插件等遵循各自许可，不能把 Studio 的 0BSD 解释为对它们的重新授权。
- 内置提示词指南是项目中用于模型提示词编写的资料，不包含模型权重，不代表与模型提供方存在官方关系。
- UI 截图和原型参考图用于展示与测试；其中的第三方角色、商标、模型生成结果等不因本项目许可获得额外权利。

0BSD 原文与识别信息：[OSI](https://opensource.org/license/0bsd)、[SPDX](https://spdx.org/licenses/0BSD.html)。

## Android / LAN / 云端适配

- Kotlin、AndroidX / Jetpack Compose / Media3、OkHttp、Coil 与 Gradle 保留其各自许可；具体版本见 android-native/ 的 Gradle 文件，分发的 APK 不包含签名私钥。AndroidX / Kotlin / OkHttp 等组件采用 Apache-2.0 等原许可，不能改为本项目的 0BSD。
- LAN 服务使用 aiohttp 及相关依赖，版本与许可以 requirements-lan.txt 和发行包 THIRD_PARTY_LICENSES 中元数据为准。
- Pixstag、DeepSeek 为外部服务，按各平台条款和账户规则使用；不随本项目分发账户、API Key 或额度。
