/** Explicit billed/local inference acceptance; runs through the real desktop bridge. */
import {chromium} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
const browser=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const page=browser.contexts()[0].pages()[0];
const rpc=(name,args={})=>page.evaluate(async([name,args])=>await document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,args),[name,args]);
const state=()=>rpc('bootstrap');
const root=path.resolve('../local-data/v030-live-'+Date.now());
const report={project:root,tests:[],errors:[]};
const record=async name=>{await fs.writeFile('../local-data/v030-live-report.json',JSON.stringify(report,null,2));console.log(name)};
async function until(predicate,seconds=420){const limit=Date.now()+seconds*1000;while(Date.now()<limit){const s=await state();if(predicate(s))return s;await new Promise(r=>setTimeout(r,500));}throw Error('Timed out waiting for actual backend');}
try{
 await rpc('project.new',{path:root,title:'XY Studio v0.3 实际生成验收'});
 const actor=await rpc('asset.add',{kind:'characters',name:'桌面机器人',description:'一只桌上的红色玩具机器人'});
 const scene=await rpc('asset.add',{kind:'scenes',name:'蓝墙桌面',description:'木桌和蓝色墙面'});
 const shot=await rpc('asset.add',{kind:'shots',description:'小机器人举起手臂'});
 await rpc('asset.link',{id:shot,ids:[actor,scene]});
 const base={mode:'qwen',prompt:'A small red toy robot standing on a wooden desk, plain blue wall, soft daylight, detailed toy photography.',ratio:'16:9',megapixels:.1,seconds:.5,seed:'884031',steps:4,cinema:false,cinema_strength:.4,quad_lora:true,qwen_int8:true,styles:[],scale:1.5,references:[]};
 async function generate(name,target,overrides={}){
  const g={...base,...overrides};const start=Date.now();const id=await rpc('generation.submit',{target,generation:g});
  const observed=[];
  const s=await until(s=>{const j=s.project.tasks.find(t=>t.id===id);if(!j)return false;const key=[j.status,j.node,j.progress].join(':');if(observed.at(-1)!==key)observed.push(key);return ['completed','failed','unknown','cancelled'].includes(j.status) && s.activeJob!==id;});
  const job=s.project.tasks.find(t=>t.id===id);
  report.tests.push({name,id,target,generation:g,status:job.status,seconds:(Date.now()-start)/1000,outputs:job.raw.outputs,observed,error:job.error});await record(name+' '+job.status);
  if(job.status!=='completed')throw Error(name+': '+job.error);
  const item=[...s.project.assets,...s.project.shots].find(a=>a.id===target);
  if(!item.versions.some(v=>v.file===job.raw.outputs[0]))throw Error('Output not attached to original target');
  return item;
 }
 let image=await generate('Qwen 文生图',actor);
 const ref=image.imageFile;
 await generate('Qwen 图片编辑',actor,{mode:'qwen_edit',references:[ref],prompt:'将输入图中机器人的身体改为绿色，保留原构图、形状、光线和背景。'});
 await generate('Krea2 无 LoRA',scene,{mode:'krea'});
 for(const style of Object.keys((await state()).catalog.styles))await generate('Krea2 LoRA '+style,scene,{mode:'krea',styles:[style],steps:2});
 await generate('四视图 LoRA 开启',actor,{mode:'quad',references:[ref],prompt:'Create four views of the same robot: face close-up, front, side and back, plain background, consistent proportions.'});
 await generate('四视图 LoRA 关闭',actor,{mode:'quad',references:[ref],quad_lora:false,prompt:'A single consistent robot on the same desk.'});
 await generate('RFMSR 1.5 倍',actor,{mode:'upscale',references:[ref],steps:2});
 const h3={integrated_multimodal_description:'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced. [Shot 1] Static camera. A toy robot slowly raises one arm, retaining the desk and blue wall.',overall_soundscape:'Quiet indoor ambience.',non_diegetic_music:'None.'};
 for(const mode of ['h3_i2v','h3_ref','h3_t2v','h3_fl2v']){
  const prompt=mode==='h3_ref'?JSON.stringify({subject_definitions:'<Picture 1> is a red toy robot on a wooden desk.',summary:'A robot lifts its arm.',retention_analysis:'Preserve the robot and desk.',detailed_description:'[Shot 1] Static camera. The robot slowly raises one arm.',overall_soundscape:'Quiet room tone.',non_diegetic_music:'None.'}):JSON.stringify({...h3,integrated_multimodal_description:mode==='h3_t2v'?'[Shot 1] A red toy robot slowly raises one arm on a wooden desk against a plain blue wall. Static camera, soft daylight.':h3.integrated_multimodal_description});
  await generate(mode,shot,{mode,prompt,references:mode==='h3_t2v'?[]:mode==='h3_fl2v'?[ref,image.imageFile]:[ref],steps:2});
 }
 await generate('H3 电影 LoRA 开启',shot,{mode:'h3_i2v',prompt:JSON.stringify(h3),references:[ref],steps:2,cinema:true});
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2,{},{timeout:90000});
 await page.locator('.big-play').first().click();await page.waitForFunction(()=>document.querySelector('video').currentTime>.2);await page.getByRole('button',{name:'暂停视频',exact:true}).first().click();
 await page.screenshot({path:'../docs/screenshots/v030-live-storyboard.png'});
 // Real account model list, skill reading, multiple-round approval then generation.
 await rpc('models.refresh');await until(s=>!s.modelsBusy,60);report.models=(await state()).config.models;
 await rpc('settings.save',{online:false});
 await page.getByLabel('给 AI 助手的消息').fill('请新建名为“AI验收场景”的场景，并用 Krea2 生成一张无人的雨夜便利店场景图。使用工具提出操作，我会在界面逐项确认。不要只提供提示词。');
 await page.getByRole('button',{name:'发送消息',exact:true}).click();
 let approved=0,generated=false;
 for(let round=0;round<12;round++){
  const s=await until(s=>!!s.review || !s.busy,300);
  if(!s.review)break;
  await page.getByRole('button',{name:'审阅操作',exact:true}).click();
  if(s.review.name==='generate'){
   await page.getByLabel('分辨率 MP').fill('.1');await page.getByLabel('采样步数').fill('4');
   await page.getByRole('button',{name:'加入生成队列',exact:true}).click();generated=true;
  }else await page.getByRole('button',{name:'确认'+s.review.title,exact:true}).click();
  approved++;if(generated)break;
 }
 const s=await until(s=>!s.activeJob && !s.busy,420);
 const last=s.project.tasks.at(-1);
 if(!generated || last.status!=='completed')throw Error('DeepSeek confirmed creation-to-generation did not complete');
 report.agent={approved,status:last.status,target:last.targetId,skills:s.project.chat.flatMap(m=>m.activity || []).filter(a=>a.type==='skill')};
 await record('DeepSeek AI→审阅→实际生成 completed');
 await rpc('settings.save',{online:true});
 await page.getByLabel('给 AI 助手的消息').fill('请联网查询 Vue 3 的官方文档网址，只需要一句话和来源链接，不要创建或生成内容。');
 await page.getByRole('button',{name:'发送消息',exact:true}).click();
 const searched=await until(s=>!s.busy,300);
 report.search=searched.project.chat.at(-1);
 if(!report.search.activity.some(a=>a.type==='search'))throw Error('No real search evidence');
 await record('DeepSeek 实际联网 completed');
 await rpc('project.save');report.passed=true;await record('ALL REAL GENERATION TESTS PASSED');
}catch(e){report.errors.push(String(e));await record('FAILED '+String(e));process.exitCode=1;}
finally{await browser.close();}
