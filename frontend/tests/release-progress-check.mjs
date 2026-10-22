/** Real paused queue, screenshots and orderly packaged-app exit; no inference. */
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
const browser = await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9226', { noDefaults: true });
const page = browser.contexts()[0].pages()[0];
const rpc = (command, payload = {}) => page.evaluate(async ([command, payload]) => document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command, payload), [command, payload]);
const root = path.resolve('../local-data/v032-release-progress-' + Date.now());
try {
  await rpc('project.new', { path: root, title: '生成进度界面验收' });
  const actor = await rpc('asset.add', { kind: 'characters', name: '进度验收角色', description: '图片再次点击可取消选中，双击查看完整图片。' });
  const scene = await rpc('asset.add', { kind: 'scenes', name: '进度验收场景', description: '每个素材保留自己的生成任务和历史版本。' });
  const shot = await rpc('asset.add', { kind: 'shots', description: '同一镜头的图片与视频生成状态保留在镜头内。' });
  const source = path.resolve(process.env.XY_LEGACY || '../local-data/v032-compat', 'assets/b1463e53334345328a91dc047816aec3.png');
  for (const id of [actor, scene, shot]) await rpc('asset.import', { id, paths: [source] });
  await rpc('asset.link', { id: shot, ids: [actor, scene] });
  await rpc('queue.toggle');
  const g = await rpc('generation.defaults', { target: actor, mode: 'qwen' });
  const ids = [];
  for (const target of [actor, scene, shot]) ids.push(await rpc('generation.submit', { target, generation: { ...g, prompt: '实际暂停队列验收，不执行 GPU 生成', megapixels: .1, steps: 4 } }));
  for (const [nav, file] of [['角色资产', 'role'], ['场景资产', 'scene'], ['分镜工作区', 'storyboard'], ['任务与历史', 'tasks']]) {
    await page.getByRole('button', { name: nav, exact: true }).click();
    for (const bar of await page.getByRole('progressbar').all()) {
      if (await bar.getAttribute('aria-valuenow') !== null) throw Error('Invented percentage in paused queue');
    }
    await page.screenshot({ path: `../docs/screenshots/v032-queued-${file}.png` });
  }
  for (const id of ids) await rpc('task.cancel', { id });
  const s = await rpc('bootstrap');
  if (s.activeJob || s.project.tasks.some(t => t.status !== 'cancelled')) throw Error('Paused jobs were not correctly cancelled');
  await fs.writeFile('../local-data/v032-release-progress-report.json', JSON.stringify({ project: root, version: s.version, ids, statuses: s.project.tasks.map(t => t.status), passed: true }, null, 2));
  console.log('Real paused queue and all four progress surfaces passed');
  try { await rpc('app.close'); } catch { /* Renderer disconnect can precede the RPC reply. */ }
} finally { await browser.close(); }
