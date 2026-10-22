import {chromium} from '@playwright/test';
const b=await chromium.connectOverCDP(process.env.XY_CDP || 'http://127.0.0.1:9225',{noDefaults:true});
const p=b.contexts()[0].pages()[0];
const rpc=(name,payload={})=>p.evaluate(async([name,payload])=>document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('studio').api(name,payload),[name,payload]);
const s=await rpc('bootstrap');
if(process.argv[2]==='reset' && s.review)await rpc('review.respond',{id:s.review.id,accepted:false});
if(process.argv[2]==='close'){
 try{await rpc('app.close');}
 catch(error){
  // Closing the host can destroy CDP before its final bridge reply. Other
  // errors must still fail. Process exit is independently checked in QA.
  if(!String(error).includes('Target page, context or browser has been closed'))throw error;
  console.log('Desktop close requested; CDP closed with the window.');
 }
}
else console.log(JSON.stringify({version:s.version,project:s.project?.root,busy:s.busy,active:s.activeJob,keySet:s.config.keySet,error:s.error}));
await b.close();
