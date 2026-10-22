# 第一版实现说明

GUI（Qt 主线程）负责项目变更和审阅；推理 worker 使用项目快照，独立写任务 journal，信号返回主线程后再合入项目。生成以单队列串行提交，避免应用主动同时加载多个生成任务。ComfyUI 外部用户仍可提交任务，应用不清空全局队列。

`workflows.py` 构建 API DAG，依据 `/object_info` 检查节点存在、模型枚举、连接闭合。原编辑器 workflow 中的预览、注释、断开节点不进入 API 图。工作流模型和采样器显式固定，GUI 参数替换有界字段。H3 LoRA 同时接入 guider 和 scheduler，关闭则两者直连底模。

`comfy.py` 使用 HTTP 上传、提交、历史轮询和输出下载，WebSocket 接收按 prompt_id 过滤的当前节点步数。提交响应或采样 100% 不是完成；只有 history.completed 后成功回收 output 媒体才登记完成。没有步数时显示忙碌状态，WebSocket 不可用时仍轮询 HTTP，不伪造总进度。网络异常不自动重新提交。目标后端支持带 prompt_id 的中断；取消只针对所选任务。

`storage.py` 项目相对路径、导入副本、原子 JSON 替换、生成历史。条目删除保留媒体文件。路径解析拒绝越出项目。中断恢复以 jobs journal 为准，重复输出注册幂等。

`deepseek.py` 官方 chat/completions + tools。AI 只能提出 set_story / add_item / update_item / generate，字段校验且需 GUI 审阅。它不能执行系统命令或删除任意文件。2026-10-09 已验证真实 API 文本及多轮工具消息，下一轮可以引用上一轮已完成图片的实际路径；并非自动执行未来输出依赖的任务图。

v0.1.4：在项目操作外增加只读 read_skill 和 web_search。初始提示词只带技能目录，允许读取白名单内的独立技能文件；技能正文保留在本轮临时消息中。联网使用 DeepSeek Anthropic 兼容 `/anthropic/v1/messages` 的服务端搜索，并由主对话整理有来源的回答；不假设 Responses API 会执行 web_search。工具循环最多 8 次主对话请求、3 次搜索调用。只读操作与项目操作混在一轮时，先返回资料，要求模型重新提出修改，原 GUI 审阅边界不变。日志记录已读文件与实际搜索来源，不保存密钥。

模型通过 `/models` 获取，GUI 提供缓存列表及手动异步刷新；请求开始时固定模型、联网开关与项目快照。来源链接仅允许 HTTP/HTTPS，渲染前转义 HTML，不允许链接执行本地文件或脚本。

与原工作流差异：Qwen 常规 8-bit PNG 保存；Qwen 编辑新增 VAE 和有序图像引用及确定性几何处理；四视图使用 source_image、VAE、target_latent 路径减少中途 VAE 换入，输出尺寸改为 GUI 选择；RFMSR 直接保存结果，省略 UI 清理/预览；H3 时长在客户端用相同表达式算好。明确排除独立电影工作流及断开的 Turbo/放大节点。
