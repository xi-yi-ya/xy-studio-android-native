/** Requires a real XY Studio --debug-port 9225. There is no mock browser server. */
import {test,expect,chromium, type Browser,type Page} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';
let browser:Browser,page:Page,root:string,original:string;
let actor:string,scene:string,shot:string;
const legacyRoot=path.resolve(process.env.XY_LEGACY || '../local-data/XY-Studio-v030-compat');
const validationVersion=process.env.XY_VALIDATION_VERSION || 'v033';
test.describe.configure({mode:'serial'});
async function rpc(command:string,payload:Record<string,unknown>={}){
 return page.evaluate(async([command,payload])=>await (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command,payload),[command,payload] as const);
}
async function state(){return rpc('bootstrap') as Promise<any>}
test.beforeAll(async()=>{
 browser=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
 page=browser.contexts()[0]!.pages()[0]!;
 await page.reload();
 await expect(page.getByRole('button',{name:/保存项目/})).toBeVisible();
 original=(await state()).project.root;
 root=path.resolve('../local-data','v030-ui-'+Date.now());
 await rpc('project.new',{path:root,title:'Vue 真实桌面验收'});
});
test.afterAll(async()=>{if(original)await rpc('project.open',{path:original});await browser?.close()});
test.afterEach(async()=>{
 expect(await page.evaluate(()=>(document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('studio').connectionError)).toBe('');
});
test('new empty project, role and scene adoption and name edits persist',async()=>{
 const reference=path.join(legacyRoot,'assets/b1463e53334345328a91dc047816aec3.png');
 await rpc('library.import',{kind:'image',paths:[reference]});
 for(const [nav,name] of [['角色资产','Vue 测试角色'],['场景资产','Vue 测试场景']]){
  await page.getByRole('button',{name:nav,exact:true}).click();
  await page.getByRole('button',{name:nav==='角色资产'?'添加角色':'添加场景',exact:true}).click();
  await page.getByRole('button',{name:'选用这张图片',exact:true}).first().click();
  await page.getByLabel('素材名称',{exact:true}).fill(name!);
  await expect(page.getByLabel('描述',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'确认添加',exact:true}).click();
 }
 actor=(await state()).project.assets.find((a:any)=>a.kind==='characters').id;
 scene=(await state()).project.assets.find((a:any)=>a.kind==='scenes').id;
 expect(JSON.parse(await fs.readFile(path.join(root,'project.json'),'utf8')).schema).toBe(1);
 await page.getByRole('button',{name:'角色资产',exact:true}).click();
 const card=page.getByTestId('asset-'+actor);await card.click({button:'right'});
 await page.getByRole('menuitem',{name:'修改名称'}).click();
 await page.getByLabel('名称',{exact:true}).fill('Vue 角色改名');
 await page.getByRole('button',{name:'保存修改',exact:true}).click();
 expect((await state()).project.assets.find((a:any)=>a.id===actor).name).toBe('Vue 角色改名');
 await expect(card.locator('.asset-description')).toHaveCount(0);
});

test('double click image, zoom, history and right-click context',async()=>{
 const card=page.getByTestId('asset-'+actor);
 await card.locator('.asset-image').dblclick();await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:'放大图片',exact:true}).click();await expect(page.locator('.preview-toolbar')).toContainText('125%');
 await page.keyboard.press('Escape');
 await card.getByRole('button',{name:/历史版本/}).click();await expect(page.locator('.version-card')).toHaveCount(1);
 await page.getByRole('button',{name:'设为当前版本',exact:true}).click();await page.keyboard.press('Escape');
 await card.click({button:'right'});await page.getByRole('menuitem',{name:'发送给 AI'}).click();
 await expect(page.locator('.context-banner')).toContainText('Vue 角色改名');
 expect((await state()).contextIds).toContain(actor);
});
test('role and scene images toggle selection while menus and preview preserve context',async()=>{
 for(const [nav,id] of [['角色资产',actor],['场景资产',scene]]){
  await page.getByRole('button',{name:nav,exact:true}).click();
  await rpc('selection',{id:null});
  const card=page.getByTestId('asset-'+id),image=card.locator('.asset-image');
  await image.click();await expect(card).toHaveClass(/selected/);expect((await state()).selectedId).toBe(id);
  await image.click();await expect(card).not.toHaveClass(/selected/);expect((await state()).selectedId).toBeNull();
  await image.click();await card.getByRole('button',{name:/更多操作/}).click();
  expect((await state()).selectedId).toBe(id);await page.keyboard.press('Escape');
  await image.dblclick();await expect(page.getByRole('dialog')).toBeVisible();expect((await state()).selectedId).toBe(id);
  await page.keyboard.press('Escape');await image.click();expect((await state()).selectedId).toBeNull();
 }
});
test('shot numbering, real associations, timeline, folding and media mode boundaries',async()=>{
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();
 await page.getByRole('button',{name:'添加镜头',exact:true}).first().click();
 shot=(await state()).project.shots[0].id;
 await expect(page.getByTestId('shot-'+shot)).toContainText('分镜 1');
 await page.getByRole('button',{name:'关联镜头1素材',exact:true}).click();
 await page.locator('.link-option').first().click();await page.locator('.link-option').nth(1).click();
 await page.getByRole('button',{name:'保存关联',exact:true}).click();
 expect((await state()).project.shots[0].assetIds).toEqual([actor,scene]);
 const card=page.getByTestId('shot-'+shot);
 await rpc('asset.import',{id:shot,paths:[path.join(legacyRoot,'assets/b1463e53334345328a91dc047816aec3.png')]});
 await rpc('selection',{id:null});
 await card.locator('.shot-image').click();await expect(card).toHaveClass(/selected/);
 await card.locator('.shot-image').click();await expect(card).not.toHaveClass(/selected/);expect((await state()).selectedId).toBeNull();
 await card.getByRole('button',{name:'选择素材Vue 角色改名',exact:true}).click();expect((await state()).selectedId).toBe(actor);
 await card.getByRole('button',{name:'选择素材Vue 角色改名',exact:true}).click();expect((await state()).selectedId).toBeNull();
 await page.getByRole('button',{name:'折叠镜头1',exact:true}).click();await expect(page.getByTestId('shot-'+shot).locator('.shot-body')).toHaveCount(0);
 await page.getByRole('button',{name:/定位镜头1/}).click();await expect(page.getByTestId('shot-'+shot).locator('.shot-body')).toBeVisible();
 await page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true}).click();
 const imageModes=await page.getByLabel('生成工作流').locator('option').evaluateAll(o=>o.map(v=>(v as HTMLOptionElement).value));
 expect(imageModes).toContain('upscale');expect(imageModes.every(v=>!v.startsWith('h3'))).toBeTruthy();
 await page.getByLabel('生成工作流').selectOption('upscale');await expect(page.getByLabel('放大倍数')).toBeVisible();await expect(page.getByLabel('H3 时长')).toHaveCount(0);
 await expect(page.getByLabel('采样步数',{exact:true})).toHaveValue('15');
 await page.getByLabel('生成工作流').selectOption('qwen');await expect(page.getByLabel('采样步数',{exact:true})).toHaveValue('40');
 await page.getByLabel('采样步数',{exact:true}).fill('24');
 await page.getByLabel('生成工作流').selectOption('krea');await expect(page.getByLabel('采样步数',{exact:true})).toHaveValue('8');
 await page.getByLabel('生成工作流').selectOption('qwen');await expect(page.getByLabel('采样步数',{exact:true})).toHaveValue('24');
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await page.locator('.topbar').getByRole('button',{name:'生成视频',exact:true}).click();
 const videoModes=await page.getByLabel('生成工作流').locator('option').evaluateAll(o=>o.map(v=>(v as HTMLOptionElement).value));
 expect(videoModes).toHaveLength(4);expect(videoModes.every(v=>v.startsWith('h3'))).toBeTruthy();
 await expect(page.getByLabel('H3 时长')).toBeVisible();await expect(page.getByLabel('放大倍数')).toHaveCount(0);
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
});
test('queue parameters and cancellation persist, last prompt restored, no fake progress',async()=>{
 await rpc('queue.toggle');
 await page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true}).click();
 await expect(page.getByLabel('采样步数',{exact:true})).toHaveValue('40');
 const initialSeed=await page.getByLabel('种子',{exact:true}).inputValue();
 await page.getByRole('button',{name:'换一个随机种子',exact:true}).click();
 await expect(page.getByLabel('种子',{exact:true})).not.toHaveValue(initialSeed);
 await page.getByLabel('采样步数',{exact:true}).fill('0');
 await expect(page.locator('.form-note')).toContainText('40 步');
 await page.getByLabel('生成提示词').fill('界面测试提示词，实际加入暂停队列');await page.getByLabel('种子',{exact:true}).fill('9223372036854775807');
 await page.getByRole('button',{name:'加入生成队列',exact:true}).click();
 let s=await state();expect(s.project.tasks[0].status).toBe('new');expect(s.project.tasks[0].progress).toBeNull();expect(s.project.tasks[0].generation.seed).toBe('9223372036854775807');
 expect(s.project.tasks[0].generation.steps).toBe(40);
 await expect(page.locator('.active-generation').getByRole('progressbar')).toBeVisible();
 await expect(page.locator('.active-generation').getByRole('progressbar')).not.toHaveAttribute('aria-valuenow');
 await expect(page.locator('.active-generation')).toContainText('等待执行 · 队列已暂停');
 await page.getByRole('button',{name:'任务与历史',exact:true}).click();
 for(const bar of await page.getByRole('progressbar').all())await expect(bar).not.toHaveAttribute('aria-valuenow');
 await page.getByRole('button',{name:'取消',exact:true}).click();expect((await state()).project.tasks[0].status).toBe('cancelled');
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();await page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true}).click();
 await expect(page.getByLabel('生成提示词')).toHaveValue('界面测试提示词，实际加入暂停队列');await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await page.getByRole('button',{name:/保存项目/}).click();
 await rpc('project.open',{path:original});await rpc('project.open',{path:root});
 s=await state();expect(s.project.assets).toHaveLength(2);expect(s.project.shots[0].assetIds).toEqual([actor,scene]);expect(s.project.tasks[0].status).toBe('cancelled');
});
test('old real H3 video plays, seeks and retains history in its original shot',async()=>{
 await rpc('project.open',{path:legacyRoot});
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();
 const video=page.locator('video').first();await expect(video).toBeVisible();
 await page.waitForFunction(()=>document.querySelector('video')!.readyState>=2);
 const before=(await state()).project.shots.length;
 await page.locator('.big-play').first().click();await page.waitForFunction(()=>document.querySelector('video')!.currentTime>.2);
 await page.getByRole('button',{name:'暂停视频',exact:true}).first().click();
 await page.getByLabel('视频进度',{exact:true}).first().fill('1');
 expect(await video.evaluate(v=>v.currentTime)).toBeGreaterThan(.9);
 expect(await video.evaluate(v=>v.error)).toBeNull();
 await page.getByTestId('shot-'+(await state()).project.shots[0].id).getByRole('button',{name:/历史版本/}).nth(1).click();
 expect((await state()).project.shots.length).toBe(before);await expect(page.locator('.inline-history')).toBeVisible();
});
test('late events from a detached video do not break the next project',async()=>{
 await rpc('project.open',{path:legacyRoot});
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('video')!.readyState>=2);
 const oldDuration=await page.locator('video').first().evaluate(v=>v.duration);
 expect(oldDuration).toBeGreaterThan(0);
 const detached=await page.evaluate(async nextRoot=>{
  const old=document.querySelector('video')!;
  await (document.querySelector('#app') as any).__vue_app__.config.globalProperties.$pinia._s.get('studio').api('project.open',{path:nextRoot});
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  old.dispatchEvent(new Event('loadedmetadata'));
  old.dispatchEvent(new Event('timeupdate'));
  return !old.isConnected;
 },root);
 expect(detached).toBeTruthy();
});

