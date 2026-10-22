/** Actual owned ComfyUI cancellation and durable close/reopen recovery setup. */
import {chromium} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
const b=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9226',{noDefaults:true});const p=b.contexts()[0].pages()[0];
const rpc=(name,args={})=>p.evaluate(async([name,args])=>await document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,args),[name,args]);
const state=()=>rpc('bootstrap');
async function until(predicate,seconds=180){const end=Date.now()+seconds*1000;while(Date.now()<end){const s=await state();if(predicate(s))return s;await new Promise(r=>setTimeout(r,100));}throw Error('Actual task timeout');}
const root=path.resolve('../local-data/v030-recovery-'+Date.now());const report={project:root};
try{
 await rpc('project.new',{path:root,title:'桌面任务恢复验收'});
 const shot=await rpc('asset.add',{kind:'shots',description:'机器人动作'});
 const live=JSON.parse(await fs.readFile('../local-data/v030-live-report.json','utf8'));
 const reference=path.join(live.project,live.tests[0].outputs[0]);
 const [ref]=await rpc('asset.import',{id:shot,paths:[reference]});
 const gen={...(await rpc('generation.defaults',{target:shot,mode:'h3_i2v'})),megapixels:.1,seconds:.5,steps:20,references:[ref],prompt:JSON.stringify({integrated_multimodal_description:'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced. [Shot 1] The robot slowly raises its hand. Static camera, retain background.',overall_soundscape:'Quiet room tone.',non_diegetic_music:'None.'})};
 const cancel=await rpc('generation.submit',{target:shot,generation:gen});
 await until(s=>s.project.tasks.find(t=>t.id===cancel)?.raw.prompt_id);
 await p.getByRole('button',{name:'任务与历史',exact:true}).click();await p.getByRole('button',{name:'取消',exact:true}).click();
 const cancelled=await until(s=>s.project.tasks.find(t=>t.id===cancel)?.status==='cancelled' && !s.activeJob);
 report.cancel=cancelled.project.tasks.find(t=>t.id===cancel).raw;
 console.log('ACTUAL OWNED TASK CANCELLED',cancel);
 const resume=await rpc('generation.submit',{target:shot,generation:{...gen,steps:16,seed:'884042'}});
 const submitted=await until(s=>s.project.tasks.find(t=>t.id===resume)?.raw.prompt_id);
 report.resume=submitted.project.tasks.find(t=>t.id===resume).raw;
 await fs.writeFile('../local-data/v030-recovery-report.json',JSON.stringify(report,null,2));
 console.log('READY FOR CLOSE / REOPEN',resume,report.resume.prompt_id);
 // Request only our app's graceful close. It does not cancel the external task.
 try{await rpc('app.close')}catch(e){if(!String(e).includes('closed'))throw e}
}finally{await b.close()}
