"""Refresh offline source snapshots and file map. No network or app mutations."""
from pathlib import Path
from html import escape
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'android-native/app/src/main/java/cn/xiyi/xystudio'
FILES = [
 ('MainActivity','入口、连接表单、项目/资产/分镜/素材页面','onCreate → StudioTheme → StudioApp；ProjectsScreen 发项目命令，EditAssetDialog 保存时带 revision。MainActivity 类很短，文件内还有多个顶层页面函数。'),
 ('StudioShell','应用骨架、首页、四栏导航、创作工作区','StudioApp 读取 vm.page 决定展示哪个页面；HomeScreen 显示真实项目/任务/素材；GenerationEntries 打开生成表单。'),
 ('StudioTheme','颜色、文字、卡片与图标','StudioTheme 定义 Material3 配色；StudioCard 统一轻卡片；StudioIcon 使用 Canvas 绘制图标，不访问 PC。'),
 ('StudioViewModel','状态持有、命令调度、同步、生成与上传','先看 action 和 call，再看 pair/startSocket/receive；openGeneration 请求默认值，submitGeneration 保留审阅分支。importMedia 读取系统 Uri 并上传。'),
 ('LanApi','HTTP 请求、LAN 认证、上传和媒体地址','validateBase 限制地址；pair 取令牌；rpc 封装统一信封；upload 发送 multipart；media 只接受授权 /media/ URL。WebSocket 监听代码位于 ViewModel。'),
 ('ConnectionStore','固定连接密码的加密持久化','key 从 AndroidKeyStore 取得/创建 AES 密钥；save 使用 AES/GCM 和随机 IV；load 解密失败返回 null；clear 清除本应用保存的连接信息。'),
 ('GenerationScreen','完整图片/视频生成表单','GenerationDialog 保存输入、选择工作流与参考图、调用 GenerationRules；先 generation.preview 再显示确认框，最终调用 submitGeneration。ReferencePicker 管理参考图列表。'),
 ('GenerationRules','纯表单规则','referenceRange 给出每种 mode 的参考图数量；referenceHint 提示角色；validate 返回错误文字或 null，最终规则仍由 PC 决定。'),
 ('CreationScreens','任务列表与全屏 AI 对话','TasksScreen 展示真实状态、参数、取消与恢复查询；AssistantScreen 展示模型/消息/引用/审阅/输入；Choice 与 NumericField 是共用表单组件。'),
 ('ChatAttachments','对话附件入口与卡片','打开 ProjectMediaPicker 或系统 OpenDocument；选择 PC 媒体调用 context.add_media；手机上传交给 ViewModel；context.remove/clear 不删除素材。'),
 ('MediaPicker','独立的项目素材选择器','ProjectMediaPicker 自己维护类型、搜索、分页、错误；LaunchedEffect 加载，项目切换时关闭；不共用主素材库筛选状态。'),
 ('LibraryFilters','主素材库筛选控件','来源、所属关联、排序、回收站状态改变后重新查询；它只设置参数，不在手机重新写资产库。'),
 ('WorkspaceActions','角色/场景/分镜的补充操作','NewAssetButton 创建条目；WorkspaceActions 生成/换图/删除；LinkAssetsDialog 保存分镜关联；ChatSources 打开真实搜索来源。'),
 ('MediaDialog','图片缩放与视频预览','MediaDialog 选择图片/视频预览；NativeVideo 管理 ExoPlayer；DisposableEffect 释放，生命周期停止时暂停；图片还可进入图生视频。'),
]

def page(title, body, css='../style.css'):
    return f'<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><link rel="stylesheet" href="{css}"><header><div class="eyebrow">XY STUDIO / SOURCE READING</div><h1>{escape(title)}</h1></header><main style="max-width:1150px;margin:auto;padding:0 24px 40px">{body}</main></html>'

def lines(text):
    return '<pre>' + ''.join(f'<span class="source-line" id="L{i}"><span class="line-no">{i}</span>{escape(line)}</span>' for i,line in enumerate(text.splitlines(),1)) + '</pre>'

rows=[]; manifest={}
for name, role, route in FILES:
    path=SOURCE/(name+'.kt')
    text=path.read_text(encoding='utf-8-sig')
    methods=[]
    for i,line in enumerate(text.splitlines(),1):
        match=re.search(r'\bfun\s+(?:[\w<>?]+\.)?(\w+)\s*\(',line)
        if match:methods.append(f'<a href="#L{i}">{escape(match[1])} · {i}</a>')
    java=f'../javadoc/cn/xiyi/handbook/StudioJavaGuide.{name}.html'
    body=f'<p><a href="../java-guide.html#map">← 返回文件地图</a>　<a href="{java}">Java 职责对照</a></p><section><h2>{escape(role)}</h2><p>{escape(route)}</p><p class="small">2026-10-28 公开源码快照。真实位置：android-native/app/src/main/java/cn/xiyi/xystudio/{name}.kt。后续修改以 IDE 文件为准。</p><p>'+ ' · '.join(methods)+'</p></section>'+lines(text)
    (HERE/'source'/f'{name}.html').write_text(page(name+'.kt',body),encoding='utf-8')
    rows.append(f'<tr><td><a href="source/{name}.html">{name}.kt</a></td><td>{role}</td><td>{route}</td></tr>')
    manifest[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
table='<table><tr><th>文件</th><th>主要职责</th><th>阅读提示</th></tr>'+''.join(rows)+'</table>'
guide=HERE/'java-guide.html'
content=guide.read_text(encoding='utf-8')
if '<!-- FILE_MAP -->' in content:content=content.replace('<!-- FILE_MAP -->','<!-- FILE_MAP_START -->'+table+'<!-- FILE_MAP_END -->')
else:content=re.sub(r'<!-- FILE_MAP_START -->.*?<!-- FILE_MAP_END -->','<!-- FILE_MAP_START -->'+table+'<!-- FILE_MAP_END -->',content,flags=re.S)
guide.write_text(content,encoding='utf-8')
java=(HERE/'java-src/StudioJavaGuide.java').read_text(encoding='utf-8')
(HERE/'java-source.html').write_text(page('StudioJavaGuide.java','<p><a href="java-guide.html#java">← 返回 Java 说明</a>　<a href="javadoc/index.html">Javadoc</a></p><p class="note">可编译的教学模型，不是可替换 Kotlin 的 Android 客户端。接口没有伪造数据实现。</p>'+lines(java),'style.css'),encoding='utf-8')
(HERE/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Generated {len(FILES)} Kotlin source pages + Java reading page.')