test('Agent import review and retry use real reactive parameter data without cloning errors',async()=>{
 await rpc('project.open',{path:root});
 const s=await state();
 const bundle=path.join(root,'agent-review.json');
 await fs.writeFile(bundle,JSON.stringify({project_id:s.project.id,provider:'integration fixture',message:{role:'assistant',content:'生成参数待审阅',tool_calls:[{id:'ui-approve',type:'function',function:{name:'generate',arguments:JSON.stringify({target:shot,mode:'qwen',prompt:'审阅用提示词',references:[]})}}]}}));
 await rpc('agent.import',{path:bundle});
 await page.getByRole('button',{name:'审阅操作',exact:true}).click();
 await expect(page.getByLabel('生成提示词')).toHaveValue('审阅用提示词');
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 expect((await state()).review).toBeNull();
 await page.getByRole('button',{name:'任务与历史',exact:true}).click();await page.getByRole('button',{name:'再次生成',exact:true}).click();
 await expect(page.getByLabel('生成提示词')).toHaveValue('界面测试提示词，实际加入暂停队列');
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
});
test('1920/2K/4K and browser zoom keep media, chat and navigation usable',async()=>{
 await rpc('project.open',{path:legacyRoot});
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();
 for(const [width,height] of [[1920,1080],[2560,1440],[3840,2160],[1024,768]]){
  await page.setViewportSize({width:width!,height:height!});
  await expect(page.getByRole('button',{name:'分镜工作区',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 }
 await page.setViewportSize({width:1600,height:950});
 await page.evaluate(()=>document.documentElement.style.zoom='1.25');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.evaluate(()=>document.documentElement.style.zoom='1');
 await page.screenshot({path:process.env.XY_SCREENSHOT || `../docs/screenshots/${validationVersion}-storyboard.png`});
});
test('many real shot cards and empty search do not break the workbench',async()=>{
 await rpc('project.open',{path:root});
 for(let i=0;i<40;i++)await rpc('asset.add',{kind:'shots',description:'较长的镜头描述。'.repeat(25)});
 await page.getByRole('button',{name:'分镜工作区',exact:true}).click();await expect(page.locator('.shot-card')).toHaveCount(41);
 await page.getByLabel('搜索镜头').fill('完全不存在的名称');await expect(page.locator('.shot-card')).toHaveCount(0);await expect(page.getByText('没有找到这个镜头',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'清除搜索',exact:true}).click();await expect(page.locator('.shot-card')).toHaveCount(41);
 await page.getByRole('button',{name:'折叠全部',exact:true}).click();await expect(page.locator('.shot-body')).toHaveCount(0);
 await page.getByRole('button',{name:/定位镜头41/}).click();await expect(page.locator('.shot-body')).toHaveCount(1);
});
test('AI review and legacy activity records use readable Chinese without internal JSON',async()=>{
 await rpc('project.open',{path:root});
 const s=await state();const bundle=path.join(root,'readable-review.json');
 const content='将为你创建一个小型舞台。\n'+JSON.stringify({type:'skill',skill:'h3',file:'SKILL.md'});
 await fs.writeFile(bundle,JSON.stringify({project_id:s.project.id,provider:'UI regression fixture',message:{role:'assistant',content,_activity:[{type:'skill',skill:'h3',file:'SKILL.md'},{type:'search',sources:[{title:'参考来源测试',url:'https://example.com/'}]}],tool_calls:[{id:'readable-create',type:'function',function:{name:'add_item',arguments:JSON.stringify({kind:'scenes',name:'非技术用户验收舞台',description:'',file:s.project.assets[0].imageFile})}}]}}));
 await rpc('agent.import',{path:bundle});
 await expect(page.locator('.assistant-panel')).not.toContainText('SKILL.md');
 await expect(page.locator('.assistant-panel')).not.toContainText('"type"');
 await expect(page.locator('.chat-sources')).toContainText('参考来源测试');
 await page.getByRole('button',{name:'审阅操作',exact:true}).click();
 await expect(page.locator('.review-fields')).toContainText('创建类型');
 await expect(page.locator('.review-fields')).toContainText('场景');
 await expect(page.getByRole('dialog')).not.toContainText('"kind"');
 await page.getByRole('button',{name:'确认添加条目',exact:true}).click();
 await expect(page.locator('.assistant-panel')).toContainText('已创建：非技术用户验收舞台');
 const stored=JSON.parse(await fs.readFile(path.join(root,'project.json'),'utf8'));
 expect(stored.chat.find((m:any)=>m.content?.includes('将为你创建一个小型舞台'))?.content).toContain('SKILL.md');
});
test('real generated task history shows its own images and video poster',async()=>{
 const report=JSON.parse(await fs.readFile(process.env.XY_HISTORY_REPORT || '../local-data/v111-progress-report.json','utf8'));
 expect(report.passed).toBeTruthy();await rpc('project.open',{path:report.project});
 await page.getByRole('button',{name:'任务与历史',exact:true}).click();
 const s=await state();expect(s.project.tasks).toHaveLength(5);
 for(const task of s.project.tasks){
  const row=page.getByTestId('task-'+task.id);
  await expect(row.locator('.task-output')).toHaveCount(task.results.length);
  for(const [index,result] of task.results.entries()){
   const img=row.locator('.task-output img').nth(index);await expect(img).toHaveAttribute('src',result.media);
   await expect.poll(()=>img.evaluate((image:HTMLImageElement)=>image.naturalWidth)).toBeGreaterThan(0);
  }
 }
 const sceneTasks=s.project.tasks.filter((t:any)=>t.targetName==='进度验收舞台');
 expect(sceneTasks).toHaveLength(2);expect(sceneTasks[0].results[0].media).not.toBe(sceneTasks[1].results[0].media);
 const row=page.getByTestId('task-'+sceneTasks[0].id);
 await row.locator('.task-output').click();await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');
 await row.getByRole('button',{name:'查看结果',exact:true}).click();
 await expect(page.locator('.version-card')).toHaveCount(sceneTasks[0].results.length);
 await expect(page.locator('.version-card img')).toHaveAttribute('src',sceneTasks[0].results[0].media);
 await page.keyboard.press('Escape');
 await row.locator('.task-details summary').click();await expect(row.locator('.generation-details')).toContainText('随机种子');
 await expect(row.locator('.task-details')).not.toContainText('prompt_id');
 await page.locator('.workspace-scroll').evaluate(e=>e.scrollTop=0);
 await page.screenshot({path:`../docs/screenshots/${validationVersion}-history.png`});
});

test('AI object and file references can be individually removed without a selected card',async()=>{
 await rpc('project.open',{path:root});await rpc('context.clear');
 await rpc('selection',{id:actor,pin:true});await rpc('selection',{id:scene,pin:true});
 await rpc('selection',{id:null});
 await page.getByRole('button',{name:'移除AI引用Vue 角色改名',exact:true}).click();
 let s=await state();expect(s.selectedId).toBeNull();expect(s.contextIds).toEqual([scene]);
 const file=s.project.assets.find((a:any)=>a.id===actor).imageFile;
 await rpc('context.add_media',{file});
 await expect(page.locator('.context-pins')).toContainText('图片');
 await page.getByRole('button',{name:/移除AI素材引用/}).click();
 expect((await state()).mediaContext).toEqual([]);expect((await state()).contextIds).toEqual([scene]);
 await rpc('selection',{id:scene});
 await page.getByRole('button',{name:'取消讨论Vue 测试场景',exact:true}).click();
 s=await state();expect(s.selectedId).toBeNull();expect(s.contextIds).toEqual([]);
 await rpc('selection',{id:actor,pin:true});await rpc('context.add_media',{file});
 await page.getByRole('button',{name:'清除 AI 上下文',exact:true}).click();
 s=await state();expect(s.selectedId).toBeNull();expect(s.contextIds).toEqual([]);expect(s.mediaContext).toEqual([]);
 expect(s.project.assets).toHaveLength(3); // Two original assets plus the review-created scene.
});

test('complete image library paginates all originals and restores generated historical references',async()=>{
 await rpc('project.open',{path:path.resolve('../local-data/v110-library-fixture')});
 await page.getByRole('button',{name:'图片库',exact:true}).click();
 const all=await rpc('library.query',{kind:'image',limit:100}) as any;
 expect(all.total).toBeGreaterThan(24);
 await expect(page.locator('.library-card')).toHaveCount(24);
 const first=await page.locator('.library-card').evaluateAll(cards=>cards.map(c=>c.getAttribute('data-testid')));
 await page.getByRole('button',{name:'图片下一页',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(all.total-24);
 const second=await page.locator('.library-card').evaluateAll(cards=>cards.map(c=>c.getAttribute('data-testid')));
 expect(first.filter(id=>second.includes(id))).toEqual([]);
 await page.getByLabel('图片来源筛选').selectOption('generated');
 await expect(page.locator('.library-card')).toHaveCount(all.stats.generated);
 const history=all.items.find((r:any)=>r.source==='generated' && r.owners.some((o:any)=>o.kind==='scenes') && !r.current);
 expect(history).toBeTruthy();
 const card=page.getByTestId('library-'+history.id);
 await expect.poll(()=>card.locator('img').evaluate((image:HTMLImageElement)=>image.naturalWidth)).toBeGreaterThan(0);
 await card.getByRole('button',{name:'查看记录',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText(history.prompt);
 await page.getByRole('button',{name:'放大预览',exact:true}).click();await expect(page.locator('.preview-toolbar')).toBeVisible();await page.keyboard.press('Escape');
 await card.getByRole('button',{name:'发送给 AI',exact:true}).click();
 expect((await state()).mediaContext[0].file).toBe(history.file);
 await page.getByRole('button',{name:/移除AI素材引用/}).click();expect((await state()).mediaContext).toEqual([]);
 await card.getByRole('button',{name:'查看记录',exact:true}).click();
 await page.getByRole('button',{name:history.owners[0].name,exact:true}).click();
 const origin=page.getByTestId('asset-'+history.owners[0].id);await expect(origin).toHaveClass(/selected/);
 await page.locator('.topbar').getByRole('button',{name:'生成图片',exact:true}).click();
 await page.getByLabel('生成工作流').selectOption('qwen_edit');
 while(await page.getByRole('button',{name:'移除参考图',exact:true}).count())await page.getByRole('button',{name:'移除参考图',exact:true}).first().click();
 await page.getByLabel('选择项目参考图').selectOption((await state()).project.assets.find((a:any)=>a.id===history.owners[0].id).imageFile);
 await page.getByRole('button',{name:'加入参考',exact:true}).click();
 await expect(page.getByLabel('使用本机 INT8 模型')).toBeChecked();
 await expect(page.getByLabel('编辑输出尺寸')).toHaveValue('source');
 await page.getByRole('button',{name:'从图片库选择',exact:true}).click();
 await page.getByLabel('图片来源筛选').selectOption('generated');
 await page.getByTestId('library-'+history.id).getByRole('button',{name:'选用这张图片',exact:true}).click();
 await expect(page.locator('.choose-library')).toHaveCount(0);
 // The appended row is an exact historical reference; backend validation returns the same real dimensions.
 await expect(page.locator('.reference-image-row')).toHaveCount(2);
 await page.getByLabel('编辑输出尺寸').selectOption('custom');await expect(page.getByLabel('分辨率 MP')).toBeVisible();
 await page.getByRole('button',{name:'取消生成',exact:true}).click();
 await page.getByRole('button',{name:'图片库',exact:true}).click();
 await page.getByLabel('图片归属筛选').selectOption('deleted');await expect(page.locator('.library-card')).toHaveCount(1);
 await expect(page.locator('.library-card')).toContainText('条目已删除');
 await page.getByLabel('图片归属筛选').selectOption('all');
 await page.getByLabel('搜索图片资产').fill('绝对不存在的素材');await expect(page.getByText('没有找到匹配的图片',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'清除筛选',exact:true}).click();
 await expect(page.locator('.library-card')).toHaveCount(24);
 for(const [width,height] of [[1920,1080],[2560,1440],[3840,2160],[1024,768]]){
  await page.setViewportSize({width:width!,height:height!});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await expect(page.getByRole('button',{name:'图片库',exact:true})).toBeVisible();
 }
 await page.setViewportSize({width:1600,height:950});
 await page.screenshot({path:`../docs/screenshots/${validationVersion}-image-library.png`});
});

test('video library includes generated and imported originals, previews and cancels exact AI attachments',async()=>{
 await page.getByRole('button',{name:'视频库',exact:true}).click();
 const all=await rpc('library.query',{kind:'video',limit:100}) as any;
 expect(all.total).toBe(2);expect(all.stats.generated).toBe(1);expect(all.stats.imported).toBe(1);
 await expect(page.locator('.library-card')).toHaveCount(2);
 const generated=all.items.find((r:any)=>r.source==='generated');
 const card=page.getByTestId('library-'+generated.id);
 await expect.poll(()=>card.locator('img').evaluate((image:HTMLImageElement)=>image.naturalWidth)).toBeGreaterThan(0);
 await card.locator('.library-image').click();await expect(page.getByRole('dialog')).toBeVisible();
 await page.waitForFunction(()=>document.querySelector('video')!.readyState>=2);
 await page.getByRole('dialog').locator('video').evaluate(v=>v.play());
 await page.waitForFunction(()=>document.querySelector('video')!.currentTime>.2);
 expect(await page.getByRole('dialog').locator('video').evaluate(v=>v.error)).toBeNull();
 await page.keyboard.press('Escape');
 await card.getByRole('button',{name:'发送给 AI',exact:true}).click();
 expect((await state()).mediaContext[0].kind).toBe('video');
 await page.getByRole('button',{name:/移除AI素材引用/}).click();expect((await state()).mediaContext).toEqual([]);
 await page.getByLabel('视频来源筛选').selectOption('imported');await expect(page.locator('.library-card')).toHaveCount(1);
 await page.getByLabel('视频来源筛选').selectOption('all');await expect(page.locator('.library-card')).toHaveCount(2);
 await page.screenshot({path:`../docs/screenshots/${validationVersion}-video-library.png`});
});

test('historical generated image and video can be deleted and restored without losing job records',async()=>{
 const copy=path.resolve('../local-data',`${validationVersion}-historical-delete-${Date.now()}`);
 const source=path.resolve('../local-data/v110-library-fixture');
 await fs.cp(source,copy,{recursive:true,filter:p=>!p.endsWith('project.xy-studio.lock')});
 await rpc('project.open',{path:copy});
 const prior=await state();
 for(const kind of ['image','video']){
  const all=await rpc('library.query',{kind,source:'generated',limit:100}) as any;
  const record=all.items.find((r:any)=>!r.current) || all.items[0];
  expect(record).toBeTruthy();
  for(const owner of record.owners)if(record.current)await rpc('asset.delete',{id:owner.id});
  const bytes=await fs.readFile(path.join(copy,record.file));
  await page.getByRole('button',{name:kind==='image'?'图片库':'视频库',exact:true}).click();
  await page.getByLabel(kind==='image'?'图片来源筛选':'视频来源筛选').selectOption('generated');
  const card=page.getByTestId('library-'+record.id);await card.waitFor();
  await card.getByRole('button',{name:/删除素材/}).click();
  await page.getByRole('button',{name:'移入回收站',exact:true}).click();
  await expect(card).toHaveCount(0);
  expect((await rpc('library.query',{kind,limit:100}) as any).items.some((r:any)=>r.file===record.file)).toBe(false);
  await page.getByRole('button',{name:'回收站',exact:true}).click();
  await page.getByTestId('library-'+record.id).getByRole('button',{name:'恢复素材',exact:true}).click();
  await page.getByRole('button',{name:kind==='image'?'返回图片库':'返回视频库',exact:true}).click();
  expect((await rpc('library.query',{kind,source:'generated',limit:100}) as any).items.find((r:any)=>r.file===record.file).id).toBe(record.id);
  expect(await fs.readFile(path.join(copy,record.file))).toEqual(bytes);
 }
 expect((await state()).project.tasks.map((t:any)=>[t.id,t.raw.outputs])).toEqual(prior.project.tasks.map((t:any)=>[t.id,t.raw.outputs]));
});
