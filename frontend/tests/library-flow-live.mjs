/** Opt-in: real DeepSeek and low-resolution local ComfyUI inference. */
import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';import path from 'node:path';
const version=process.env.XY_VALIDATION_VERSION || 'v120-package';
const browser=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9227',{noDefaults:true});
const page=browser.contexts()[0].pages()[0];
const rpc=(command,payload={})=>page.evaluate(async([command,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload]);
const root=path.resolve(`../local-data/${version}-library-live-${Date.now()}`);
const report={version,project:root,tests:[],passed:false,errors:[]};
const save=()=>fs.writeFile(`../local-data/${version}-library-live-report.json`,JSON.stringify(report,null,2));
let before;
async function suggest(text,mode,refs){
 await page.getByLabel('给 AI 助手的消息').fill(text);await page.getByRole('button',{name:'发送消息',exact:true}).click();
 await page.waitForFunction(()=>{const s=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');return !!s.state.review || !s.busy},null,{timeout:240000});
 const state=await rpc('bootstrap'),review=state.review;
 if(review?.name!=='generate' || review.generation.mode!==mode)throw Error('Agent did not directly prepare '+mode+': '+(review?.name || state.status));
 if(JSON.stringify(review.generation.references)!==JSON.stringify(refs))throw Error('Agent input references differ from current attachments');
 await page.getByRole('button',{name:'审阅操作',exact:true}).click();return review.generation;
}
async function finish(record){
 const deadline=Date.now()+900000;record.measuredProgress=[];let previous=-1;
 while(Date.now()<deadline){
  const sample=await page.evaluate(id=>{
   const s=document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');const t=s.project.tasks.find(t=>t.id===id);
   return {task:JSON.parse(JSON.stringify(t)),active:s.state.activeJob,error:s.state.error,bars:[...document.querySelectorAll(`[data-task-id="${id}"] [role="progressbar"]`)].map(b=>b.getAttribute('aria-valuenow'))};
  },record.id);
  const t=sample.task;if(sample.error)throw Error(sample.error);
  if(t.status==='running' && t.node==='sample' && t.progress!==null && t.progress!==previous){
   if(!sample.bars.length || sample.bars.some(v=>v===null || Math.abs(Number(v)-t.progress)>.001))throw Error('Actual UI progress differs from backend');
   if(t.steps.max!==record.generation.steps)throw Error('Sampler step count differs');
   record.measuredProgress.push(t.steps.value);previous=t.progress;
  }
  if(['failed','unknown','cancelled'].includes(t.status))throw Error(t.error || t.status);
  if(t.status==='completed' && sample.active!==record.id){
   if(!record.measuredProgress.length)throw Error('No measured sampler progress observed');
   record.outputs=t.raw.outputs;record.status=t.status;
   const lib=await rpc('library.query',{kind:t.kind,source:'generated',limit:100});
   const row=lib.items.find(r=>r.file===record.outputs[0]);
   if(!row || row.owners.length || row.deletedOwner)throw Error('New result was adopted without user choice');
   record.libraryId=row.id;await save();console.log(record.name+': completed with real progress, unassigned result');return t;
  }
  await new Promise(r=>setTimeout(r,220));
 }
 throw Error('Real inference timed out');
}
try{
 before=await rpc('bootstrap');if(!before.config.keySet || before.activeJob || before.busy)throw Error('QA window must be idle with saved DeepSeek key');
 const queue=await(await fetch('http://127.0.0.1:8188/queue')).json();
 if(queue.queue_running.length || queue.queue_pending.length)throw Error('ComfyUI is in use; preserve independent tasks');
 await rpc('project.new',{path:root,title:'素材库真实生成与选用验收'});await rpc('settings.save',{online:false});
 const old=JSON.parse(await fs.readFile('../local-data/v111-original-history.json','utf8'));
 const graph=old['f6980b0a-c9f7-4c5d-9178-c64e4cc8c0c8'].prompt[2];
 const comfy='D:/AI/CGMi_ComfyUI_Helper_v1.2/CGMi_ComfyUI_Helper_v1.2/ComfyUI';
 const sourceA=path.join(root,'初音未来参考.png'),sourceB=path.join(root,'舞台参考.png');
 await fs.copyFile(path.join(comfy,'input',graph.ref0.inputs.image),sourceA);await fs.copyFile(path.join(comfy,'input',graph.ref1.inputs.image),sourceB);
 const refs=await rpc('library.import',{kind:'image',paths:[sourceA,sourceB]});
 for(const file of refs)await rpc('context.add_media',{file});
 await page.getByRole('button',{name:'图片库',exact:true}).click();
 const suggested=await suggest('把第一张图中的初音未来放进第二张舞台图，保持人物服装、舞台结构和灯光，生成一张合成图片。', 'qwen_edit',refs);
 if(suggested.steps!==40 || !suggested.qwen_int8)throw Error('Qwen review defaults regressed');
 await page.getByLabel('编辑输出尺寸').selectOption('custom');await page.getByLabel('分辨率 MP').fill('0.2');
 await page.screenshot({path:`../docs/screenshots/${version}-image-review.png`});
 await page.getByRole('button',{name:'加入生成队列',exact:true}).click();
 await page.getByRole('button',{name:'任务与历史',exact:true}).click();
 let state=await rpc('bootstrap');let task=state.project.tasks.at(-1);
 const imageRecord={name:'Real Agent image generation',id:task.id,generation:task.generation};report.tests.push(imageRecord);await save();
 task=await finish(imageRecord);const image=task.results[0].file;
 state=await rpc('bootstrap');if(state.project.assets.length || state.project.shots.length)throw Error('Image generation created an asset or shot');
 await page.getByRole('button',{name:'图片库',exact:true}).click();await page.getByLabel('图片来源筛选').selectOption('generated');
 await page.locator('.library-card').waitFor();await page.screenshot({path:`../docs/screenshots/${version}-generated-images.png`});
 await page.getByRole('button',{name:'角色资产',exact:true}).click();await page.getByRole('button',{name:'添加角色',exact:true}).click();
 await page.getByLabel('图片来源筛选').selectOption('generated');
 await page.getByRole('button',{name:'选用这张图片',exact:true}).click();await page.getByLabel('素材名称').fill('初音未来');await page.getByRole('button',{name:'确认添加',exact:true}).click();
 state=await rpc('bootstrap');const actor=state.project.assets[0];if(actor.imageFile!==image || actor.versions.length!==1)throw Error('Manual role adoption failed');
 await page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true}).click();
 if(await page.getByLabel('生成提示词').inputValue()!==task.generation.prompt || await page.getByRole('dialog').locator('.reference-thumb').count()!==2)throw Error('New attempt lost original input prompt or references');
 const restored=await rpc('generation.defaults',{mode:'qwen_edit'});if(JSON.stringify(restored.references)!==JSON.stringify(refs))throw Error('Edited result replaced original references');
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await rpc('context.clear');await rpc('context.add_media',{file:image});
 await suggest('让这张图片动起来，镜头缓慢推进，初音未来轻轻挥手，直接生成一个短视频。','h3_i2v',[image]);
 await page.getByLabel('分辨率 MP').fill('0.1');await page.getByLabel('H3 时长').fill('2');
 await page.screenshot({path:`../docs/screenshots/${version}-direct-video-review.png`});
 await page.getByRole('button',{name:'加入生成队列',exact:true}).click();await page.getByRole('button',{name:'任务与历史',exact:true}).click();
 state=await rpc('bootstrap');task=state.project.tasks.at(-1);const videoRecord={name:'Real Agent direct image-to-video',id:task.id,generation:task.generation};report.tests.push(videoRecord);await save();
 task=await finish(videoRecord);const video=task.results[0].file;
 state=await rpc('bootstrap');if(state.project.shots.length || state.project.assets.length!==1 || state.project.assets[0].versions.length!==1)throw Error('Video generation auto-adopted result or generated an extra image');
 if(state.project.tasks.length!==2)throw Error('Agent generated unexpected extra tasks');
 await page.getByRole('button',{name:'视频库',exact:true}).click();await page.locator('.library-card').waitFor();await page.screenshot({path:`../docs/screenshots/${version}-generated-videos.png`});
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();await page.getByRole('button',{name:'添加镜头',exact:true}).first().click();
 await page.getByRole('button',{name:'添加视频',exact:true}).click();await page.getByRole('button',{name:'选用这段视频',exact:true}).click();await page.getByRole('button',{name:'确认添加',exact:true}).click();
 state=await rpc('bootstrap');if(state.project.shots[0].videoFile!==video || state.project.shots[0].duration<=0)throw Error('Video adoption or duration failed');
 const shot=state.project.shots[0];await rpc('asset.use_media',{id:shot.id,file:image});await rpc('asset.link',{id:shot.id,ids:[actor.id]});
 await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2,null,{timeout:120000});
 await page.locator('video').first().evaluate(v=>v.play());await page.waitForFunction(()=>document.querySelector('video').currentTime>.15);await page.locator('video').first().evaluate(v=>v.pause());
 await page.screenshot({path:`../docs/screenshots/${version}-adopted-storyboard.png`});
 report.playback=true;report.model=state.config.model;report.passed=true;
}catch(e){report.errors.push(String(e));process.exitCode=1;console.error(String(e));}
finally{
 await save();if(before){const current=await rpc('bootstrap');if(current.review)await rpc('review.respond',{id:current.review.id,accepted:false});await rpc('settings.save',{online:before.config.online});}
 await browser.close();
}
