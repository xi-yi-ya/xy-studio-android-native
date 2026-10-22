/** Real desktop bridge and disk files; no browser mock or simulated completion. */
import {test,expect,chromium,type Browser,type Page} from '@playwright/test';
import fs from 'node:fs/promises';import path from 'node:path';
let browser:Browser,page:Page,original:string,root:string,file:string;
const version=process.env.XY_VALIDATION_VERSION || 'v120';
const legacy=path.resolve(process.env.XY_LEGACY || '../local-data/XY-Studio-v030-compat');
test.describe.configure({mode:'serial'});
const rpc=(command:string,payload:Record<string,unknown>={})=>page.evaluate(async([command,payload])=>(document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload] as const);
const state=()=>rpc('bootstrap') as Promise<any>;
test.beforeAll(async()=>{
 browser=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});page=browser.contexts()[0]!.pages()[0]!;
 original=(await state()).project.root;root=path.resolve('../local-data',`${version}-library-ui-${Date.now()}`);
 await rpc('project.new',{path:root,title:'素材库选择流程验收'});
});
test.afterAll(async()=>{const s=await state();if(s.review)await rpc('review.respond',{id:s.review.id,accepted:false});if(original)await rpc('project.open',{path:original});await browser.close();});
test.afterEach(async()=>{expect((await state()).error).toBe('');});
test('empty pickers guide generation and global entries survive collapsed AI',async()=>{
 await page.getByRole('button',{name:'角色资产',exact:true}).click();await page.getByRole('button',{name:'添加角色',exact:true}).click();
 await expect(page.getByText('图片库还没有图片',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'确认添加',exact:true})).toBeDisabled();
 await page.getByRole('dialog').getByRole('button',{name:'生成图片',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText('结果保存到图片库');await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await page.getByRole('button',{name:'收起 AI 助手',exact:true}).click();
 await expect(page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true})).toBeVisible();
 await expect(page.locator('.topbar').getByRole('button',{name:'生成视频',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'展开 AI 助手',exact:true}).click();
 await page.getByRole('button',{name:'视频库',exact:true}).click();await expect(page.getByText('视频库还没有视频',{exact:true})).toBeVisible();
});
test('button attachment works and all drag or legacy file-drop events do nothing',async()=>{
 await page.getByRole('button',{name:'图片库',exact:true}).click();
 const source=path.join(legacy,'assets/b1463e53334345328a91dc047816aec3.png');
 await rpc('library.import',{kind:'image',paths:[source]});
 await page.getByRole('button',{name:'刷新图片库',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(1);
 const result=await rpc('library.query',{kind:'image'}) as any;file=result.items[0].file;
 expect((await state()).project.assets).toHaveLength(0);
 await page.getByRole('button',{name:'发送给 AI',exact:true}).click();
 await expect(page.locator('.media-attachment img')).toHaveCount(1);
 expect((await state()).mediaContext.map((m:any)=>m.file)).toEqual([file]);
 await page.getByRole('button',{name:/移除AI素材引用/}).click();expect((await state()).mediaContext).toEqual([]);
 const prevented=await page.evaluate(source=>{
  window.dispatchEvent(new CustomEvent('xy-files-dropped',{detail:{paths:[source],x:20,y:20}}));
  return ['dragstart','dragover','drop'].map(type=>{
   const event=new DragEvent(type,{bubbles:true,cancelable:true,dataTransfer:new DataTransfer()});
   document.querySelector('.chat-composer')!.dispatchEvent(event);return event.defaultPrevented;
  });
 },source);
 expect(prevented).toEqual([true,true,true]);
 expect((await state()).mediaContext).toEqual([]);
 expect((await rpc('library.query',{kind:'image'}) as any).total).toBe(1);
 await expect(page.locator('[draggable="true"]')).toHaveCount(0);
});

test('library deletion is cancellable, persistent, removes AI reference and restores identity',async()=>{
 const before=(await rpc('library.query',{kind:'image'}) as any).items[0];
 const bytes=await fs.readFile(path.join(root,file));
 await page.getByRole('button',{name:'发送给 AI',exact:true}).click();
 await page.getByRole('button',{name:/删除素材/}).click();
 await expect(page.getByRole('dialog')).toContainText('不释放磁盘空间');
 await page.getByRole('button',{name:'保留素材',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(1);
 await page.getByRole('button',{name:/删除素材/}).click();
 await page.getByRole('button',{name:'移入回收站',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(0);
 expect((await state()).mediaContext).toEqual([]);
 expect(await fs.readFile(path.join(root,file))).toEqual(bytes);
 await rpc('project.new',{path:root+'-reopen',title:'重新打开测试'});await rpc('project.open',{path:root});
 expect((await rpc('library.query',{kind:'image'}) as any).total).toBe(0);
 await page.getByRole('button',{name:'图片库',exact:true}).click();
 await page.getByRole('button',{name:'回收站',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(1);
 await page.screenshot({path:`../docs/screenshots/${version}-recycle-bin.png`});
 await page.getByRole('button',{name:'恢复素材',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(0);
 await page.getByRole('button',{name:'返回图片库',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(1);
 expect((await rpc('library.query',{kind:'image'}) as any).items[0].id).toBe(before.id);
});
test('manual adoption retains names and prevents accidental replacement',async()=>{
 await page.getByRole('button',{name:'角色资产',exact:true}).click();await page.getByRole('button',{name:'添加角色',exact:true}).click();
 await page.getByRole('button',{name:'选用这张图片',exact:true}).first().click();await page.getByRole('button',{name:'确认添加',exact:true}).click();
 const s=await state();expect(s.project.assets).toHaveLength(1);const actor=s.project.assets[0];
 const row=(await rpc('library.query',{kind:'image'}) as any).items[0];expect(actor.name).toBe(row.name);
 await page.getByTestId('asset-'+actor.id).getByRole('button',{name:'替换图片',exact:true}).click();
 await page.getByRole('button',{name:'选用这张图片',exact:true}).first().click();await page.getByRole('button',{name:'取消添加',exact:true}).click();
 expect((await state()).project.assets[0].imageFile).toBe(file);
 await page.screenshot({path:`../docs/screenshots/${version}-simple-assets.png`});
});

test('current role image cannot be deleted from the library',async()=>{
 await page.getByRole('button',{name:'图片库',exact:true}).click();
 await page.getByRole('button',{name:/删除素材/}).click();
 await expect(page.getByRole('button',{name:'移入回收站',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'保留素材',exact:true}).click();
 expect((await rpc('library.query',{kind:'image'}) as any).total).toBe(1);
});
test('Agent direct video review shows its input and rejects without generating image or shot',async()=>{
 const s=await state();const bundle=path.join(root,'direct-video.json');
 await fs.writeFile(bundle,JSON.stringify({project_id:s.project.id,message:{role:'assistant',content:'请确认视频参数。',tool_calls:[{id:'video',type:'function',function:{name:'generate',arguments:JSON.stringify({mode:'h3_i2v',prompt:'integrated_multimodal_description: A slow shot.\noverall_soundscape: N/A\nnon_diegetic_music: N/A',references:[file]})}}]}}));
 await rpc('agent.import',{path:bundle});await page.getByRole('button',{name:'审阅操作',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText('生成视频 · 参数审阅');
 await expect(page.locator('.reference-thumb img')).toHaveCount(1);
 await expect.poll(()=>page.locator('.reference-thumb img').evaluate((img:HTMLImageElement)=>img.naturalWidth)).toBeGreaterThan(0);
 await page.getByRole('button',{name:'放大参考图1',exact:true}).click();await expect(page.locator('.reference-large')).toBeVisible();await page.keyboard.press('Escape');
 await expect(page.getByRole('dialog')).toContainText('生成视频 · 参数审阅');
 await page.screenshot({path:`../docs/screenshots/${version}-video-review.png`});
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 expect((await state()).project.shots).toHaveLength(0);expect((await state()).project.tasks).toHaveLength(0);
});
test('edit references and prompt survive new attempts, and empty search differs from empty library',async()=>{
 await rpc('queue.toggle');
 const g=await rpc('generation.defaults',{mode:'qwen_edit'}) as any;g.prompt='保留人物，改变背景灯光';g.references=[file];
 await rpc('generation.submit',{generation:g});const j=(await state()).project.tasks.at(-1);await rpc('task.cancel',{id:j.id});
 await page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true}).click();
 await expect(page.getByLabel('生成提示词')).toHaveValue(g.prompt);await expect(page.getByRole('dialog').locator('.reference-thumb img')).toHaveCount(1);
 await page.getByRole('button',{name:'移除参考图',exact:true}).click();await expect(page.locator('.reference-thumb')).toHaveCount(0);
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await page.getByRole('button',{name:'任务与历史',exact:true}).click();await page.getByRole('button',{name:'再次生成',exact:true}).click();
 await expect(page.getByLabel('生成提示词')).toHaveValue(g.prompt);await expect(page.getByRole('dialog').locator('.reference-thumb img')).toHaveCount(1);
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await page.getByRole('button',{name:'图片库',exact:true}).click();await page.getByLabel('搜索图片资产').fill('找不到这个素材');
 await expect(page.getByText('没有找到匹配的图片',{exact:true})).toBeVisible();await expect(page.getByText('图片库还没有图片',{exact:true})).toHaveCount(0);
 await page.getByRole('button',{name:'清除筛选',exact:true}).click();await expect(page.locator('.library-card')).toHaveCount(1);
});

test('missing original reference is shown explicitly and cannot create a new task',async()=>{
 const originalFile=path.resolve(root,file);
 expect(path.relative(root,originalFile).startsWith('..')).toBe(false);
 await fs.unlink(originalFile); // Only the unique file imported into this test project.
 await page.getByRole('button',{name:'任务与历史',exact:true}).click();
 await page.getByRole('button',{name:'再次生成',exact:true}).click();
 await expect(page.getByRole('dialog').getByText('原文件缺失，请重新选择',{exact:true})).toBeVisible();
 await expect(page.getByRole('dialog').getByRole('button',{name:'放大参考图1',exact:true})).toBeDisabled();
 const before=await state();const g=await rpc('generation.defaults',{mode:'qwen_edit'});
 await expect(rpc('generation.submit',{generation:g})).rejects.toThrow('参考图不存在');
 expect((await state()).project.tasks).toHaveLength(before.project.tasks.length);
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
});
