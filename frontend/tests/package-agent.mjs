import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
const b=await chromium.connectOverCDP('http://127.0.0.1:9226',{noDefaults:true});const p=b.contexts()[0].pages()[0];
const rpc=(name,args={})=>p.evaluate(async([name,args])=>await document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,args),[name,args]);
const before=await rpc('bootstrap');
try{
 await p.getByLabel('AI 模型',{exact:true}).selectOption('deepseek-v4-pro');
 await p.getByLabel('给 AI 助手的消息').fill('当前项目叫什么名字，一共有几个镜头？只回复一句中文，不要调用工具。');
 await p.getByRole('button',{name:'发送消息',exact:true}).click();
 await p.waitForFunction(()=>!document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').busy,{}, {timeout:180000});
 const s=await rpc('bootstrap');const message=s.project.chat.at(-1);
 if(message.role!=='assistant' || (!message.text.includes('1') || !message.text.includes(before.project.name)))throw Error('Packaged DeepSeek response missing');
 await fs.writeFile('../local-data/v031-packaged-agent.json',JSON.stringify({model:s.config.model,keyAvailable:s.config.keySet,message,passed:true},null,2));
 console.log('PACKAGED REAL DEEPSEEK PASSED',s.config.model);
}finally{await rpc('settings.save',{model:before.config.model,online:before.config.online});await b.close()}
