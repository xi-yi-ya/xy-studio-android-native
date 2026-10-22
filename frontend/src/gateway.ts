import { isLan, connectLan, lanCommand } from './lan';
export interface ChannelSignal { connect(callback: (value: string) => void): void }
interface NativeBridge { request(value: string): void; reply: ChannelSignal; stateChanged: ChannelSignal; notification: ChannelSignal }
declare global {
  interface Window {
    qt?: { webChannelTransport: unknown };
    QWebChannel?: new (transport: unknown, ready: (channel: {objects: {studio: NativeBridge}}) => void) => unknown;
  }
}
let bridge: NativeBridge | null = null;
const waiting = new Map<string, {resolve:(value:unknown)=>void;reject:(error:Error)=>void}>();
export async function connect(onState:(value:unknown)=>void,onNotice:(text:string)=>void) {
  if(isLan) return connectLan(onState,onNotice);
  for(let i=0;i<50 && (!window.qt || !window.QWebChannel);i++) await new Promise(r=>setTimeout(r,100));
  if(!window.qt || !window.QWebChannel) throw new Error('桌面通信未连接。请通过 XY Studio.exe 运行，浏览器开发页不提供真实后端或 Mock 回退。');
  await new Promise<void>(resolve=>new window.QWebChannel!(window.qt!.webChannelTransport,channel=>{
    bridge=channel.objects.studio;
    bridge.reply.connect(raw=>{
      const response=JSON.parse(raw);const p=waiting.get(response.id);if(!p)return;
      waiting.delete(response.id);if(response.ok)p.resolve(response.result);else p.reject(new Error(response.error));
    });
    bridge.stateChanged.connect(raw=>onState(JSON.parse(raw)));
    bridge.notification.connect(onNotice);resolve();
  }));
  return command('bootstrap');
}
export function command<T=unknown>(name:string,payload:Record<string,unknown>={}):Promise<T> {
  if(isLan) return lanCommand<T>(name,payload);
  if(!bridge)return Promise.reject(new Error('桌面通信不可用'));
  const id=crypto.randomUUID();
  return new Promise<T>((resolve,reject)=>{waiting.set(id,{resolve:value=>resolve(value as T),reject});bridge!.request(JSON.stringify({id,command:name,payload}));});
}
