# XY Studio Android 原生预览版

本次最终 Android 工程是 `android-native/`：Kotlin + Jetpack Compose + OkHttp + Media3。
不包含 WebView、Vue 页面或 Capacitor 运行时。`mobile/` 和 Vue LAN 适配是需求变更前保留的试作，不是交付客户端。

当前本地 APK 为 `1.2.1-native-preview.5-pixstag`：新增 PC 统一调用的 Pixstag 云端视频入口、模型 / 清晰度选择、图片与视频参考、任务阶段和恢复查询，详见 [Pixstag 视频使用说明](PIXSTAG-VIDEO.md)。原有对话附件、资产、分镜和回收站保留。历史说明见 [桌面功能对照](ANDROID-DESKTOP-PARITY.md)、[移动界面验收](ANDROID-MOBILE-DESIGN.md)、[原生生成体验](ANDROID-GENERATION-UX.md)。

## 启动 PC

1. 双击仓库根目录的 `启动XYStudio.cmd`，它会打开 `releases/v1.2.1-lan-preview-20261026-pixstag/XY-Studio/XY-Studio.exe`。也可安装 `requirements.txt` 后运行 `main.py`。旧版 EXE 不会自动升级；新预览包独立保存。
2. 使用本地生成时启动已有 ComfyUI，确认 PC 的 `http://127.0.0.1:8188` 可访问。模型和工作流由原 Studio Python 业务处理。使用 Pixstag 云端视频只需 PC 联网并在桌面配置 Pixstag Key，无需启动 ComfyUI。
3. 在 Studio 侧栏下方点击 **手机连接**，选择本机局域网 IPv4 和空闲端口，再点击 **启动局域网服务并自动同步**。PC 与手机共用正在运行的 Studio 实例。关闭面板不会停止服务；面板内可单独停止服务，退出 Studio 则停止服务。
4. 服务开启后，手机可浏览 Studio 已登记的全部可访问项目（已有最近项目 + 持久项目索引）。PC 打开或新建项目会自动加入列表；两端切换当前项目会同步跟随，无需再点共享。手机打开列表中的项目也会切换 PC 的当前项目。素材仍在原 PC 目录，按需读取，不复制或迁移项目。未曾登记的旧项目在 PC 打开一次即可加入；不会扫描整个硬盘。固定密码保存在 Windows 凭据库，不随重启改变。
5. API Key 和 ComfyUI 地址仍在 PC 设置中配置。手机不接收或保存 DeepSeek Key。端口被旧测试服务占用时可选择其他端口；不要重复打开同一项目的独立实例。

独立 LAN 启动脚本仍保留，便于排查或无工作台启动：

   ```powershell
   .\scripts\start-lan.ps1
   # 多网卡时明确指定 Wi-Fi IPv4：
   .\scripts\start-lan.ps1 -Bind 192.168.50.198 -Port 8765
   ```

独立模式在服务窗口点击“授权并打开已有项目”选择 `project.json`，可再点击“打开共用桌面工作台”。该模式关闭服务窗口会停止服务，和内置面板的隐藏行为不同。原进程锁仍阻止多个独立实例争写同一项目。

服务默认绑定明确的私有 IPv4；不绑定 `0.0.0.0`，不开放 ComfyUI 端口，不修改路由器或 Windows 防火墙规则。如 Windows 弹出防火墙对话框，仅允许可信的**专用网络**。如果手机连不上，先核对 IP、同网段、访客网络隔离和防火墙；不要为调试关闭整个防火墙。

## 安装和连接手机

- 安装 `releases/android-native-preview/XY-Studio-Android-debug.apk`，需要 Android 8.0 / API 26 或更高版本。这是本地 Debug APK，未公开发布。
- 同一 Wi-Fi 下首次输入 PC 服务地址、窗口中的固定 12 位连接密码和设备名称。**没有一次性授权码**。
- 手机使用 Android Keystore / AES-GCM 加密保存连接密码，重新打开应用自动连接。PC 密码使用系统凭据库保存。密码连续错误 10 次会暂停验证 5 分钟。
- 访问令牌在内存中有效 8 小时；会话过期或服务重启时手机用保存的密码重新授权。PC 点击“更换连接密码并撤销全部设备”后旧密码和令牌均失效，手机需要输入新密码。手机“断开并清除授权”仅删除本应用保存的 LAN 连接信息。
- 项目页只显示 PC 已授权项目。手机新建项目会由 PC 在指定项目目录中创建唯一的新文件夹；不接收手机传入的 PC 路径。
- 断线自动重连恢复最新状态，不自动重交生成。若提交时超时，先重连并检查“任务”，确认没有同一任务后再决定是否提交。

这是可信局域网的 HTTP/WebSocket 方案，配对和授权不能防止同网段恶意监听或中间人攻击。勿在公共 Wi-Fi 使用、勿配置公网转发。需要不可信网络时，应另行增加 TLS 证书配对，而不是开放当前服务。

2026-10-23 已在 iQOO 9 验证桌面内置服务 `http://192.168.50.198:8765`：全部已登记项目列表、PC 打开项目后的自动跟随、手机切换后 PC 跟随、素材刷新和现有视频播放。此前 `8767` 是独立 QA 服务的历史地址。日常以当前 Studio「手机连接」面板显示的地址为准，无需逐个共享项目；勿重复启动进程写同一项目。记录见 [自动同步验收](../demo/evidence/project-sync-20261023/README.md)。

## USB 部署与真实测试

