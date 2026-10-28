# XY Studio v0.3.2

## 修改

- 角色、场景、分镜图及关联素材重复点击可以取消选中。取消由后端原子判断，避免快速重复点击的状态竞争；时间轴定位仍明确选中，双击查看大图保持对象上下文。右键、更多菜单及历史/生成按钮不会意外切换选中状态。明确发送给 AI 的固定上下文不会随普通取消选中而删除。
- 新增统一 `TaskProgress.vue`：角色/场景卡片、分镜卡片、全局当前任务及任务列表均显示真实阶段。ComfyUI 返回节点步数时显示比例条、步数和当前节点百分比；没有步数时显示等待、提交、排队、执行、保存等阶段，不推算百分比。节点 100% 不代表任务完成。
- 同一素材存在运行任务及后来加入的任务时，卡片优先显示实际运行任务，避免最新排队记录遮住进度。
- ComfyUI 兼容 `progress_state` 的运行节点，继续过滤其他 prompt。握手与接收分开设定超时；取消接口 HTTP 200 空响应不再被错误当作无效 JSON。
- Agent 连续操作只完成原因分析与实现方案，未改执行权限、工具审阅、Skill 或生成完成后的接续规则。[方案说明](AGENT-CONTINUATION-PLAN.md)

## 验证结果

- Vue TypeScript 检查与 Vite 构建通过，Windows PyInstaller 包构建通过。
- 82 项 Python 测试通过，包含原有所有测试、新增选中切换、progress_state 过滤及取消空响应回归。
- 9 项真实 Qt WebEngine 桌面回归在源码及打包版均通过：角色/场景/分镜取消选中、菜单与双击、关联素材、时间轴、项目保存打开、生成审阅、模式边界、队列取消、真实旧视频播放、缩放及大量分镜。
- 打包版三个真实暂停队列任务及四个进度显示区域验证通过：后端实际建立 journal；暂停时不提交 ComfyUI，不显示百分比；三个任务均通过正常接口取消。验收后正常关闭打包版，EXE 及对应 WebEngine 进程退出；独立 ComfyUI PID 46192 仍监听 8188。
- 本轮低规格 Krea 实际生成成功，HTTP 阶段与结果登记正常，但数字进度实测**未通过**：现有 8188 的 WebSocket 只发握手状态/协商回复，不推送生成事件，连空队列更新也未推送。独立 socket 诊断复现同样现象，不是单独的 Vue 显示问题。没有在前端伪造步数，也没有将该实测改成放宽断言的“通过”。

## 当前待处理事项

后续结果（2026-10-10）：用户允许重启后，v0.3.3 验证完成真实角色、场景、分镜图片和低规格 H3 的步数与界面百分比一致，本节原阻塞已解除。详情见 [v0.3.3](RELEASE-v0.3.3.md)。以下保留 v0.3.2 交付当时的证据边界。

已向用户请求允许重启独立 ComfyUI 来继续排查和验证节点推送。当前队列为空，但重启会清除其内存历史，所以尚未执行。不能据现有证据保证重启必然解决问题；如仍异常，应进一步定位 ComfyUI 事件发布或扩展的影响。数字节点进度的最终实测因此仍待完成，阶段显示已经验证。

本次不改 DeepSeek Key、原项目 schema、资产 ID、业务工作流及历史格式。旧版本目录保留。测试使用独立项目，未重放用户的舞台/初音请求，也未开启自动连续生成。

## 文件清单

| 范围 | 文件 |
|---|---|
| 原子取消选中及活动任务选择 | `studio/service.py`、`frontend/src/stores/studio.ts` |
| 统一进度、图片点击与布局 | `frontend/src/components/TaskProgress.vue`、`AssetCard.vue`、`ShotCard.vue`、`frontend/src/App.vue`、`frontend/src/style.css` |
| ComfyUI 事件及空响应兼容 | `studio/comfy.py` |
| 回归及显式实测脚本 | `tests/test_desktop_service.py`、`tests/test_core.py`、`frontend/tests/desktop.spec.ts`、`progress-live.mjs`、`release-progress-check.mjs` |
| 版本与交付说明 | `studio/__init__.py`、`frontend/package.json`、`frontend/package-lock.json`、`README.md`、本文及 Agent 方案 |

## 界面截图

以下截图是实际暂停队列，不能作为采样百分比已实测通过的证据。

![分镜与全局阶段进度](screenshots/v032-queued-storyboard.png)

![角色卡片进度](screenshots/v032-queued-role.png)

![场景卡片进度](screenshots/v032-queued-scene.png)

![任务列表](screenshots/v032-queued-tasks.png)

本机运行：`releases/v0.3.2/XY-Studio/XY-Studio.exe`，保留整个 `XY-Studio` 文件夹。旧版若正打开同一项目，需先关闭旧版再在新版打开，以避免项目锁冲突。
