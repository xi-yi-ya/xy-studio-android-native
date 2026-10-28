# XY Studio v0.3.0 Vue 正式迁移

## 架构决定

正式界面使用已验收的 Vue 3 原型设计。QWebEngineView 只承载构建后的网页，QWebChannel 只传递有类型的命令、回应和状态事件。Python 进程内服务继续调用既有 storage / workflows / comfy / deepseek / skill_library / research 模块；不重写模型工作流、Agent 工具和项目格式。

评估了 Tauri 2 + Python sidecar：需要额外 Rust 工具链、桌面 IPC 层、Python 子进程监督与本地 API 服务。当前环境已具备 PySide6 6.12 WebEngine/WebChannel，直接复用已有依赖可以减少生命周期边界和维护层级，因此本轮选择 Qt Web 容器。原 Qt Widgets 页面不作为正式入口，但源码和 v0.2.0 发布包保留。

参考：[Tauri 前置依赖](https://v2.tauri.app/start/prerequisites/)、[Tauri sidecar](https://v2.tauri.app/develop/sidecar/)、[Qt WebChannel](https://doc.qt.io/qtforpython-6/PySide6/QtWebChannel/QWebChannel.html)。

## 阶段

1. 从旧控制层提取项目、队列和审阅协调服务，验证 schema=1、ID、journal、凭据和配置兼容。
2. 在独立 `frontend/` 接入真实状态与命令，保留原型布局。没有 Bridge 时明确报错，不使用 Mock 回退。
3. 接通完整参数、参考图顺序、历史、文件导入、设置、模型列表、Agent 和 Skill/搜索记录。
4. 使用独立测试项目执行实际 ComfyUI 和 DeepSeek 验证，GPU 测试保持低分辨率和短时长。
5. Windows 新版本独立打包，验证启动、关闭、任务恢复和子进程清理。ComfyUI 保持独立运行。

## 接口及安全边界

命令请求包含 request id、command、payload；服务返回匹配 id 的 result/error。Python 主线程持有项目，网络线程只操作快照，结果按 project/target/job ID 回写。QWebChannel 不开放任意脚本或文件路径执行。

Agent 工具先形成服务端待审阅操作，再由 Vue 确认或取消；目标解析复用 resolve_target。生成确认前不提交 ComfyUI，取消/失败阻止后续自动执行。

媒体服务只监听 loopback 随机端口，提供受随机会话标识保护的当前项目媒体及静态前端，支持视频 Range；不提供目录浏览、凭据或业务 HTTP API。关闭应用结束服务线程和渲染进程，未完成 ComfyUI 任务保留 prompt_id 用于恢复，不终止 ComfyUI 进程。

## 回退

`releases/v0.2.0/XY-Studio/XY-Studio.exe` 和 Git 标签 `v0.2.0` 保持可用。原型保留于 `prototypes/vue-workbench/`。真实生成测试和界面测试只使用 `local-data/` 下独立项目，不覆盖用户项目。

## 功能交付与接口

| 范围 | 正式 Vue 功能 / 后端接口 |
| --- | --- |
| 项目 | 新建文件夹、打开 project.json、保存故事、最近项目、打开目录；project.* |
| 角色 / 场景 | 新建、编辑、导入、右键、删除、历史选择、双击缩放；asset.* / version.use |
| 分镜 | 连续编号、自定义名称、角色场景关联、实际参考图、图片 / 视频及原卡片历史、折叠、时间轴定位 |
| 生成 | 九种批准模式；图片比例 / MP、64 位种子、步数、H3 秒数及实际帧数、LoRA 开关 / 强度、放大倍数；generation.* |
| 任务 | 串行队列、暂停、节点进度 / 阶段、定向取消、恢复原 prompt_id、结果文件与完整参数、审阅后再次生成；task.* / queue.toggle |
| AI | 真实模型选择、联网开关、当前及固定素材上下文、长回复展开、定位提问、工具结果、逐项中文审阅、创建后续办、离线建议导入 |
| Skill | 原 read_skill / 检索实现保留，按需加载，读取及来源记录显示在对应回复；不追加新的 Agent 权限 |
| 设置 | 原 ComfyUI 地址、DeepSeek 模型缓存和 Windows 凭据管理器 Key；settings.save / models.refresh |

响应匹配 request id；状态事件包含 real project/tasks/review。服务持有待审阅参数和目标 ID，客户端仅确认 / 拒绝或审阅生成参数。任务步数是 ComfyUI 节点步数，没有数据时为 null，不计算伪造的总进度。64 位 seed 在传输层以字符串表示，落盘仍为原整数。

## 测试结果（2026-10-10）

- Python：79 项通过，其中原 v0.2.0 的 68 项全部保留；新增服务、媒体安全、编解码和真实 Qt 文件选择流程测试。
- 正式打包 EXE：8 项桌面回归通过。覆盖创建 / 编辑 / 导入 / 保存 / 重开、旧项目、图片缩放、版本归属、关联 / 时间轴 / 折叠、真实队列取消、提示词恢复、AI 参数审阅与任务重试、视频实际播放和拖动、41 个真实长文本卡片及空搜索。
- 1920×1080、2560×1440、3840×2160、1024×768 视口和 125% 浏览器缩放检查通过。采用 Qt 6 自动 DPI；这是布局 / 缩放验证，不等同在三台不同物理显示器上的实测。
- 真实低规格工作流：Qwen BF16 原配置与 INT8 文生 / 编辑、Krea2、九种风格 LoRA、QuadView 开 / 关、RFMSR 1.5×、四种 H3 模式、电影 LoRA 开启均成功。图片 / 视频输出均检查实际尺寸和可解码媒体。
- 真实 DeepSeek：账户模型列表、Flash 多轮创建→审阅→Krea 出图、按需 Skill、真实联网检索、打包 EXE 使用 v4-pro 对话通过。没有使用替代回复或假任务。
- 实际取消：仅取消本应用发起的 H3 prompt_id，任务返回 cancelled。
- 实际退出恢复：生成中关闭 EXE；重开后没有自动重交；使用原 prompt_id `004fa4f0-f61e-4ae4-8a0d-9bd423c199a2` 查询并下载结果，原镜头仅新增一个视频版本。独立 ComfyUI PID 46192 在前后保持运行。
- 视频缓存：实际 H.264/AAC 测试媒体转为 VP9/Opus，24 帧和 48000 个音频采样保留，源文件哈希不变；缓存取消会清理未完成文件。实际旧 H3 视频已在 EXE 内播放、暂停和拖动。
- 构建：Vue TypeScript / Vite 检查通过；PyInstaller 6.22.3 Windows onedir 成功，包含 WebEngineProcess、WebChannel、前端、Skill 与编解码依赖。

逐项生成证据见 `VALIDATION-v0.3.0.json`。完整本机记录为 `local-data/v030-live-report.json`、`v030-recovery-report.json`、`v030-packaged-agent.json`；测试素材和密钥不提交 Git。

## 修改文件清单

- `main.py`、`studio/__init__.py`：唯一正式入口与 v0.3.0 版本。
- `studio/desktop.py`：桌面 Web 容器、有限 Bridge、导航约束、应用生命周期。
- `studio/service.py`：从旧窗口提取的项目 / 任务 / AI 审阅协调服务。
- `studio/media_server.py`：仅 loopback 的静态 / 项目媒体读取与 Range。
- `studio/video_preview.py`：可取消、原子写入、单后台线程的视频预览缓存。
- `frontend/`：沿用已验收原型的正式 Vue 页面、组件、类型、真实状态及 RPC；包含桌面 / 真实推理 QA 脚本。
- `scripts/build.ps1`：Vue 构建与 Windows WebEngine 打包；保留已有发布目录。
- `tests/test_desktop_service.py`、`tests/test_video_preview.py`：新增集成检查。
- `README.md`、本说明、验证 JSON、截图：启动、兼容性与验收证据。

`storage.py`、`workflows.py`、`comfy.py`、`deepseek.py`、`skill_library.py`、`research.py` 和原 `ui.py` 没有修改；旧项目格式和工作流图保持原有契约。

## 截图

![正式 EXE 分镜工作区](screenshots/v030-storyboard.png)
![角色资产](screenshots/v030-characters.png)
![场景资产](screenshots/v030-scenes.png)
![设置](screenshots/v030-settings.png)
![真实 DeepSeek 审阅及生成](screenshots/v030-agent.png)

## 已知范围与验收限制

- 首次观看 H3 原视频会准备 VP9/Opus 兼容预览；最长边最多 1280 像素，原始视频保留，可用“打开原文件”查看。缓存位于项目 previews，重新打开可复用。CPU 转换需要等待，界面明确显示准备状态。
- 本轮推理保持 0.1 MP、短视频 / 低步数。没有验证高分辨率、长时长或所有参数组合的显存表现，也不将其标为推荐配置。
- 本机 Computer Use 无法激活原生系统文件选择窗口，返回 `failed to activate captured window`。已验证其正常弹出与归属，另用真实 Qt 文件对话框测试新建 / 打开 / 导入的实际返回路径；原生系统选择器的人工点选仍应由用户复核。该限制没有以 Mock 文件返回替代生产逻辑。
- 无完整非线性剪辑器、自动成片拼接、视频 / 音频参考输入或自动连续性审片；这些不属于旧 v0.2.0 功能，迁移未新增承诺。
- ComfyUI 重启丢失自身历史时，应用不能凭空恢复结果；提交不明且没有 prompt_id 的任务不会自动重交。关闭应用只断开自身查询，不关闭或全局中断 ComfyUI。
- 旧 Qt v0.2.0 不识别新增的项目互斥锁；不要让回退程序和正式版本同时编辑同一个项目。回退前关闭正式版本并保留项目副本。

## 发布与回退操作

正式包：`releases/v0.3.0/XY-Studio/XY-Studio.exe`，需保留整个目录。用户运行不需要 Node、Python 或 Rust；只需原 ComfyUI 与模型环境。源码：构建 frontend 后运行 main.py。Qt Widgets 旧界面只能通过 v0.2.0 包或旧 Git 标签使用，不再作为正式入口。

本次使用独立测试项目，未覆盖已有项目或 v0.2.0 发布包。回退时关闭 v0.3.0，双击原 `releases/v0.2.0/XY-Studio/XY-Studio.exe` 打开项目副本；schema=1 不需要逆向转换。新增 previews 缓存可忽略。
