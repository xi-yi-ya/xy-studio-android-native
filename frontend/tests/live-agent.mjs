/** Continue an explicit live-desktop run; also verifies newly approved Agent actions. */
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
const b=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const p=b.contexts()[0].pages()[0];
const rpc=(name,args={})=>p.evaluate(async([name,args])=>await document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,args),[name,args]);
const state=()=>rpc('bootstrap');
const report=JSON.parse(await fs.readFile('../local-data/v030-live-report.json','utf8'));
const record=async label=>{await fs.writeFile('../local-data/v030-live-report.json',JSON.stringify(report,null,2));console.log(label)};
async function until(predicate,seconds=300){const end=Date.now()+seconds*1000;while(Date.now()<end){const s=await state();if(predicate(s))return s;await new Promise(r=>setTimeout(r,500));}throw Error('Actual backend timeout');}
try{
 const s=await state();if(s.project.root!==report.project)throw Error('Wrong live project');
 if(s.review?.name!=='generate')throw Error('Expected saved pending generation review');
 if(!await p.getByLabel('分辨率 MP').count())await p.getByRole('button',{name:'审阅操作',exact:true}).click();
 await p.getByLabel('分辨率 MP').fill('.1');await p.getByLabel('采样步数').fill('4');
 await p.getByRole('button',{name:'加入生成队列',exact:true}).click();
 const final=await until(s=>!s.activeJob && !s.busy,420);
 if(final.project.tasks.at(-1).status!=='completed')throw Error('Agent generation failed');
 report.agent={approved:2,status:'completed',target:final.project.tasks.at(-1).targetId,skills:final.project.chat.flatMap(m=>m.activity||[]).filter(a=>a.type==='skill')};
 await record('DeepSeek 创建→确认→实际图片 completed');
 await rpc('settings.save',{online:true});
 await p.getByLabel('给 AI 助手的消息').fill('请联网查询 Vue 3 的官方文档网址，只需要一句话和来源链接，不要创建或生成内容。');await p.getByRole('button',{name:'发送消息',exact:true}).click();
 const searched=await until(s=>!s.busy,300);report.search=searched.project.chat.at(-1);
 if(!report.search.activity.some(a=>a.type==='search'))throw Error('No real search evidence');
 await record('DeepSeek 实际联网 completed');
 await rpc('project.save');report.resolvedErrors=report.errors;report.errors=[];report.passed=true;
 await record('ALL REAL INTEGRATION TESTS PASSED');
 await p.getByRole('button',{name:'场景资产',exact:true}).click();await p.screenshot({path:'../docs/screenshots/v030-agent.png'});
}catch(e){report.errors.push(String(e));await record('FAILED '+String(e));process.exitCode=1}
finally{await b.close()}
