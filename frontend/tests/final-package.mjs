import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
const b=await chromium.connectOverCDP('http://127.0.0.1:9226',{noDefaults:true});const p=b.contexts()[0].pages()[0];
const rpc=(name,args={})=>p.evaluate(async([name,args])=>await document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,args),[name,args]);
try{
 const root=path.resolve('../local-data/v030-bf16-'+Date.now());await rpc('project.new',{path:root,title:'BF16 原工作流验收'});
 const actor=await rpc('asset.add',{kind:'characters',name:'BF16 机器人',description:'桌面上的红色玩具机器人'});
 await p.getByRole('button',{name:'角色资产',exact:true}).click();await p.getByTestId('asset-'+actor).getByRole('button',{name:'生成新版本',exact:true}).click();
 await p.getByLabel('生成提示词').fill('A small red toy robot on a wooden desk against a plain blue wall, soft daylight, detailed photography.');
 await p.getByLabel('分辨率 MP').fill('.1');await p.getByLabel('采样步数').fill('4');
 await p.getByRole('button',{name:'加入生成队列',exact:true}).click();
 await p.waitForFunction(()=>{const s=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');return !s.state.activeJob && s.project.tasks.length && ['completed','failed','unknown'].includes(s.project.tasks.at(-1).status)}, {}, {timeout:600000});
 const s=await rpc('bootstrap');const job=s.project.tasks.at(-1);
 await fs.writeFile('../local-data/v030-bf16-report.json',JSON.stringify({project:root,job:job.raw,passed:job.status==='completed'},null,2));
 if(job.status!=='completed')throw Error(job.error);
 console.log('PACKAGED BF16 QWEN ACTUAL GENERATION PASSED');
 await rpc('project.open',{path:path.resolve('../local-data/XY-Studio-v030-compat')});
 await p.getByRole('button',{name:'分镜工作区',exact:true}).click();
 await p.locator('.workspace-scroll').evaluate(el=>el.scrollTop=0);
 await p.screenshot({path:'../docs/screenshots/v030-storyboard.png'});
 await p.getByRole('button',{name:'角色资产',exact:true}).click();await p.screenshot({path:'../docs/screenshots/v030-characters.png'});
 await p.getByRole('button',{name:'场景资产',exact:true}).click();await p.screenshot({path:'../docs/screenshots/v030-scenes.png'});
 await p.getByRole('button',{name:'设置',exact:true}).click();await p.screenshot({path:'../docs/screenshots/v030-settings.png'});
 console.log('FINAL PACKAGE SCREENSHOTS SAVED');
}finally{await b.close()}
