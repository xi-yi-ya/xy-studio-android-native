/** Explicit real DeepSeek request; prepares an image edit and cancels before inference. */
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
const b=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const p=b.contexts()[0].pages()[0];
const validationVersion=process.env.XY_VALIDATION_VERSION || 'v033';
const rpc=(command,payload={})=>p.evaluate(async([command,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload]);
let before;
try{
 await p.reload();await p.getByRole('button',{name:/保存项目/}).waitFor();
 before=await rpc('bootstrap');
 const report=JSON.parse(await fs.readFile(`../local-data/${validationVersion}-progress-report.json`,'utf8'));
 await rpc('project.open',{path:report.project});await rpc('settings.save',{online:false});
 const s=await rpc('bootstrap');if(!s.config.keySet)throw Error('DeepSeek key is unavailable');
 const actor=s.project.assets.find(a=>a.kind==='characters');await rpc('selection',{id:actor.id});
 await p.getByRole('button',{name:'角色资产',exact:true}).click();
 await p.getByLabel('给 AI 助手的消息').fill('请立即为选中的角色生成一个修改版本：使用它现有的图片作为 Qwen 编辑参考，把机器人身体改成黄色，保留原有构图、造型和背景，不创建新角色。请调用图片编辑操作，我会在界面参数窗口审阅。');
 await p.getByRole('button',{name:'发送消息',exact:true}).click();
 await p.waitForFunction(()=>{const s=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');return !!s.state.review || !s.busy},{},{timeout:240000});
 const ready=await rpc('bootstrap');if(ready.review?.name!=='generate')throw Error('No actual image-edit suggestion was prepared');
 const message=ready.project.chat.at(-1);
 if(!/[\u4e00-\u9fff]/.test(message.text))throw Error('Operation explanation is not presented in Chinese');
 if(!message.activity.some(a=>a.type==='skill'&&a.skill==='qwen'))throw Error('No real guide reading evidence');
 const visible=await p.locator('.assistant-panel').innerText();
 if(/SKILL\.md|"type"\s*:|"file"\s*:|read_skill/.test(visible))throw Error('Internal metadata leaked into chat');
 await p.getByRole('button',{name:'审阅操作',exact:true}).click();await p.getByLabel('生成提示词').waitFor();
 if(await p.locator('.reference-row').innerText().then(t=>/assets\/|outputs\//.test(t)))throw Error('A raw reference path is visible');
 await p.getByRole('button',{name:'取消生成',exact:true}).click();
 const end=await rpc('bootstrap');if(end.project.tasks.length!==s.project.tasks.length || end.review)throw Error('Cancelled suggestion submitted inference');
 await p.screenshot({path:`../docs/screenshots/${validationVersion}-assistant.png`});
 await fs.writeFile(`../local-data/${validationVersion}-readable-agent-report.json`,JSON.stringify({model:end.config.model,skillReads:message.activity.filter(a=>a.type==='skill').length,response:message.text,reviewCancelled:true,taskCountUnchanged:true,passed:true},null,2));
 console.log('REAL DEEPSEEK: readable reply, guide loading, image-edit review and cancellation passed');
}finally{
 if(before){const state=await rpc('bootstrap');if(state.review)await rpc('review.respond',{id:state.review.id,accepted:false});await rpc('settings.save',{online:before.config.online,model:before.config.model});await rpc('project.open',{path:before.project.root});}
 await b.close();
}
