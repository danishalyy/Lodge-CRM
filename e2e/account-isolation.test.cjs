const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright-core');
const ts=require('../apps/web/node_modules/typescript');
const web=path.resolve(__dirname,'../apps/web');
const base='http://127.0.0.1:3107';
let server,browser;
before(async()=>{
  fs.cpSync(path.join(web,'.next/static'),path.join(web,'.next/standalone/.next/static'),{recursive:true});
  server=spawn(process.execPath,[path.join(web,'.next/standalone/server.js')],{env:{...process.env,HOSTNAME:'127.0.0.1',PORT:'3107'},stdio:'ignore'});
  for(let i=0;i<100;i++){
    try{if((await fetch(base+'/login')).ok)break;}catch{}
    if(i===99)throw Error('Standalone frontend did not become ready');
    await new Promise(r=>setTimeout(r,100));
  }
  browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server']});
});
after(async()=>{if(browser)await browser.close();if(server)server.kill('SIGTERM')});

async function accountPage(user){
  const context=await browser.newContext();
  await context.addCookies([{name:'lodge_session',value:'ui-only-test-session',url:base}]);
  const page=await context.newPage();
  const requests=[];
  await page.route('**/api/**',async route=>{
    const url=route.request().url();
    if(url.endsWith('/api/v1/auth/me'))await route.fulfill({json:user});
    else{requests.push(url);await route.fulfill({json:[]})}
  });
  return {context,page,requests};
}

test('lodge account cannot render any platform children',async()=>{
  const {context,page,requests}=await accountPage({id:'lodge-user',is_super_admin:false,mfa_enabled:false,memberships:[]});
  try{
    for(const route of ['/super-admin','/super-admin/lodges','/super-admin/users']){
      await page.goto(base+route);
      await page.getByRole('heading',{name:'Access denied',exact:true}).waitFor();
      assert.equal(await page.getByText('Platform Console',{exact:true}).count(),0);
    }
    assert.deepEqual(requests,[],'unauthorized children must not fetch platform data');
  }finally{await context.close()}
});

test('direct lodge module URL enforces role permissions and resets previous account context',async()=>{
  const user={id:'new-staff',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:'own-lodge',permissions:['tasks.view'],entitlements:['tasks']}]};
  const {context,page,requests}=await accountPage(user);
  try{
    await context.addInitScript(()=>{
      localStorage.setItem('active_user_id','previous-user');
      localStorage.setItem('active_lodge_id','previous-lodge');
      localStorage.setItem('active_lodge_name','Previous private lodge');
    });
    await page.goto(base+'/hr');
    await page.getByRole('heading',{name:'Access denied',exact:true}).waitFor();
    assert.deepEqual(requests,[]);
    assert.deepEqual(await page.evaluate(()=>[localStorage.getItem('active_user_id'),localStorage.getItem('active_lodge_id'),localStorage.getItem('active_lodge_name')]),['new-staff','own-lodge',null]);
  }finally{await context.close()}
});

test('offline queues isolate users and lodges, preserve photos and never adopt legacy records',async()=>{
  const context=await browser.newContext();const page=await context.newPage();
  try{
    await page.goto(base+'/login');
    const source=fs.readFileSync(path.join(web,'lib/offlineWildlife.ts'),'utf8');
    const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    await page.evaluate(async()=>{
      await new Promise((resolve,reject)=>{
        const r=indexedDB.open('lodge-crm-offline',1);
        r.onupgradeneeded=()=>r.result.createObjectStore('wildlife-queue',{keyPath:'id'});
        r.onsuccess=()=>{const db=r.result;const tx=db.transaction('wildlife-queue','readwrite');tx.objectStore('wildlife-queue').put({id:'legacy',payload:{notes:'unknown owner'}});tx.oncomplete=()=>{db.close();resolve()}};
        r.onerror=()=>reject(r.error);
      });
    });
    await page.addScriptTag({content:`window.offlineModule=(()=>{const exports={};${js};return exports;})();`});
    const result=await page.evaluate(async()=>{
      const api=window.offlineModule;
      const a={userId:'user-a',lodgeId:'lodge-a'},b={userId:'user-b',lodgeId:'lodge-a'},c={userId:'user-a',lodgeId:'lodge-b'};
      const item=note=>({id:'same-client-reference',payload:{notes:note},photo:new Blob([note],{type:'image/jpeg'}),createdAt:new Date().toISOString()});
      await api.queueSighting(a,item('A'));await api.queueSighting(b,item('B'));await api.queueSighting(c,item('C'));
      const first=await api.queuedSightings(a);
      const initial=[first.map(x=>x.payload.notes),(await api.queuedSightings(b)).map(x=>x.payload.notes),(await api.queuedSightings(c)).map(x=>x.payload.notes),await first[0].photo.text()];
      await api.removeQueuedSighting(b,'same-client-reference');
      const retained=[(await api.queuedSightings(a)).length,(await api.queuedSightings(b)).length,(await api.queuedSightings(c)).length];
      let unsignedRejected=false;try{await api.queuedSightings({userId:'',lodgeId:'lodge-a'})}catch{unsignedRejected=true}
      return {initial,retained,unsignedRejected};
    });
    assert.deepEqual(result,{initial:[['A'],['B'],['C'],'A'],retained:[1,0,1],unsignedRejected:true});
  }finally{await context.close()}
});

test('sign out clears the account context and returns to login',async()=>{
  const {context,page}=await accountPage({id:'signed-in-user',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:'own-lodge',permissions:[],entitlements:[]}]});
  let expectedUser;
  try{
    await page.route('**/api/v1/auth/logout',async route=>{
      expectedUser=route.request().headers()['x-expected-user-id'];
      await route.fulfill({json:{ok:true}});
    });
    await page.goto(base+'/settings');
    await page.getByRole('heading',{name:'Security settings',exact:true}).waitFor();
    await page.getByRole('button',{name:'Sign out',exact:true}).click();
    await page.waitForURL(base+'/login');
    assert.equal(expectedUser,'signed-in-user');
    assert.deepEqual(await page.evaluate(()=>[localStorage.getItem('active_user_id'),localStorage.getItem('active_lodge_id')]),[null,null]);
  }finally{await context.close()}
});

test('account switch in another tab removes the previous platform console',async()=>{
  const context=await browser.newContext();
  await context.addCookies([{name:'lodge_session',value:'ui-test-session',url:base}]);
  let user={id:'platform-user',is_super_admin:true,mfa_enabled:true,memberships:[]};
  await context.route('**/api/**',route=>route.fulfill({json:route.request().url().endsWith('/api/v1/auth/me')?user:[]}));
  try{
    const page=await context.newPage();
    await page.goto(base+'/super-admin/lodges');
    await page.getByRole('heading',{name:'Lodges',exact:true}).waitFor();
    const peer=await context.newPage();await peer.goto(base+'/login');
    user={id:'lodge-user',is_super_admin:false,mfa_enabled:false,memberships:[]};
    await peer.evaluate(()=>localStorage.setItem('active_user_id','lodge-user'));
    await page.getByRole('heading',{name:'Access denied',exact:true}).waitFor();
    assert.equal(await page.getByText('Platform Console',{exact:true}).count(),0);
  }finally{await context.close()}
});
