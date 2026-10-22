/** Real DeepSeek -> unchanged default review -> ComfyUI, then manual defaults.
 * Explicit opt-in script: creates a dedicated project and uses local inference.
 */
import {chromium} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
const version=process.env.XY_VALIDATION_VERSION || 'v111';
const browser=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const page=browser.contexts()[0].pages()[0];
const rpc=(command,payload={})=>page.evaluate(async([command,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload]);
const root=path.resolve(`../local-data/${version}-seed-live-${Date.now()}`);
const report={project:root,tests:[],passed:false,errors:[]};
const save=()=>fs.writeFile(`../local-data/${version}-seed-live-report.json`,JSON.stringify(report,null,2));
let before;
async function waitJob(record){
 const deadline=Date.now()+900000;
 record.measuredProgress=0;
 while(Date.now()<deadline){
  const sample=await page.evaluate(async id=>{
   await new Promise(resolve=>requestAnimationFrame(resolve));
   const store=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');
   return {task:JSON.parse(JSON.stringify(store.project.tasks.find(t=>t.id===id))),active:store.state.activeJob,error:store.state.error,bars:[...document.querySelectorAll(`[data-task-id="${id}"] [role="progressbar"]`)].map(b=>b.getAttribute('aria-valuenow'))};
  },record.id);
  const {task}=sample;
  if(sample.error)throw Error(sample.error);
  if(task.status==='running' && task.node==='sample' && task.progress!==null && sample.active===record.id){
   if(task.steps.max!==40 || sample.bars.length<2 || sample.bars.some(v=>Number(v)!==task.progress))throw Error('Actual 40-step UI progress mismatch');
   record.measuredProgress++;
  }
  if(['failed','unknown','cancelled'].includes(task.status))throw Error(task.error || task.status);
  if(task.status==='completed' && sample.active!==record.id){
   if(!record.measuredProgress)throw Error('No real progress measured');
   if(task.generation.seed!==record.generation.seed || task.generation.steps!==40)throw Error('Confirmed parameters changed during execution');
   record.outputs=task.raw.outputs;record.status=task.status;
   const state=await rpc('bootstrap');
   if(!state.project.assets.find(a=>a.id===record.target).versions.some(v=>v.file===record.outputs[0]))throw Error('Result detached from original card');
   await save();console.log(record.name+': real 40-step inference completed');return;
  }
  await new Promise(r=>setTimeout(r,180));
 }
 throw Error('Generation timeout');
}
try{
 before=await rpc('bootstrap');
 if(!before.config.keySet || before.activeJob || before.busy)throw Error('QA app must be idle with a saved DeepSeek key');
 const queue=await(await fetch('http://127.0.0.1:8188/queue')).json();
 if(queue.queue_running.length || queue.queue_pending.length)throw Error('Preserve user ComfyUI tasks');
 const history=JSON.parse(await fs.readFile('../local-data/v111-original-history.json','utf8'));
 const graph=history['f6980b0a-c9f7-4c5d-9178-c64e4cc8c0c8'].prompt[2];
 const comfy=process.env.XY_COMFY_ROOT || 'D:/AI/CGMi_ComfyUI_Helper_v1.2/CGMi_ComfyUI_Helper_v1.2/ComfyUI';
 await rpc('project.new',{path:root,title:'Agent 默认种子真实验收'});
 await rpc('settings.save',{online:false});
 const actor=await rpc('asset.add',{kind:'characters',name:'初音未来',description:'青绿色双马尾虚拟歌姬'});
 const scene=await rpc('asset.add',{kind:'scenes',name:'舞台',description:'冷色灯光演唱会舞台'});
 const [actorRef]=await rpc('asset.import',{id:actor,paths:[path.join(comfy,'input',graph.ref0.inputs.image)]});
 const [sceneRef]=await rpc('asset.import',{id:scene,paths:[path.join(comfy,'input',graph.ref1.inputs.image)]});
 await rpc('selection',{id:scene,pin:true});
 await page.getByRole('button',{name:'场景资产',exact:true}).click();
 await page.getByLabel('给 AI 助手的消息').fill('请对选中的舞台生成 Qwen 编辑新版本，不创建任何新条目。现有参考图顺序必须为：第一张初音未来角色图，第二张舞台图。调用图片编辑工具供我审阅。采用以下完整提示词：\n'+graph.encode.inputs.prompt);
 await page.getByRole('button',{name:'发送消息',exact:true}).click();
 await page.waitForFunction(()=>{const s=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');return !!s.state.review || !s.busy},null,{timeout:240000});
 const ready=await rpc('bootstrap');
 if(ready.review?.name!=='generate' || ready.review.targetId!==scene)throw Error('Agent did not prepare the existing scene edit');
 const generation=ready.review.generation;
 if(generation.mode!=='qwen_edit' || generation.seed==='42' || generation.steps!==40 || !generation.edit_follow_source || !generation.qwen_int8)throw Error('Default parameters are incorrect');
 if(JSON.stringify(generation.references)!==JSON.stringify([actorRef,sceneRef]))throw Error('Agent reference order differs from request');
 report.model=ready.config.model;
 await page.getByRole('button',{name:'审阅操作',exact:true}).click();
 await page.getByLabel('生成提示词').waitFor();
 if(await page.getByLabel('种子',{exact:true}).inputValue()!==generation.seed || await page.getByLabel('采样步数',{exact:true}).inputValue()!=='40')throw Error('Review UI differs from backend');
 await page.screenshot({path:`../docs/screenshots/${version}-agent-default-review.png`});
 await page.getByRole('button',{name:'加入生成队列',exact:true}).click();
 const task=(await rpc('bootstrap')).project.tasks.at(-1);
 const record={name:'Agent unchanged defaults',id:task.id,target:scene,generation};
 report.tests.push(record);await save();await waitJob(record);
 // Exercise the manual dialog's new defaults against the current real result.
 // Leave its seed, steps, model and source-size selection untouched.
 await page.getByTestId('asset-'+scene).getByRole('button',{name:'生成新版本',exact:true}).click();
 await page.getByLabel('生成提示词').fill('保留当前舞台上的初音未来人物、服装、位置、灯光和构图，清晰渲染全图，不添加人物。');
 const manualSeed=await page.getByLabel('种子',{exact:true}).inputValue();
 if(manualSeed==='42' || manualSeed===generation.seed || await page.getByLabel('采样步数',{exact:true}).inputValue()!=='40')throw Error('Manual dialog still uses a fixed seed');
 await page.getByRole('button',{name:'加入生成队列',exact:true}).click();
 const second=(await rpc('bootstrap')).project.tasks.at(-1);
 if(second.generation.seed!==manualSeed)throw Error('Manual confirmed seed changed');
 const r2={name:'Manual new default seed',id:second.id,target:scene,generation:second.generation};
 report.tests.push(r2);await save();await waitJob(r2);
 await page.getByTestId('asset-'+scene).getByRole('button',{name:/历史版本/}).click();
 await page.locator('.version-card').first().waitFor();
 await page.screenshot({path:`../docs/screenshots/${version}-seed-history.png`});
 await page.keyboard.press('Escape');
 report.passed=true;
}catch(e){report.errors.push(String(e));process.exitCode=1;console.error(String(e));}
finally{
 await save();
 if(before){const current=await rpc('bootstrap');if(current.review)await rpc('review.respond',{id:current.review.id,accepted:false});await rpc('settings.save',{online:before.config.online});}
 await browser.close();
}
