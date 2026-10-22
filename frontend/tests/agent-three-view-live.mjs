/** Opt-in real API regression; run only on a local-data/v121-* project copy. */
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
const version=process.env.XY_VALIDATION_VERSION || 'v121-source';
const generate=process.env.XY_GENERATE==='1';
const b=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const page=b.contexts()[0].pages()[0];
const rpc=(name,payload={})=>page.evaluate(async([name,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,payload),[name,payload]);
const report={version,realApi:true,generate,passed:false,errors:[],progress:[]};
const save=()=>fs.writeFile(`../local-data/${version}-three-view-live.json`,JSON.stringify(report,null,2));
let before;
try{
 before=await rpc('bootstrap');
 if(!/[/\\]local-data[/\\]v121-/.test(before.project.root))throw Error('Refusing to test on a user project');
 if(before.busy || before.activeJob || before.review || !before.config.keySet)throw Error('Test desktop is not ready');
 report.project=before.project.root;report.model=before.config.model;
 await rpc('context.clear');await rpc('settings.save',{online:false});
 await page.getByLabel('给 AI 助手的消息').fill('帮我生成一个洛天依三视图');
 await page.getByRole('button',{name:'发送消息',exact:true}).click();
 await page.waitForFunction(()=>{const s=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');return !!s.state.review || !s.busy},null,{timeout:240000});
 let state=await rpc('bootstrap'),review=state.review;
 if(review?.name!=='generate' || review.generation.mode!=='qwen' || review.generation.references.length)throw Error('Expected direct Qwen T2I review: '+JSON.stringify({review,status:state.status,error:state.error}));
 if(state.project.assets.length!==before.project.assets.length || state.project.shots.length!==before.project.shots.length)throw Error('Agent created an unwanted asset');
 report.review={name:review.name,mode:review.generation.mode,references:review.generation.references,steps:review.generation.steps};
 await page.getByRole('button',{name:'审阅操作',exact:true}).click();
 await page.screenshot({path:`../docs/screenshots/${version}-three-view-review.png`});
 if(generate){
  const queue=await(await fetch('http://127.0.0.1:8188/queue')).json();
  if(queue.queue_running.length || queue.queue_pending.length)throw Error('Independent ComfyUI queue is busy');
  await page.getByLabel('分辨率 MP').fill('0.2');
  await page.getByRole('button',{name:'加入生成队列',exact:true}).click();
  await page.getByRole('button',{name:'任务与历史',exact:true}).click();
  state=await rpc('bootstrap');const job=state.project.tasks.at(-1);report.job=job.id;
  if(job.generation.mode!=='qwen' || job.generation.steps!==40)throw Error('Actual queued generation differs');
  const deadline=Date.now()+900000;
  while(Date.now()<deadline){
   state=await rpc('bootstrap');const task=state.project.tasks.find(t=>t.id===job.id);
   if(task.status==='running' && task.steps?.max && !report.progress.includes(task.steps.value))report.progress.push(task.steps.value);
   if(['failed','unknown','cancelled'].includes(task.status))throw Error(task.error || task.status);
   if(task.status==='completed' && state.activeJob!==job.id){report.output=task.raw.outputs[0];break;}
   await new Promise(resolve=>setTimeout(resolve,500));
  }
  if(!report.output || !report.progress.length)throw Error('No completed output with real step progress');
  const lib=await rpc('library.query',{kind:'image',source:'generated',limit:100});
  const row=lib.items.find(r=>r.file===report.output);
  if(!row || row.owners.length)throw Error('Generated result not retained unassigned in library');
  const original=await fs.readFile(path.join(report.project,report.output));
  await page.getByRole('button',{name:'图片库',exact:true}).click();
  const card=page.getByTestId('library-'+row.id);await card.waitFor();
  await card.getByRole('button',{name:/删除素材/}).click();await page.getByRole('button',{name:'移入回收站',exact:true}).click();
  if((await rpc('library.query',{kind:'image',source:'generated',limit:100})).items.some(r=>r.file===report.output))throw Error('Deleted result still in library');
  await page.getByRole('button',{name:'回收站',exact:true}).click();
  await page.getByTestId('library-'+row.id).getByRole('button',{name:'恢复素材',exact:true}).click();
  await page.getByRole('button',{name:'返回图片库',exact:true}).click();
  await page.getByTestId('library-'+row.id).waitFor();
  if(!(await fs.readFile(path.join(report.project,report.output))).equals(original))throw Error('Original bytes changed');
  await page.screenshot({path:`../docs/screenshots/${version}-generated-restored.png`});
  report.generatedDeleteRestore=true;
 }else await page.getByRole('button',{name:'取消生成',exact:true}).click();
 report.passed=true;console.log(JSON.stringify({passed:true,review:report.review,output:report.output,steps:report.progress}));
}catch(e){report.errors.push(String(e));console.error(String(e));process.exitCode=1;}
finally{
 await save();
 if(before){const current=await rpc('bootstrap');if(current.review)await rpc('review.respond',{id:current.review.id,accepted:false});await rpc('settings.save',{online:before.config.online});}
 await b.close();
}
