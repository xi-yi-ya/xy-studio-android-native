import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
const b=await chromium.connectOverCDP('http://127.0.0.1:9226',{noDefaults:true});const p=b.contexts()[0].pages()[0];
const rpc=(name,args={})=>p.evaluate(async([name,args])=>await document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,args),[name,args]);
try{
 const report=JSON.parse(await fs.readFile('../local-data/v030-recovery-report.json','utf8'));
 const before=await rpc('bootstrap');if(before.activeJob)throw Error('Reopened task was auto-started');
 if(before.project.tasks.at(-1).raw.prompt_id!==report.resume.prompt_id)throw Error('Lost original prompt_id');
 await p.getByRole('button',{name:'任务与历史',exact:true}).click();await p.getByRole('button',{name:'恢复查询',exact:true}).click();
 await p.waitForFunction(()=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').project.tasks.at(-1).status==='completed',{}, {timeout:180000});
 const after=await rpc('bootstrap');const job=after.project.tasks.at(-1);
 if(job.raw.prompt_id!==report.resume.prompt_id)throw Error('Prompt was resubmitted');
 if(after.project.shots[0].versions.filter(v=>v.kind==='video').length!==1)throw Error('Duplicate history or wrong target');
 report.recovered=job.raw;report.passed=true;await fs.writeFile('../local-data/v030-recovery-report.json',JSON.stringify(report,null,2));
 console.log('RECOVERY PASSED, same prompt_id',job.raw.prompt_id);
}finally{await b.close()}
