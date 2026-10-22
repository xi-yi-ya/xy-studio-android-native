/** Explicit real DeepSeek read-only asset query. No generation submission. */
import {chromium} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
const version=process.env.XY_VALIDATION_VERSION || 'v110';
const b=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const p=b.contexts()[0].pages()[0];
const rpc=(command,payload={})=>p.evaluate(async([command,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload]);
let before;
try{
 before=await rpc('bootstrap');
 await rpc('project.open',{path:path.resolve('../local-data/v110-library-fixture')});await rpc('settings.save',{online:false});
 await rpc('context.clear');
 const images=await rpc('library.query',{kind:'image',limit:100}),videos=await rpc('library.query',{kind:'video',limit:100});
 const start=await rpc('bootstrap');if(!start.config.keySet)throw Error('Saved DeepSeek key unavailable');
 await p.getByLabel('给 AI 助手的消息').fill('请查询本项目的完整图片库和视频库，分别报告全部素材数量、生成数量和导入数量，并列出舞台的历史图片以及条目删除后仍保留的生成图片。请实际查询全部记录，需要时分页，只查询不创建条目、不生成任何内容，也不要输出文件路径或内部工具信息。');
 await p.getByRole('button',{name:'发送消息',exact:true}).click();
 await p.waitForFunction(()=>!document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').busy,{},{timeout:240000});
 const end=await rpc('bootstrap');const message=end.project.chat.at(-1);
 const queries=message.activity.filter(a=>a.type==='asset_query');
 if(!queries.some(a=>a.kind==='image'&&a.total===images.total) || !queries.some(a=>a.kind==='video'&&a.total===videos.total))throw Error('Missing actual full image/video inventory query');
 if(end.review || end.project.tasks.length!==start.project.tasks.length || end.project.assets.length!==start.project.assets.length)throw Error('Read-only query modified project');
 const visible=await p.locator('.assistant-panel').innerText();
 if(/SKILL\.md|query_image_assets|query_video_assets|"type"\s*:|assets\/|outputs\//.test(visible))throw Error('Technical metadata leaked into UI');
 await fs.writeFile(`../local-data/${version}-asset-query-report.json`,JSON.stringify({passed:true,model:end.config.model,queries,expected:{images:images.stats,videos:videos.stats},response:message.text,readOnly:true},null,2));
 await p.screenshot({path:`../docs/screenshots/${version}-asset-query.png`});
 console.log('REAL DEEPSEEK: complete image/video inventory queries and read-only behavior passed');
}finally{
 if(before){const s=await rpc('bootstrap');if(s.review)await rpc('review.respond',{id:s.review.id,accepted:false});await rpc('settings.save',{online:before.config.online,model:before.config.model});await rpc('project.open',{path:before.project.root});}
 await b.close();
}
