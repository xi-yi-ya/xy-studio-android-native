/** Opt-in save/reopen of real QA media, optionally with a frozen EXE on a project copy. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';

const live = JSON.parse(await fs.readFile('../local-data/v120-package-library-live-report.json', 'utf8'));
const root = process.env.XY_READBACK_ROOT || live.project;
const expected = JSON.parse(await fs.readFile(path.join(root, 'project.json'), 'utf8'));
const browser = await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9227', { noDefaults: true });
const page = browser.contexts()[0].pages()[0];
const rpc = (command, payload = {}) => page.evaluate(async ([command, payload]) =>
  document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(command, payload), [command, payload]);
await page.waitForFunction(() => document.querySelector('#app')?.__vue_app__?.config.globalProperties.$pinia._s.get('studio').ready);
const report = { passed: false, errors: [] };
try {
  if (!process.env.XY_READBACK_ROOT) {
    await rpc('project.new', { path: path.resolve('../local-data/v120-readback-empty-' + Date.now()), title: '重开验收临时空项目' });
    await rpc('project.open', { path: root });
  }
  const state = await rpc('bootstrap');
  report.version = state.version;
  report.project = root;
  assert.equal(state.error, '');
  assert.equal(state.project.id, expected.id);
  assert.equal(state.project.tasks.length, 2);
  assert.ok(state.project.tasks.every(task => task.status === 'completed'));
  await page.getByRole('button', { name: '分镜工作区', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2);
  await page.locator('video').first().evaluate(video => video.play());
  await page.waitForFunction(() => document.querySelector('video').currentTime > .2);
  await page.locator('video').first().evaluate(video => video.pause());
  await rpc('project.save');
  const actual = JSON.parse(await fs.readFile(path.join(root, 'project.json'), 'utf8'));
  for (const key of ['schema', 'id', 'title', 'story', 'characters', 'scenes', 'shots', 'media_names', 'chat'])
    assert.deepEqual(actual[key], expected[key], key + ' changed');
  const jobs = data => data.jobs.map(job => ({ id: job.id, target: job.target, generation: job.generation, outputs: job.outputs }));
  assert.deepEqual(jobs(actual), jobs(expected));
  for (const job of actual.jobs) for (const file of job.outputs) await fs.access(path.join(root, file));
  Object.assign(report, { idsUnchanged: true, promptAndReferencesUnchanged: true, mediaNamesUnchanged: true, playback: true, schema: actual.schema });
  if (state.version === '1.2.0') {
    const images = await rpc('library.query', { kind: 'image', limit: 100 });
    const videos = await rpc('library.query', { kind: 'video', limit: 100 });
    assert.equal(images.total, 3); assert.equal(videos.total, 1);
    report.library = { images: images.total, videos: videos.total };
  }
  report.passed = true;
} catch (error) {
  report.errors.push(String(error));
  process.exitCode = 1;
} finally {
  await fs.writeFile('../local-data/v120-' + (process.env.XY_READBACK_ROOT ? 'frozen' : 'package') + '-readback.json', JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
