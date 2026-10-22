/** Explicit low-resolution real inference, including the two approved Qwen graphs. */
import {chromium} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
const version=process.env.XY_VALIDATION_VERSION || 'v110';
const browser=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const page=browser.contexts()[0].pages()[0];
const rpc=(command,payload={})=>page.evaluate(async([command,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload]);
const root=path.resolve(`../local-data/${version}-qwen-`+Date.now());
const report={project:root,tests:[],passed:false,errors:[]};
const save=()=>fs.writeFile(`../local-data/${version}-qwen-report.json`,JSON.stringify(report,null,2));
try{
 const queue=await(await fetch('http://127.0.0.1:8188/queue')).json();
 if(queue.queue_running.length || queue.queue_pending.length)throw Error('Preserve existing user ComfyUI tasks');
 const old=JSON.parse(await fs.readFile(`../local-data/${version}-progress-report.json`,'utf8'));
 const data=JSON.parse(await fs.readFile(path.join(old.project,'project.json'),'utf8'));
 await rpc('project.new',{path:root,title:'Qwen 正式工作流低规格验收'});
 const scene=await rpc('asset.add',{kind:'scenes',name:'Qwen 工作流验收',description:'安静的舞台'});
 const refs=await rpc('references.import',{paths:[path.join(old.project,data.scenes[0].image),path.join(old.project,data.characters[0].image)]});
 await page.getByRole('button',{name:'场景资产',exact:true}).click();
 for(const [name,overrides] of [
  ['图像编辑沿用主图',{mode:'qwen_edit',references:refs,edit_follow_source:true,qwen_int8:true,megapixels:.1,prompt:'以 <image1> 的舞台作为背景，将 <image2> 中的绿色玩具机器人放到舞台中央，保留舞台构图、灯光、机器人造型与颜色。'}],
  ['图像编辑自定义尺寸',{mode:'qwen_edit',references:refs,edit_follow_source:false,qwen_int8:true,ratio:'1:1',megapixels:.1,prompt:'以 <image1> 的舞台作为背景，将 <image2> 中的绿色玩具机器人放到舞台中央，保留舞台灯光和机器人造型，画面使用方形构图。'}],
  ['文生图BF16与16位PNG',{mode:'qwen',references:[],qwen_int8:false,ratio:'16:9',megapixels:.2,prompt:'An empty small concert stage, blue spotlights, a dark curtain, wide view.'}]
 ]){
  const defaults=await rpc('generation.defaults',{target:scene,mode:overrides.mode});
  const generation={...defaults,steps:16,seed:String(Date.now()%2147483647),...overrides};
  const dimensions=await rpc('generation.preview',{generation});
  const id=await rpc('generation.submit',{target:scene,generation});
  const record={name,id,generation,expected:dimensions,observed:[],barsVerified:0};report.tests.push(record);await save();
  const deadline=Date.now()+1200000;
  while(Date.now()<deadline){
   const observed=await page.evaluate(async id=>{
    const store=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');
    await new Promise(resolve=>requestAnimationFrame(resolve));
    return {task:JSON.parse(JSON.stringify(store.project.tasks.find(t=>t.id===id))),active:store.state.activeJob,error:store.connectionError || store.state.error,
     bars:[...document.querySelectorAll(`[data-task-id="${id}"] [role="progressbar"]`)].map(b=>({value:b.getAttribute('aria-valuenow'),text:b.getAttribute('aria-valuetext')}))};
   },id);
   const {task,bars}=observed;
   const key=`${task.status}:${task.node}:${task.progress}`;
   if(record.observed.at(-1)?.key!==key){record.observed.push({key,steps:task.steps,bars});await save();}
   if(observed.error)throw Error(observed.error);
   if(task.status==='running' && task.progress!==null && observed.active===id){
    if(bars.length<2 || bars.some(b=>Number(b.value)!==task.progress || !b.text.includes('步')))throw Error('UI progress did not match actual ComfyUI steps');
    record.barsVerified++;
   }
   if(['failed','unknown','cancelled'].includes(task.status))throw Error(task.error || task.status);
   if(task.status==='completed' && observed.active!==id){
    record.outputs=task.raw.outputs;record.status=task.status;
    if(!record.barsVerified)throw Error('No actual step progress observed');
    const asset=(await rpc('bootstrap')).project.assets.find(a=>a.id===scene);
    if(!asset.versions.some(v=>v.file===record.outputs[0]))throw Error('History lost original ownership');
    console.log(name+': real inference completed, '+record.barsVerified+' measured UI progress samples');await save();break;
   }
   await new Promise(r=>setTimeout(r,150));
  }
  if(record.status!=='completed')throw Error('Actual generation timed out');
 }
 await page.getByRole('button',{name:'图片库',exact:true}).click();await page.locator('.library-card').first().waitFor();
 await page.screenshot({path:`../docs/screenshots/${version}-qwen-results.png`});
 report.passed=true;
}catch(error){report.errors.push(String(error));process.exitCode=1;console.error(String(error));}
finally{await save();await browser.close();}