```powershell
# 构建、保留已有手机数据并覆盖安装，然后启动原生 Activity
.\scripts\deploy-android.ps1 -Build
# 只部署已构建 APK
.\scripts\deploy-android.ps1
```

脚本先执行 `adb devices -l`，只接受 `device` 状态，再执行 `adb install --no-streaming -r` 和 `am start`，最后读取本应用 logcat。iQOO 如出现安装验证，需在手机手动允许；脚本不会修改手机安全设置、清除数据或卸载应用。`--no-streaming` 是标准 ADB 安装方式，本机验证比流式安装稳定。

设备测试包位于 `android-native/app/build/outputs/apk/androidTest/debug/`。`deploy-android.ps1 -Build -LanReadyFile <本地QA文件> -Generate` 显式启用真实 GPU 生成，必须使用专门的验收项目。LAN 服务的 `--ready-file` 仅供本地自动化，包含连接密码，不应分享或打进交付包；普通启动脚本不会生成该文件。真机测试先启动主应用再运行 Instrumentation，避免本机系统后台启动限制。

本轮准确通过项与未测项见 `docs/ANDROID-ACCEPTANCE.md`，不要把构建通过当作所有桌面功能都已通过真机验收。

## 日常流程

1. 首页「切换」选择项目，进入「创作」查看角色 / 场景 / 分镜；底部「素材」查看 PC 图片库 / 视频库。图片支持双指缩放，视频使用原生 Media3 播放原文件。
2. “生成图片”打开原生参数确认页。模式和参数目录来自 PC；手机不编译 ComfyUI 工作流。可选择 Qwen、编辑、Krea、四视图或放大等已有模式。
3. “生成视频”选择 H3 模式、提示词、分辨率、秒数与有序参考图，确认后交给 PC 队列。参考图来自 PC 图片库，手机导入的素材也会上传保存到 PC。
4. “任务”显示后端真实阶段、节点和步数。节点百分比不代表总任务百分比；没有测量值时仅显示忙碌状态。完成后查看图片或播放视频。
5. 结果进入原有图片库 / 视频库。在素材卡片“选用”中添加为角色、场景或使用到分镜；不会自动覆盖原有资产。
6. 创作页右下角「AI 助手」进入全屏对话；「对话设置」选择模型、设置联网。素材卡片可“给 AI”，角色/分镜也可发送引用。Skill 加载与工具审阅仍由 PC 的原逻辑执行；生成建议先确认参数，再加入队列。

PC 与手机是**共享工作台会话**：当前项目、选中条目和 AI 引用也共享。所有写入都在 PC Qt 主线程串行执行，JSON 继续原子落盘。故事与资产编辑带文档版本校验；发生冲突会拒绝，不会静默覆盖。此预览版不是多人独立会话协作系统。

## 从源码构建

已在项目 `local-data/android-tools/` 隔离配置 JDK 21 和 Android SDK，没有修改全局 `JAVA_HOME` / `PATH`。

```powershell
.\scripts\build-android.ps1 -Test
# 其他机器可以指定已有工具：
.\scripts\build-android.ps1 -JavaHome 'D:\Tools\jdk-21' -SdkRoot 'D:\Tools\android-sdk' -Test
```

需要 SDK Platform 36、Build Tools 36.0.0。Gradle Wrapper 使用 8.14.3，Android Gradle Plugin 8.13.0，Kotlin 2.3.0，Compose BOM 2025.10.01。构建脚本只为当前进程设置环境，重复交付前备份旧 APK。

直接 Maven Central 在本环境返回 HTTP 403，因此本工程增加 Google 托管的 Maven Central 镜像；Google Android 依赖仍从 Google Maven 获取。没有全局修改 Gradle 仓库。参考：[Kotlin/Gradle 兼容表](https://kotlinlang.org/docs/gradle-configure-project.html)、[Compose BOM](https://developer.android.com/develop/ui/compose/bom)、[Media3 原生播放](https://developer.android.com/media/media3/exoplayer/hello-world)。

## 代码入口与兼容边界

| 位置 | 用途 |
|---|---|
| `android-native/app/src/main/java/cn/xiyi/xystudio/` | 原生页面、ViewModel、LAN 网络层、Media3 播放 |
| `studio/lan/host.py` | 授权项目、命令白名单、Qt 线程转发、编辑版本检查 |
| `studio/lan/server.py` | HTTP、WebSocket、配对、受限媒体、上传 |
| `studio/lan/desktop_control.py` | 桌面“手机连接”面板与服务启动/停止；共用当前业务实例 |
| `studio/service.py` | 原有业务权威：生成、队列、Agent、审阅、存储；本次未重写 |
| `scripts/start-lan.ps1` | Windows LAN 服务入口 |
| `tests/test_lan.py` | 临时测试项目上的通信和权限自动化测试 |
| `scripts/test_lan_live.py` | 显式运行真实 ComfyUI 的 PC 联调；会新建验收项目并使用 GPU |
| `android-native/app/src/androidTest/` | 显式传入 PC 地址 / 连接密码的原生设备测试 |
| `demo/` | 录屏流程与真实证据 |

原项目 schema=1、ID、目录与工作流保持原样。新增预览数据字段仅出现在 LAN 返回值中。API 禁止任意 PC 路径、任意文件下载、密钥变更、桌面退出和离线 Agent 文件导入。媒体链接只能读取已授权项目的图片或视频，并随会话撤销和项目切换失效。

回滚：关闭 LAN 服务；保留此轮新增的项目和生成素材；使用原 `main.py` 或原发布版 EXE。不要删除用户项目来“回滚”。未提交的编辑器配置保持原状，本轮没有 Push、Release 或公开发布。
