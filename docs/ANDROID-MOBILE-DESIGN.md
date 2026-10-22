# 原生移动创作界面 · preview.3

2026-10-22，当前本地 APK：`1.2.1-native-preview.3`。本轮优化 Kotlin / Jetpack Compose 页面，没有改变 Python 工作流、项目格式或桌面业务。代码和安装包均未上传 GitHub。

## 界面与导航

- 背景 `#F8F9FB`，主色 `#168F98`，正文 `#20252B`；白色轻边框卡片、青蓝进度与柔和红色错误提示。
- 底部四栏：**首页 / 创作 / 素材 / 任务**。首页展示真实当前项目、角色/场景/分镜数量、图片/视频生成入口和最近作品；有进行中任务时才展示真实进度。
- 首页「切换」进入项目列表；「进入项目」进入创作页。创作页保留角色资产、场景资产和分镜工作区。
- 素材页分图片库与视频库，保留预览、搜索、导入、选用和图片制作视频；任务页保留真实状态及历史记录。
- AI 助手在创作页右下角，点击进入全屏对话，返回恢复原页面。对话设置默认折叠，输入草稿在本次应用进程内保留；空会话提供只填入输入框、不自动发送的创作建议。
- 连接入口收在顶部状态按钮中。手机仍自动连接此前保存的 PC 地址与固定密码。

## 实际验证

设备：iQOO 9 / V2171A，Android 15，ADB `device`。PC 使用既有独立验收项目，通过 `192.168.50.198:8767` 提供真实数据。

| 检查 | 结果与边界 |
|---|---|
| Debug APK、设备测试包 | Gradle 构建成功；APK v2 签名验证通过 |
| 单元测试 | 8 项通过，0 失败；网络边界与生成输入规则 |
| USB 部署 | 主应用与测试包覆盖安装成功，ADB 启动成功；没有清除应用数据 |
| 真机导航回归 | `NativeNavigationTest`：`OK (1 test)`，18.996 秒 |
| 真实数据 | 读取真实项目名、素材与历史任务；测试前后任务 ID 集合一致 |
| 页面交互 | 四栏切换、项目列表、角色/场景/分镜入口、AI 全屏与返回、设置展开/收起、草稿保留通过 |
| 生成表单 | 图片/视频表单打开、关闭确认和继续编辑通过；本轮未提交新的生成任务 |
| 视频播放 | 打开 PC 上已有真实视频，Media3 播放位置超过 1 秒 |
| 视觉检查 | 查看首页、素材卡片、AI 对话与键盘展开截图；输入框、发送和返回入口可见 |
| 日志 | 最终可获取的应用 logcat 中未发现 FATAL EXCEPTION、SocketTimeoutException 或 ExoPlaybackException；环形日志不代表全量历史 |

交付与手机已安装 APK SHA-256 相同：

```text
8f481b01ac8b79d7e1e0566f3830a32e0837f5c2473d45023bce44a2a8bb0911
```

APK：`releases/android-native-preview/XY-Studio-Android-debug.apk`。

首轮测试因原 8767 服务未运行而连接超时；保留失败记录，恢复该独立项目服务后两次回归通过。没有更换当前桌面项目或强制停止其他服务。当前 8767 是本地 QA 后台服务；日常连接自己的项目请使用 Studio「手机连接」面板共享，选择空闲端口并更新手机地址，勿启动第二个进程写同一项目。

## 证据与未覆盖项

证据目录：`demo/evidence/android-design-20261022/`。

- `device-navigation.txt`：最终真机测试结果；`device-navigation-first-pass.txt`：第一次恢复服务后的成功记录；`device-service-unavailable.txt`：首次连接超时。
- `build-final.txt`、`TEST-*.xml`、`apk-verification.txt`、`logcat-final.txt`：构建、单测、安装包一致性和可获取日志。
- `screenshots/01-home.png` 至 `12-projects.png`：真实设备页面；`keyboard-settled.png`：键盘动画完成后复核。自动化键盘截图可能处于输入法过渡帧，以后者判断稳定布局。截图中已有会话和素材为项目真实内容，不是本轮生成记录。

本轮没有重新调用 GPU 或 DeepSeek API；此前图片/视频端到端生成记录保留在 [preview.2 生成验收](ANDROID-GENERATION-UX.md)。未验证新首页在真实运行任务中的进度展示、横屏/平板、超大字体、大素材库、长视频或所有工作流。本轮不修改 Python 与桌面实现，未重跑桌面回归套件。

## 源码与回滚

主要入口：`StudioTheme.kt`（配色、卡片、图标），`StudioShell.kt`（首页与导航），`CreationScreens.kt`（任务与 AI），`GenerationScreen.kt`（生成表单）。

修改前源码保存在 `local-data/android-design-backup-20261022-201446/`；构建脚本保留旧 APK 的时间戳 `.bak`。回滚时仅恢复这些 UI 源码并重建覆盖安装；不删除项目、素材或手机应用数据。若恢复旧 APK 受版本降级限制，应重建兼容版本号，不通过卸载清数据解决。
