# Pixstag 云端视频生成（桌面 / Android 原生）

接口依据：[Pixstag V2 官方文档](https://pixstag.com/docs/api)，核对日期 2026-10-26。新增云端路径由 PC 的 Python 后端统一执行，Android 仍是 Kotlin / Jetpack Compose 原生界面。

## 启动与配置

1. 打开本地新版 `releases/v1.2.1-lan-preview-20261026-pixstag/XY-Studio/XY-Studio.exe`。根目录 `启动XYStudio.cmd` 指向这个新版；旧包独立保留。
2. 在桌面「设置 → Pixstag 视频 API」填写自己的 API Key 并保存。留空会保留原密钥，密钥保存在 Windows 凭据管理器，不写入项目、任务 JSON、APK 或 LAN 返回值。
3. 「检测连接与积分（不生成）」仅调用账户查询。该按钮不提交视频任务。每台 PC 都需要使用自己的凭据；本仓库和安装包不包含作者的密钥。
4. 手机继续连接 PC 的「手机连接」服务，PC 提供项目与素材。API 路径不要求启动 ComfyUI；图片及本地视频生成仍使用已有 ComfyUI 路径。

## 两端操作

桌面顶部或 Android 首页 / 创作页打开「生成视频」，将「生成来源」切换为 **Pixstag 云端 API**。

- 模型：MiniMax-H3、doubao-seedance-2、doubao-seedance-2-5。
- 模式：文生视频、图生视频、首尾帧、多模态参考视频。首尾帧按第一张 / 第二张图片对应；多模态可选项目图片和 MP4 视频。
- 时长：4–30 的整数秒。清晰度：720P、768P、1080P、2K。比例支持 adaptive 及 API 列出的比例。具体模型与规格组合仍以平台校验及实际输出为准。
- 云端不提供本地采样步数、种子或 LoRA 控制，界面会隐藏这些参数。
- 参考图片原生支持 PNG / JPG；WebP 和超出 3 MB 的图片会转换、压缩内存副本上传，原项目文件保留。MP4 参考视频每个最多 5 MB，超出时须先裁剪或压缩副本。
- 当前客户端多模态上限为 9 张图片、3 个视频；这是客户端限制。音频参考尚未接入原生 / 桌面选择器。

Android 点「下一步 · 确认生成」，核对 PC 返回的模型、清晰度、秒数、素材数量及转换提示。桌面在参数审阅窗口直接核对这些设置。最后按钮明确标注 **确认调用 Pixstag（可能扣费）**。确认后由 PC 上传提示词和所选参考素材至 Pixstag。

默认关闭 AIGC 水印、开启 Context-IR、请求返回尾帧。当前自动入库的是 MP4 视频；尚未将平台返回的封面 / 尾帧另存为项目图片。

## 任务、下载与恢复

- 任务页显示实际 queued / running / succeeded / failed / cancelled 等平台阶段。API 未提供总体百分比，界面使用忙碌指示，不估算假进度。
- 成功后 PC 下载视频至当前项目 `outputs/<Studio任务ID>/pixstag-video.mp4`。下载完整并验证 MP4 后才标记完成；两端从原有视频库预览和选用到分镜。
- 平台任务 ID 会先落盘。断线、退出或下载失败后，点击「恢复查询」只查已有 ID、重试下载，不新建付费任务。
- 提交 POST 不自动重试。若提交超时且没有取得任务 ID，状态为未知，须到 Pixstag 核对；不要重复提交。本轮尚无手动绑定平台任务 ID 的界面。
- 本地尚未提交的任务可以取消。API 文档未提供已提交任务的取消接口；「停止本机查询（云端继续）」只停止本机轮询，不能停止云端生成或计费，之后可以恢复查询。
- 暂停后续队列会阻止新的 API 提交，不等于停止已提交的云端任务。

## 本轮验收与边界

2026-10-26 原始结果及截图仅留作者本机。2026-10-28 经授权公开代码与安装包，脱敏汇总见 `demo/evidence/public-summary-20261028/`；以下仍是原验收范围。

- Python：181 项全量测试通过，覆盖既有 ComfyUI 及项目功能；新增合同测试使用明确的固定响应夹具，不属于真实云端生成。
- Android：10 项单测通过；Debug APK 和设备测试包已构建并安装至 Android Studio 已有的 Pixel_10_Pro_XL 模拟器。
- 真实 API：已调用账户查询并验证可用，没有把此结果称为真实视频生成。
- 桌面：已操作云端参数页，将任务加入经过核对的暂停队列，再取消；未取得平台任务 ID、未发起付费提交。
- 模拟器的最终界面回归结果见同目录验收记录。模拟器通过 `10.0.2.2` 访问 PC，不能替代实体手机 Wi-Fi 验收。

首次模拟器自动化因 Compose 间接依赖的旧 Espresso 不兼容 API 37 而失败；固定测试依赖至稳定版 3.7.0（[AndroidX 官方说明](https://developer.android.com/jetpack/androidx/releases/test)）。Google Maven 的 Gradle TLS 握手失败时，使用从官方来源下载并核对官方 SHA-1 的项目本地副本，没有关闭 TLS 校验。仅测试依赖变化，不改变应用运行时依赖。

## 构建与代码入口

- PC 适配器：`studio/pixstag.py`，负责请求、轮询、下载和恢复日志；`studio/service.py` 决定任务走本地还是云端。
- 桌面：`frontend/src/components/GenerationForm.vue`、`SettingsPanel.vue`、`TaskProgress.vue`。
- Android：`GenerationScreen.kt`、`GenerationRules.kt`、`CreationScreens.kt`，请求仍通过 `StudioViewModel` / `LanApi` 发给 PC。
- 构建：`scripts/build-android.ps1 -Test -DeviceTests`；Windows 用 `scripts/build-lan-preview.ps1`，每次使用新的 Label。
- APK：`releases/android-native-preview/XY-Studio-Android-debug.apk`，版本 `1.2.1-native-preview.5-pixstag`。覆盖安装会保留原应用数据。

回滚时先正常退出新版，再启动保留的旧版 PC 包；若需 Android 回滚，使用构建脚本保存的旧 APK 备份。项目格式仍为 schema 1，未迁移或删除项目和素材。旧客户端无法编辑新的 Pixstag 参数，应使用新版继续查看 / 恢复这类任务。
