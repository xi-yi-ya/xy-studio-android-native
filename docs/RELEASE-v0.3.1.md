# XY Studio v0.3.1

Vue 正式迁移的交付修正版。v0.3.0 的源码、标签和发布目录保留。

- Agent 上下文补充真实项目 ID 和标题。真实 v4-pro 问答暴露旧控制层未传标题，会把有标题但故事为空的项目说成未命名；不修改 DeepSeek 工具、权限或执行审阅逻辑。
- Vue 显示后端版本号，前端依赖锁的名称与版本与正式工程同步。
- 功能清单、79 项 Python / 8 项桌面回归、21 项真实工作流和 LoRA 组合、ComfyUI 恢复及原生文件选择器自动化限制沿用 [迁移验收说明](MIGRATION-v0.3.0.md)。
- 正式 Windows 入口为 `releases/v0.3.1/XY-Studio/XY-Studio.exe`。旧项目 schema=1、凭据和工作流完全兼容，v0.2.0 可回退。

最终包验证：79 项 Python 检查、8 项桌面回归通过；真实 v4-pro 回复“当前项目叫「标题上下文验证」，一共有 1 个镜头”；正常关闭后主 EXE 与两个 QtWebEngineProcess 均退出，ComfyUI PID 46192 保持运行。记录：local-data/v031-packaged-agent.json、v031-exit-report.json。

![v0.3.1 分镜工作区](screenshots/v031-storyboard.png)
