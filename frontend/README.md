# XY Studio 正式 Vue 前端

此目录是 v0.3.0 的正式前端，直接接入 Python 服务；原型保留在 `prototypes/vue-workbench/`。

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
.venv\Scripts\python.exe main.py
```

独立 `npm run dev` 只用于界面开发，无法连接桌面 Bridge 时明确显示错误，没有 Mock 回退。业务操作只经 QWebChannel 请求；本地 HTTP 只提供静态资源与当前项目媒体。

Qt 容器持有生命周期和原生文件选择器。状态 DTO 在 `src/types.ts`，RPC 在 `src/gateway.ts`，项目和视图状态在 `src/stores/studio.ts`。所有项目变更、审批与队列操作都由 `studio/service.py` 执行；Vue 不写项目文件。

桌面端回归测试需先启动独立旧项目副本：

```powershell
.venv\Scripts\python.exe main.py local-data/XY-Studio-v030-compat --debug-port 9225
npm --prefix frontend test
```

测试会在 `local-data/` 新建真实测试项目，调用真实 Bridge；不会提交推理或调用 DeepSeek。测试依赖本机兼容性副本中的旧视频与图片。`tests/live-*.mjs` 和 `tests/desktop-recovery.mjs` 是单独显式运行的真实推理 / 计费测试，不属于默认 `npm test`。

`--debug-port` 只用于显式 QA；正常双击 EXE 不开启调试端口。发布构建使用 `scripts/build.ps1`，将 Vue 产物随 PyInstaller 一起打包，无需用户安装 Node、Python 或启动前端服务器。
