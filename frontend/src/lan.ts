import { reactive } from 'vue';
export const isLan = import.meta.env.MODE === 'mobile' || new URLSearchParams(location.search).has('lan');
export const lan = reactive({ base: localStorage.getItem('xy-lan-base') || '', status: '未连接', connected: false, pairing: false, error: '' });
let token = sessionStorage.getItem('xy-lan-token') || '';
let stateListener: (value: unknown) => void = () => {};
let noticeListener: (value: string) => void = () => {};
let projectId: string | null = null, revision = 0;
let socket: WebSocket | null = null, retry: ReturnType<typeof setTimeout> | undefined;
let reconnectDelay = 1000, stopped = false, sequence = 0;

export function validBase(input: string) {
  const url = new URL(input.includes('://') ? input : 'http://' + input);
  const parts = url.hostname.split('.').map(Number);
  const privateIP = parts.length === 4 && parts.every(n => Number.isInteger(n) && n >= 0 && n <= 255)
    && (parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168) || (parts[0] === 172 && parts[1]! >= 16 && parts[1]! <= 31));
  if (!privateIP || url.protocol !== 'http:' || url.username || url.password || url.search || url.hash || url.pathname !== '/')
    throw new Error('请输入 PC 局域网 IPv4 和端口，例如 http://192.168.1.10:8765');
  return url.origin;
}
function mediaUrls(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(mediaUrls);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k,mediaUrls(v)]));
  return typeof value === 'string' && value.startsWith('/media/') ? lan.base + value : value;
}
function receive(value: unknown) {
  const s = value as { project?: {id: string}; lanRevision?: number };
  projectId = s.project?.id || null; revision = s.lanRevision || 0;
  stateListener(mediaUrls(value));
}
async function request(path: string, options: RequestInit = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), path === '/upload' ? 120000 : 30000);
  try {
    const response = await fetch(lan.base + path, { ...options, signal: controller.signal, headers: { ...(token ? {Authorization: 'Bearer ' + token} : {}), ...options.headers } });
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== '/pair') { forget(); lan.error = body.error || '请重新配对'; }
      throw new Error(body.error || `PC 服务返回 ${response.status}`);
    }
    return body;
  } catch (error) {
    if (error instanceof TypeError || (error instanceof DOMException && error.name === 'AbortError')) {
      lan.connected = false; lan.status = '连接中断';
      throw new Error('PC 连接中断或响应超时。写入/生成可能已执行，请重连后检查任务历史，不要直接重复提交。');
    }
    throw error;
  } finally { clearTimeout(timer); }
}
function events() {
  if (stopped || !token) return;
  const generation = ++sequence;
  socket?.close();
  const ws = new WebSocket(lan.base.replace(/^http:/, 'ws:') + '/events');
  socket = ws;
  ws.onopen = () => ws.send(JSON.stringify({token}));
  ws.onmessage = event => {
    if (generation !== sequence || event.data === 'pong') return;
    const message = JSON.parse(event.data);
    if (message.type === 'state') {
      receive(message.state); lan.connected = true; lan.status = '已连接 PC'; lan.error = ''; reconnectDelay = 1000;
    }
  };
  ws.onclose = event => {
    if (generation !== sequence || stopped) return;
    lan.connected = false; lan.status = '连接中断，正在重连';
    if (event.code === 4001) { forget(); lan.error = '授权已过期或被 PC 撤销，请重新配对'; return; }
    retry = setTimeout(events, reconnectDelay); reconnectDelay = Math.min(reconnectDelay * 2, 10000);
  };
}
export async function pair(base: string, code: string, name: string) {
  forget(); lan.base = validBase(base); lan.pairing = true; lan.error = '';
  try {
    const result = await request('/pair', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({code, name})});
    token = result.token;
    sessionStorage.setItem('xy-lan-token', token); localStorage.setItem('xy-lan-base', lan.base);
    await reconnect();
  } catch (e) { lan.error = String(e); throw e; }
  finally { lan.pairing = false; }
}
export function forget() {
  stopped = true; ++sequence; clearTimeout(retry); socket?.close(); socket = null;
  token = ''; sessionStorage.removeItem('xy-lan-token'); lan.connected = false; lan.status = '未连接'; projectId = null;
}
export async function reconnect() {
  if (!token) throw new Error('请先输入 PC 地址和一次性配对码');
  lan.base = validBase(lan.base); stopped = false; clearTimeout(retry);
  const state = await lanCommand('bootstrap'); receive(state); events(); return state;
}
export async function connectLan(onState: (value: unknown) => void, onNotice: (text: string) => void) {
  stateListener = onState; noticeListener = onNotice;
  return reconnect();
}
export async function lanCommand<T = unknown>(command: string, payload: Record<string, unknown> = {}): Promise<T> {
  if (!token) throw new Error('请先连接并配对 PC');
  if (['library.import','references.import','asset.import'].includes(command)) return await uploadFiles(command,payload) as T;
  if (command === 'link.open') {
    const url = new URL(String(payload.url));
    if (!['https:', 'http:'].includes(url.protocol)) throw new Error('链接协议不安全');
    window.open(url.href, '_blank', 'noopener,noreferrer'); return true as T;
  }
  if (command === 'project.open' && !payload.path) throw new Error('请在 PC 授权项目，再点击手机上的项目卡片');
  if (['project.folder','agent.import','app.close','media.open'].includes(command)) throw new Error('请使用 PC 桌面处理此操作；手机可在素材库内预览图片与视频');
  const result = await request('/rpc', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:crypto.randomUUID(),command,payload,projectId,revision})});
  if (result.state) receive(result.state);
  if (!result.ok) throw new Error(result.error);
  return mediaUrls(result.result) as T;
}
async function uploadFiles(command: string, payload: Record<string,unknown>) {
  if (payload.paths) throw new Error('手机不能访问 PC 文件路径');
  const input = document.createElement('input'); input.type='file'; input.multiple=true;
  input.accept = payload.kind === 'video' ? 'video/mp4,video/webm' : 'image/png,image/jpeg,image/webp';
  const files = await new Promise<File[]>(resolve => {
    input.onchange = () => resolve(Array.from(input.files || [])); input.oncancel = () => resolve([]); input.click();
  });
  const results: string[] = [], selectedProject = projectId;
  for (const file of files) {
    if (file.size > 100*1024*1024) throw new Error('单个素材不能超过 100 MB');
    const form = new FormData(); form.append('metadata', JSON.stringify({command,payload,projectId:selectedProject})); form.append('file',file);
    const result = await request('/upload',{method:'POST',body:form}); results.push(...result.result);
  }
  if (files.length) { await lanCommand('bootstrap'); noticeListener('素材已保存至 PC 项目'); }
  return results;
}
document.addEventListener('visibilitychange', () => { if (isLan && !document.hidden && token) void reconnect().catch(e => {lan.error=String(e);}); });
