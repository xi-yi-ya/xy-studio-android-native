# 公开交付 · 2026-10-28

作者已授权将此前独立私有仓库公开，并上传源码、文档、Android Debug APK 和 Windows LAN / Pixstag 预览包。原工作目录、未提交工作、项目数据和原桌面仓库的 Git 远端保持原状。

## 包含

Kotlin / Compose 原生客户端、PC LAN 与共享 Python 业务、Vue 桌面、ComfyUI 工作流、Pixstag V2、自动化测试、构建部署脚本、中文手册、Java 阅读模型与 Javadoc。Capacitor 试作以停止维护状态保留源码。

二进制放在 Releases，包含 APK、完整 Windows ZIP、离线手册 ZIP、SHA256SUMS.txt。不分发模型、ComfyUI 环境、IDE/SDK/JDK 安装器或私钥。

## 验证与边界

181 项 Python、10 项 Android 单测以及 1 项模拟器界面回归为 2026-10-26 真实历史结果。模拟器走真实 PC HTTP/WebSocket，云端表单 / 参考图片视频 / 暂停入队取消通过，既有真实视频播放到 1.645 秒。本次发布会核对源码文件、历史敏感信息、安装包 SHA-256、ZIP CRC 和 GitHub 远程回读。

没有提交付费 Pixstag 任务；没有将账户查询成功、合同测试或暂停队列称为真实云端生成成功。本次云端接入未做实体手机 Wi-Fi 验收。最终 Windows 包已构建并启动，进一步人工窗口验收因作者 Esc 停止。

已知限制：API 无已提交任务取消端点或整体百分比；音频参考选择、封面 / 尾帧独立下载、未知提交后的手动任务 ID 绑定尚未提供。停止查询不停止云端计费。一次定向测试出现 Windows Qt/COM 诊断，同轮测试继续通过，隔离复验通过，未掩盖该记录。

原始截图 / logcat 含个人素材与设备信息，只留本机；公开汇总见 demo/evidence/public-summary-20261028/。历史文档保留原日期，“未上传 / 私有”指当时状态。

## 运行和回退

Windows 完整解压运行 XY-Studio/XY-Studio.exe，点“手机连接”；Android 安装 Release APK。密钥和连接密码由使用者自行配置。详细见 ANDROID-NATIVE.md、PIXSTAG-VIDEO.md 和 android-handbook/manual.html。

本次源码为原有私有历史的后续提交，不重写远端历史。旧 Release 和本机旧 Windows 包保留。运行旧版前先退出新版；Android 旧版降级可能被系统阻止，不为降级清除应用数据。恢复本地源码可使用 Git 对照旧提交，用户项目不做迁移 / 删除。
