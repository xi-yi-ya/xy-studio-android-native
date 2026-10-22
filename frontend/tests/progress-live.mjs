/** Explicit low-resolution ComfyUI inference; never run by npm test. */
import { chromium } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs/promises';

const browser = await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225', { noDefaults: true });
const page = browser.contexts()[0].pages()[0];
const rpc = (command, payload = {}) => page.evaluate(async ([command, payload]) => document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command, payload), [command, payload]);
const validationVersion = process.env.XY_VALIDATION_VERSION || 'v032';
const root = path.resolve(`../local-data/${validationVersion}-progress-` + Date.now());
const report = { project: root, tests: [], errors: [] };
const reportPath = `../local-data/${validationVersion}-progress-report.json`;
const save = () => fs.writeFile(reportPath, JSON.stringify(report, null, 2));
try {
  const queue = await (await fetch('http://127.0.0.1:8188/queue')).json();
  if (queue.queue_running.length || queue.queue_pending.length) throw Error('ComfyUI is busy; preserve existing user tasks');
  await rpc('project.new', { path: root, title: `v${validationVersion.replace(/^v/, '').replace(/^(\d)(\d)(\d)$/, '$1.$2.$3')} 真实进度验收` });
  const actor = await rpc('asset.add', { kind: 'characters', name: '进度验收角色', description: '桌面绿色机器人' });
  const scene = await rpc('asset.add', { kind: 'scenes', name: '进度验收舞台', description: '空舞台与蓝色灯光' });
  const shot = await rpc('asset.add', { kind: 'shots', description: '舞台上的小机器人' });
  await rpc('asset.link', { id: shot, ids: [actor, scene] });
  const base = { mode: 'krea', prompt: 'A green toy robot on a simple wooden desk, blue background, soft daylight.', ratio: '16:9', megapixels: .1, seconds: .5, seed: String(Date.now() % 2147483647), steps: 16, cinema: false, cinema_strength: .4, quad_lora: true, qwen_int8: true, styles: [], scale: 1.5, references: [] };
  async function generate(name, target, nav, overrides = {}, queueAgain = false) {
    await page.getByRole('button', { name: nav, exact: true }).click();
    const generation = { ...base, seed: String(Number(base.seed) + report.tests.length * 10), ...overrides };
    const id = await rpc('generation.submit', { target, generation });
    const queuedId = queueAgain ? await rpc('generation.submit', { target, generation: { ...generation, seed: String(Number(generation.seed) + 1), steps: 4 } }) : null;
    const record = { name, id, target, generation, observed: [], barsVerified: 0, queuedId };
    report.tests.push(record);
    const deadline = Date.now() + 600000;
    let done = false;
    while (Date.now() < deadline) {
      const observed = await page.evaluate(async id => {
        const app = document.querySelector('#app').__vue_app__;
        const store = app.config.globalProperties.$pinia._s.get('studio');
        await new Promise(resolve => requestAnimationFrame(resolve));
        const task = store.project.tasks.find(t => t.id === id);
        const bars = [...document.querySelectorAll(`[data-task-id="${id}"] [role="progressbar"]`)].map(b => ({ value: b.getAttribute('aria-valuenow'), text: b.getAttribute('aria-valuetext'), width: b.querySelector('span')?.style.width ?? null }));
        const card = document.querySelector(`[data-testid="asset-${task.targetId}"]`) || document.querySelector(`[data-testid="shot-${task.targetId}"]`);
        return { task, bars, error: store.connectionError, active: store.state.activeJob, cardTask: card?.querySelector('.generation-progress')?.getAttribute('data-task-id'), pending: store.pendingTasks };
      }, id);
      const task = observed.task;
      if(observed.error)throw Error(observed.error);
      const key = `${task.status}:${task.node}:${task.progress}`;
      if (record.observed.at(-1)?.key !== key) record.observed.push({ key, steps: task.steps, bars: observed.bars });
      if (task.status === 'running' && task.progress !== null && observed.active === id) {
        if (observed.bars.length < 2) throw Error(name + ': missing real global/card progress');
        if (observed.bars.some(b => Number(b.value) !== task.progress || !b.text.includes('步'))) throw Error(name + ': UI percentage differs from actual node steps');
        if (queuedId && observed.cardTask !== id) throw Error('Queued regeneration hid the running task');
        record.barsVerified++;
        if (!record.screenshot && task.progress > 0 && task.progress < 100) {
          const screenshot = `../docs/screenshots/${validationVersion}-progress-${target === shot ? (generation.mode.startsWith('h3') ? 'video' : 'shot') : target === scene ? 'scene' : 'role'}.png`;
          await page.screenshot({ path: screenshot }); record.screenshot = screenshot;
        }
      } else if (['new', 'queued', 'submitting', 'downloading'].includes(task.status)) {
        if (observed.bars.some(b => b.value !== null || b.width !== null)) throw Error('A phase without measured steps displayed invented progress');
      }
      if (['failed', 'unknown', 'cancelled'].includes(task.status)) throw Error(name + ': ' + (task.error || task.status));
      if (task.status === 'completed' && observed.active !== id) {
        record.status = task.status; record.outputs = task.raw.outputs;
        done = true; break;
      }
      await new Promise(r => setTimeout(r, 120));
    }
    if (!done || !record.barsVerified) throw Error(name + ': no measured progress or no completion');
    if (queuedId) {
      await page.waitForFunction(id => {
        const s = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio');
        return s.project.tasks.find(t => t.id === id)?.status === 'completed' && s.state.activeJob !== id;
      }, queuedId, { timeout: 600000 });
    }
    const state = await rpc('bootstrap');
    const item = [...state.project.assets, ...state.project.shots].find(a => a.id === target);
    if (!item.versions.some(v => v.file === record.outputs[0])) throw Error('Result not attached to its original card');
    record.versionCount = item.versions.length;
    await save(); console.log(name + ': completed, verified ' + record.barsVerified + ' measured UI updates');
    return item;
  }
  await generate('角色图片进度', actor, '角色资产');
  await generate('场景图片与连续手工任务进度', scene, '场景资产', { prompt: 'An empty small concert stage, blue spotlights, a dark curtain, wide view.' }, true);
  const image = await generate('分镜图片进度', shot, '分镜工作区');
  await generate('H3 视频进度', shot, '分镜工作区', { mode: 'h3_i2v', steps: 8, references: [image.imageFile], prompt: 'integrated_multimodal_description: For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced. [Shot 1] Static camera. The green toy robot slowly lifts its right arm, retaining the desk and blue background.\noverall_soundscape: Quiet indoor room tone.\nnon_diegetic_music: N/A.' });
  await page.getByRole('button', { name: '任务与历史', exact: true }).click();
  await page.screenshot({ path: `../docs/screenshots/${validationVersion}-completed-tasks.png` });
  report.passed = true;
} catch (error) {
  report.errors.push(String(error)); process.exitCode = 1; console.error(String(error));
} finally {
  await save(); await browser.close();
}
