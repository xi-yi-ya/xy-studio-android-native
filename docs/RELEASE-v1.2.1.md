# XY Studio v1.2.1 — 生图操作纠正、素材删除与取消拖拽

本版仅本机交付，没有 push、远程发布或上传。v1.2.0 与既有项目保留。

## 确认的问题

用户在 `releases/v0.3.1/XY-Studio/project` 的聊天中要求“帮我生成一个洛天依三视图”。保存的工具调用却是 `add_item(characters)` 和 `add_item(scenes)`，没有已有图片路径，因此在选用素材时失败，根本未进入 ComfyUI 队列。这不是用户操作错误。旧对话可能影响模型选择，但不把未经证明的模型内部原因当作结论。

图片库原来没有删除入口，也属于功能缺口。取消全部拖拽是用户确认的交互变更。

## 已完成

- Agent 明确区分生成新图片与选用已有图片，三视图请求默认 Qwen 文生图。添加角色、场景必须提供库内存在的图片。错误工具建议在进入审阅前整批拦截，反馈给模型，最多纠正两次；不会先执行一部分操作，也不会绕过用户参数审阅。
- 图片库、视频库的导入素材和生成结果均可移入项目回收站、恢复。删除后普通图库、选用入口和 AI 查询排除该文件；下一条消息的对应 AI 附件也取消。
- 删除保留原文件、生成历史、路径与素材 ID，不释放磁盘空间。当前角色、场景、分镜正在使用的文件，或未完成任务引用的文件，需要先解除使用；审阅和 Agent 操作期间不允许删除。
- 已删除的历史版本不能重新选用；再次生成若需要回收站参考图，会提示先恢复。旧任务记录恢复不能重新把删除输出设为当前素材。
- 删除全部内部图片拖拽、外部图片/视频拖入及原生 drop 事件桥接。保留导入按钮、发送给 AI、选择参考图、引用取消、参考图上移/下移按钮。
- Java 对照开发文档新增第 14 章，解释整批预校验、有限纠正、逻辑删除与恢复；第 13 章拖拽明确标为历史实现。

## 验证

- Python：136 项通过。
- Vue 类型检查、Vite 生产构建通过；最终源码构建产物与打包版前端逐文件 SHA256 一致。
- 真实 Qt 桌面：24 项界面测试在源码和 Windows 包通过。包括新旧项目、图片放大、视频播放、历史归属、任务入口、2K/4K/窄窗口，以及新增的删除、恢复、持久化、引用取消和禁止拖拽。
- 源码实测：保留原错误聊天的项目副本，使用真实 DeepSeek 发送原句，得到 Qwen 文生图审阅，取消测试生成。
- 打包版实测：原项目另一副本、同一句请求，真实 DeepSeek → 参数确认 → ComfyUI Qwen 生图 → 结果入库 → UI 删除与恢复。测试选择 0.2 MP，实际输出 608×352，40 步；观察到实际采样进度，未造进度。
- 生成未增加角色、场景或分镜。对历史真实图片、视频输出另测删除/恢复与任务记录、原字节保留；本轮未重新执行视频推理。
- 用户原项目 `project.json` 与测试前 SHA256 一致。测试窗口及其 WebEngine 子进程均正常退出；用户已打开的 v1.2.0 和独立 ComfyUI 继续运行。

详细机器记录：[VALIDATION-v1.2.1.json](VALIDATION-v1.2.1.json)。测试中新增的模型异常输入使用可控回复；真实 API 测试单独记录，不把夹具当成模型验证。

## 使用

运行 `releases/v1.2.1/XY-Studio/XY-Studio.exe`，打开原项目目录即可。发布包需保留整个文件夹。

图片库 / 视频库 → 卡片“删除” → “移入回收站”；点击库右上“回收站”可恢复。要给 AI 引用图片，点击“发送给 AI”。外部文件用“导入图片 / 导入视频”。

## 已知边界

- 回收站是本项目的可恢复移除，不是 Windows 回收站，也没有永久删除或磁盘清理功能。
- 旧版本不识别可选 `media_trash` 字段，回退旧版会重新显示这些原文件。请使用新版管理回收站。
- 历史聊天保留原错误消息，因此测试截图中能看到先前失败记录；它不代表本次仍失败。没有擅自删除用户聊天。
- 实际低分辨率生成用于验证链路，不代表角色形象和高分辨率质量验收。模型仍可能给出错误建议；有限纠正失败会明确停止，不承诺完全杜绝。

## 修改文件

| 范围 | 文件 |
| --- | --- |
| 工具校验 | `studio/deepseek.py`、`studio/service.py` |
| 素材删除/恢复及历史保护 | `studio/asset_library.py`、`studio/storage.py`、`studio/service.py` |
| 禁止原生拖入 | `studio/desktop.py`；删除 `studio/file_drop.py` |
| Vue 交互 | `App.vue`、`AssetCard.vue`、`AssistantPanel.vue`、`GenerationForm.vue`、`MediaLibrary.vue`、`ReferenceImages.vue`、`ShotCard.vue`、`style.css`；删除 `mediaDrag.ts` |
| 回归测试 | `tests/test_agent.py`、`tests/test_library_flow.py`、`frontend/tests/desktop.spec.ts`、`frontend/tests/library-flow.spec.ts`、新增 `frontend/tests/agent-three-view-live.mjs`；删除过时 `scripts/verify_native_drop.py` |
| 版本/文档 | `studio/__init__.py`、`frontend/package.json`、`frontend/package-lock.json`、README、Java 对照文档、本交付/验收记录及截图 |

## 界面截图

![项目回收站](screenshots/v121-package-recycle-bin.png)

![原句进入图片生成审阅](screenshots/v121-package-three-view-review.png)

![真实生成结果删除后恢复](screenshots/v121-package-generated-restored.png)
