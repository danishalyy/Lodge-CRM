const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright-core');
const AxeBuilder=require('@axe-core/playwright').default;
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
  const page=await context.newPage();page.setDefaultTimeout(10000);
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
  const user={id:'new-staff',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:'own-lodge',permissions:['tasks.view'],entitlements:['tasks','staff_hr']}]};
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
  const context=await browser.newContext();const page=await context.newPage();page.setDefaultTimeout(10000);
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
    const page=await context.newPage();page.setDefaultTimeout(10000);
    await page.goto(base+'/super-admin/lodges');
    await page.getByRole('heading',{name:'Lodges',exact:true}).waitFor();
    const peer=await context.newPage();await peer.goto(base+'/login');
    user={id:'lodge-user',is_super_admin:false,mfa_enabled:false,memberships:[]};
    await peer.evaluate(()=>localStorage.setItem('active_user_id','lodge-user'));
    await page.getByRole('heading',{name:'Access denied',exact:true}).waitFor();
    assert.equal(await page.getByText('Platform Console',{exact:true}).count(),0);
  }finally{await context.close()}
});

test('platform branding editor previews uploads, saves and remains usable on mobile',async()=>{
  const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();page.setDefaultTimeout(10000);
  const id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
  let brand={display_name:'Acacia Lodge',logo_url:null};let saved;
  await context.addCookies([{name:'lodge_session',value:'ui-branding-test',url:base}]);
  await page.route('**/api/**',async route=>{
    const url=route.request().url();
    if(url.endsWith('/auth/me'))return route.fulfill({json:{id:'platform',is_super_admin:true,mfa_enabled:true,memberships:[]}});
    if(url.endsWith('/branding')&&route.request().method()==='PATCH'){
      saved=route.request().postDataJSON();brand={display_name:saved.display_name,logo_url:null};return route.fulfill({json:brand});
    }
    return route.fulfill({json:[{id,name:'Acacia Lodge',location:'South Africa',branding:brand,subscription_status:'Active',subscription:{package:'Standard',expiry_date:'2027-01-01'}}]});
  });
  try{
    await page.goto(base+'/super-admin/lodges');await page.getByRole('heading',{name:'Acacia Lodge',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.getByRole('button',{name:'Manage branding',exact:true}).click();
    await page.getByRole('dialog').waitFor();
    await page.getByLabel('Workspace display name').fill('Acacia River Lodge');
    const image=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64');
    await page.getByLabel('Lodge logo',{exact:true}).setInputFiles({name:'acacia.png',mimeType:'image/png',buffer:image});
    await page.getByAltText('Lodge logo preview').waitFor();
    await page.getByRole('button',{name:'Save branding',exact:true}).click();
    await page.getByRole('heading',{name:'Acacia River Lodge',exact:true}).waitFor();
    assert.equal(saved.display_name,'Acacia River Lodge');assert.equal(saved.logo_base64,image.toString('base64'));
    await page.getByRole('button',{name:/Register lodge/}).click();
    await page.getByRole('heading',{name:'Welcome a lodge',exact:true}).waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog').count(),0);
  }finally{await context.close()}
});

test('lodge identity and SafariOS remain visible together',async()=>{
  const context=await browser.newContext();const page=await context.newPage();page.setDefaultTimeout(10000);
  const id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
  await context.addCookies([{name:'lodge_session',value:'ui-lodge-test',url:base}]);
  await page.route('**/api/**',route=>route.fulfill({json:route.request().url().endsWith('/auth/me')?{id:'lodge',full_name:'Lodge Manager',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:id,lodge_name:'Original name',permissions:[],entitlements:[]}]}:{display_name:'Acacia River Lodge',logo_url:null,platform_name:'SafariOS'}}));
  try{
    await page.goto(base+'/settings');await page.locator('.lodgeIdentity').getByText('Acacia River Lodge',{exact:true}).waitFor();
    await page.locator('.lodgeIdentity').getByText('Powered by SafariOS',{exact:true}).waitFor();
    assert.equal(await page.locator('.safariBrand').count(),1);
    assert.equal(await page.getByRole('link',{name:'Super Admin',exact:true}).count(),0);
  }finally{await context.close()}
});

test('glass themes persist, desktop navigation collapses, mobile navigation uses a drawer',async()=>{
 const {context,page}=await accountPage({id:'owner',full_name:'Platform Owner',is_super_admin:true,mfa_enabled:true,memberships:[]});
 try{
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/super-admin/lodges');await page.getByRole('heading',{name:'Lodges',exact:true}).waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
  assert.equal(await page.locator('html').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(54, 54, 54)');
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(23, 23, 23)');
  assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(54, 54, 54)');
  assert.equal(await page.locator('.surfaceBackdrop i').first().evaluate(el=>getComputedStyle(el).display),'none');
  assert.equal(await page.locator('.sidebar .navItem.active .navIcon').evaluate(el=>getComputedStyle(el).color),'rgb(238, 238, 235)');
  assert.equal(await page.locator('.propertyCard').count(),0);
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backdropFilter),'blur(32px) saturate(1.1)');
  const primary=page.getByRole('button',{name:/Register lodge/});
  assert.deepEqual(await primary.evaluate(el=>({background:getComputedStyle(el).backgroundColor,text:getComputedStyle(el).color})),{background:'rgb(127, 137, 103)',text:'rgb(21, 24, 16)'});
  assert.match(await page.getByRole('heading',{name:'Lodges',exact:true}).evaluate(el=>getComputedStyle(el).fontFamily),/^"?Inter"?(?:,|$)/);
  assert.match(await page.locator('body').evaluate(el=>getComputedStyle(el).fontFamily),/Inter/);

  assert.equal(await page.locator('.sidebar').evaluate(el=>Math.round(el.getBoundingClientRect().left)),0);
  await page.getByRole('button',{name:'Collapse sidebar',exact:true}).click();
  assert.equal(await page.locator('html').getAttribute('data-sidebar'),'collapsed');
  assert.equal(await page.evaluate(()=>{const button=document.querySelector('.collapseSidebar').getBoundingClientRect(),mark=document.querySelector('.sidebar .safariMark').getBoundingClientRect();return button.left>=mark.right}),true,'collapsed navigation control must not overlap the brand');
  await page.getByRole('button',{name:'Expand sidebar',exact:true}).click();
  await page.getByRole('button',{name:'Toggle light and dark theme'}).click();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  assert.equal(await page.locator('html').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(243, 244, 239)');
  assert.deepEqual(await primary.evaluate(el=>({background:getComputedStyle(el).backgroundColor,text:getComputedStyle(el).color})),{background:'rgb(127, 137, 103)',text:'rgb(21, 24, 16)'});

  await page.reload();await page.getByRole('heading',{name:'Lodges',exact:true}).waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('navigation',{name:'Quick navigation'}).waitFor({state:'visible'});
  await page.getByRole('button',{name:'More',exact:true}).click();
  await page.getByRole('heading',{name:'Navigate SafariOS',exact:true}).waitFor();
  await page.getByRole('dialog').getByRole('link',{name:'Packages',exact:true}).waitFor();
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.getByRole('button',{name:'Open navigation',exact:true}).click();
  await page.getByRole('heading',{name:'Navigate SafariOS',exact:true}).waitFor();
  await page.keyboard.press('Escape');
 }finally{await context.close()}
});

test('command palette supports keyboard search and hides unauthorized modules',async()=>{
 const {context,page}=await accountPage({id:'staff',full_name:'Lodge Staff',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:'own',lodge_name:'Acacia Lodge',permissions:[],entitlements:[]}]});
 try{
  await page.goto(base+'/settings');await page.getByRole('heading',{name:'Security settings',exact:true}).waitFor();
  await page.keyboard.press('Control+k');await page.locator('[cmdk-input]').fill('Account Security');
  assert.equal(await page.getByRole('option',{name:'Account Security',exact:true}).count(),1);
  assert.equal(await page.getByRole('option',{name:'Platform Users',exact:true}).count(),0);
  await page.keyboard.press('Escape');await page.locator('[cmdk-input]').waitFor({state:'hidden'});
 }finally{await context.close()}
});

test('branding validates inline, reduced motion is respected, and glass screenshots render',async()=>{
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 await context.addInitScript(()=>{if(!localStorage.getItem('theme'))localStorage.setItem('theme','dark')});
 const page=await context.newPage();page.setDefaultTimeout(10000);
 await context.addCookies([{name:'lodge_session',value:'ui-only',url:base}]);
 const lodge={id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Acacia Lodge',location:'Maasai Mara, Kenya',subscription_status:'Active',subscription:{package:'Premium',expiry_date:'2027-10-20'},branding:{display_name:'Acacia Lodge',logo_url:null}};
 await page.route('**/api/**',route=>route.fulfill({json:route.request().url().endsWith('/auth/me')?{id:'owner',full_name:'Platform Owner',is_super_admin:true,mfa_enabled:true,memberships:[]}:route.request().url().includes('/platform/lodges')?[lodge]:[]}));
 try{
  await page.goto(base+'/super-admin/lodges');await page.getByRole('heading',{name:'Acacia Lodge',exact:true}).waitFor();
  assert.equal(await page.locator('.surfaceBackdrop i').first().evaluate(el=>getComputedStyle(el).animationName),'none');
  fs.mkdirSync(path.resolve(__dirname,'../docs/screenshots'),{recursive:true});
  const capture=async name=>{await page.waitForTimeout(200);await page.screenshot({path:path.resolve(__dirname,'../docs/screenshots',name),fullPage:true,animations:'disabled'})};
  assert.equal(await page.locator('.collectionToolbar .searchField').evaluate(el=>getComputedStyle(el).borderRadius),'10px');
  assert.ok(await page.locator('.collectionToolbar .searchField').evaluate(el=>el.getBoundingClientRect().height<=48));
  await capture('safarios-lodges.png');
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.getByRole('button',{name:'Manage branding',exact:true}).click();
  assert.equal(await page.locator('.glassOverlay').evaluate(el=>getComputedStyle(el).backdropFilter),'blur(12px)');
  assert.equal(await page.locator('.glassDialog .drawer').evaluate(el=>getComputedStyle(el).paddingLeft),'0px');
  await page.getByLabel('Workspace display name').fill('   ');await page.getByRole('button',{name:'Save branding',exact:true}).click();
  await page.getByText('Enter a workspace name.',{exact:true}).waitFor();
  await page.getByLabel('Workspace display name').fill('Acacia River Lodge');await page.getByLabel('Workspace display name').blur();
  await capture('safarios-branding.png');
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Toggle light and dark theme'}).click();await capture('safarios-lodges-light.png');
  const lightAudit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(lightAudit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.setViewportSize({width:390,height:844});await capture('safarios-lodges-mobile.png');
  await page.goto(base+'/login');await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();await capture('safarios-login-mobile.png');
  await page.setViewportSize({width:1440,height:1000});await capture('safarios-login.png');
  const loginAudit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(loginAudit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.route('**/api/**',route=>{const url=route.request().url();return route.fulfill({json:url.endsWith('/auth/me')?{id:'manager',full_name:'Lodge Manager',email:'manager@example.test',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:lodge.id,lodge_name:lodge.name,role:'Lodge Admin',subscription_status:'Active',permissions:['dashboard.view'],entitlements:['dashboard']}]}:url.endsWith('/dashboard')?{lodge:{name:lodge.name},metrics:{guests_in_house:0,arrivals_today:0,open_tasks:0,maintenance_open:0,activities_today:0,transfers_today:0,vehicles_unavailable:0,overdue_tasks:0},attention:[],events:[],subscription:{package:'Premium',status:'Active',expiry_date:'2027-10-20'}}:url.endsWith('/branding')?{display_name:lodge.name,logo_url:null}:[]})});
  await page.goto(base+'/dashboard');await page.getByRole('heading',{name:lodge.name,exact:true}).waitFor();
  await capture('safarios-workspace.png');await page.setViewportSize({width:390,height:844});await capture('safarios-workspace-mobile.png');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);

 }finally{await context.close()}
});

test('removing a lodge logo requires confirmation before any write',async()=>{
 const {context,page}=await accountPage({id:'owner',full_name:'Platform Owner',is_super_admin:true,mfa_enabled:true,memberships:[]});
 let writes=0;
 await page.route('**/api/v1/platform/lodges**',async route=>{if(route.request().method()==='PATCH'){writes++;await route.fulfill({json:{}})}else await route.fulfill({json:[{id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Acacia Lodge',location:'Kenya',subscription_status:'Active',branding:{display_name:'Acacia Lodge',logo_url:'/api/v1/lodges/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/branding/logo'}}]})});
 try{
  await page.goto(base+'/super-admin/lodges');await page.getByRole('button',{name:'Manage branding',exact:true}).click();
  await page.getByRole('checkbox',{name:'Remove existing logo'}).check();
  await page.getByRole('button',{name:'Save branding',exact:true}).click();
  await page.getByRole('heading',{name:'Remove this lodge logo?',exact:true}).waitFor();assert.equal(writes,0);
  await page.getByRole('button',{name:'Cancel',exact:true}).last().click();assert.equal(writes,0);
  await page.getByRole('button',{name:'Save branding',exact:true}).click();
  await page.getByRole('button',{name:'Confirm removal',exact:true}).click();
  await page.getByRole('heading',{name:'Manage branding',exact:true}).waitFor({state:'hidden'});assert.equal(writes,1);
 }finally{await context.close()}
});

test('invitation preview keeps token out of URLs and owner chooses matching password',async()=>{
 const context=await browser.newContext();const page=await context.newPage();page.setDefaultTimeout(10000);let activated;
 const token='test-invitation-token-at-least-20-characters';
 try{
  await page.route('**/api/**',async route=>{const url=route.request().url();assert.ok(!url.includes(token));
   if(url.endsWith('/invitations/preview')){assert.equal(route.request().postDataJSON().token,token);return route.fulfill({json:{name:'New Owner',email_hint:'o***@example.com',workspace:'Acacia Lodge',expires_at:'2027-01-01T00:00:00Z'}})}
   if(url.endsWith('/auth/activate')){activated=route.request().postDataJSON();await context.addCookies([{name:'lodge_session',value:'activated-test-session',url:base}]);return route.fulfill({json:{ok:true}})}
   if(url.endsWith('/auth/me'))return route.fulfill({json:{id:'owner',full_name:'New Owner',is_super_admin:false,memberships:[{lodge_id:'lodge',permissions:[],entitlements:[]}]}});
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/activate#token='+token);
  await page.getByText('Acacia Lodge',{exact:true}).waitFor();assert.equal(new URL(page.url()).hash,'');
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await page.screenshot({path:path.join(web,'../../docs/screenshots/safarios-invitation-light.png'),fullPage:true});
  await page.getByLabel('New password',{exact:true}).fill('My own private passphrase 42!');
  await page.getByLabel('Confirm password',{exact:true}).fill('A different passphrase 42!');
  await page.getByRole('button',{name:/activate|set.*password/i}).click();
  await page.getByText('Your passwords do not match.',{exact:true}).waitFor();assert.equal(activated,undefined);
  await page.getByLabel('Confirm password',{exact:true}).fill('My own private passphrase 42!');
  await page.getByRole('button',{name:/activate|set.*password/i}).click();
  await page.waitForURL('**/settings');assert.deepEqual(activated,{token,password:'My own private passphrase 42!'});
 }finally{await context.close()}
});

test('notification inbox updates unread count, archives and saves private preferences',async()=>{
 const {context,page}=await accountPage({id:'platform-owner',full_name:'Platform Owner',email:'owner@example.com',is_super_admin:true,mfa_enabled:true,memberships:[]});
 let read=false,archived=false,saved;
 try{
  await page.route('**/api/v1/auth/notification**',async route=>{const url=new URL(route.request().url()),p=url.pathname;
   if(p.endsWith('/summary'))return route.fulfill({json:{unread:read||archived?0:1}});
   if(p.endsWith('/notification-preferences')){if(route.request().method()==='PATCH')saved=route.request().postDataJSON();return route.fulfill({json:{email_enabled:true,email_min_severity:'normal',email_verified:true,email_configured:true,...saved}})}
   if(p.endsWith('/read'))read=true;else if(p.endsWith('/archive'))archived=true;else return route.fulfill({json:archived?[]:[{id:'notice-1',title:'Task needs attention',body:'Only your account can see this update.',severity:'high',created_at:'2026-10-20T12:00:00Z',read_at:read?'2026-10-20T12:01:00Z':null,email_status:'sent'}]});
   return route.fulfill({json:{ok:true}});
  });
  await page.goto(base+'/super-admin/notifications');await page.getByRole('heading',{name:'Task needs attention'}).waitFor();
  await page.getByRole('link',{name:'Notifications, 1 unread'}).waitFor();
  await page.evaluate(()=>document.documentElement.dataset.theme='light');await page.screenshot({path:path.join(web,'../../docs/screenshots/safarios-notifications-light.png'),fullPage:true});
  await page.getByRole('button',{name:'Mark read',exact:true}).click();await page.getByRole('link',{name:'Notifications',exact:true}).first().waitFor();
  await page.getByLabel('Email operational notifications').uncheck();await page.getByRole('button',{name:'Save preferences'}).click();await page.getByText('Notification preferences saved',{exact:true}).waitFor();assert.equal(saved.email_enabled,false);
  await page.getByRole('button',{name:'Archive Task needs attention'}).click();await page.getByRole('heading',{name:'No notifications here yet'}).waitFor();
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>document.documentElement.dataset.theme='dark');await page.getByRole('button',{name:'Close toast',exact:true}).click().catch(()=>{});await page.waitForTimeout(500);await page.screenshot({path:path.join(web,'../../docs/screenshots/safarios-notifications-mobile-dark.png'),fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)})),[]);
 }finally{await context.close()}
});

test('staff creation queues an invitation without choosing an owner password and supports resend',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
 const {context,page}=await accountPage({id:'lodge-owner',full_name:'Lodge Owner',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:lodge,permissions:['staff.view','staff.manage','staff.contact.view'],entitlements:['staff']}]});let created,resends=0;
 try{
  await page.route('**/api/v1/lodges/**',async route=>{const url=new URL(route.request().url()),p=url.pathname;
   if(p.endsWith('/invitation/resend')){resends++;return route.fulfill({json:{delivery_status:'pending'}})}
   if(p.endsWith('/staff')){if(route.request().method()==='POST'){created=route.request().postDataJSON();return route.fulfill({json:{id:'new-staff',delivery_status:'pending'}})}return route.fulfill({json:created?[{id:'new-staff',full_name:created.full_name,email:created.email,job_title:'',phone:'',employment_status:'active',operational_status:'available',has_login:true,account_status:'pending_activation',delivery_status:'pending'}]:[]})}
   if(p.endsWith('/branding'))return route.fulfill({json:{display_name:'Acacia Lodge',logo_url:null}});
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/staff');await page.getByRole('button',{name:'+ Staff member'}).click();
  assert.equal(await page.locator('select[name="role_key"] option[value="department_manager"]').count(),0);
  await page.locator('input[name="full_name"]').fill('Staff Owner');await page.locator('input[name="email"]').fill('owner@business.example');
  assert.equal(await page.locator('input[type="password"]').count(),0);
  await page.getByRole('button',{name:'Create and invite',exact:true}).click();
  await page.getByText('pending_activation',{exact:true}).waitFor();assert.equal(created.invite_role_key,'general_staff');assert.equal(created.email,'owner@business.example');assert.equal(created.password,undefined);
  await page.getByRole('button',{name:'Resend invitation',exact:true}).click();await page.getByText(/Replacement invitation pending/).waitFor();assert.equal(resends,1);
 }finally{await context.close()}
});

test('disabled modules and HR subfeatures stay hidden without forbidden requests; saving shows a popup',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
 const user={id:'hr-owner',full_name:'Lodge Owner',is_super_admin:false,memberships:[{lodge_id:lodge,permissions:['staff.view','staff.contact.view','staff.hr.view','staff.hr.manage','staff.roster.manage','staff.performance.manage','fuel.view'],entitlements:['staff','staff_hr']}]};
 const {context,page}=await accountPage(user);let saved=false,disabledCalls=0;
 try{
  await page.route('**/api/v1/lodges/**',async route=>{const p=new URL(route.request().url()).pathname;
   if(/\/(shifts|incidents|performance|fuel)$/.test(p)){disabledCalls++;return route.fulfill({status:403,json:{detail:'Feature is not enabled for this lodge subscription'}})}
   if(p.endsWith('/staff'))return route.fulfill({json:[{id:'staff-1',full_name:'Team Member',employment_status:'active',operational_status:'available'}]});
   if(p.endsWith('/hr/leaves')){if(route.request().method()==='POST'){saved=true;return route.fulfill({json:{id:'leave-1',status:'pending'}})}return route.fulfill({json:saved?[{id:'leave-1',staff_name:'Team Member',leave_type:'annual',start_date:'2026-11-01',end_date:'2026-11-02',status:'pending'}]:[]})}
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/hr');await page.getByRole('heading',{name:'Staff HR',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Roster',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Performance',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Incidents',exact:true}).count(),0);
  assert.equal(await page.getByRole('link',{name:'Fuel',exact:true}).count(),0);
  await page.locator('select[name="staff_id"]').selectOption('staff-1');await page.locator('input[name="start_date"]').fill('2026-11-01');await page.locator('input[name="end_date"]').fill('2026-11-02');
  await page.getByRole('button',{name:'Create request',exact:true}).click();await page.getByText('Saved successfully',{exact:true}).waitFor();await page.locator('.taskRow').getByText('Team Member',{exact:true}).waitFor();assert.equal(saved,true);assert.equal(await page.locator('input[name="start_date"]').inputValue(),'');
  await page.goto(base+'/fuel');await page.waitForURL('**/staff');assert.equal(disabledCalls,0);
 }finally{await context.close()}
});

test('Group Admin opens an assigned lodge and returns to the group without platform access',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',gid='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
 const user={id:'group-owner',full_name:'Group Owner',is_super_admin:false,groups:[{id:gid,name:'Safari Collection'}],memberships:[{lodge_id:lodge,lodge_name:'Acacia Lodge',role:'Group Admin',role_key:'group_admin',permissions:['tasks.view'],entitlements:['tasks']}]};
 const {context,page,requests}=await accountPage(user);
 try{
  await page.route('**/api/v1/groups/**',route=>route.fulfill({json:{id:gid,name:'Safari Collection',totals:{open_tasks:2},lodges:[{id:lodge,name:'Acacia Lodge',location:'Kenya',package:'Basic',subscription_status:'Active',metrics:{open_tasks:2}}]}}));
  await page.route('**/api/v1/lodges/**',route=>route.fulfill({json:new URL(route.request().url()).pathname.endsWith('/branding')?{display_name:'Acacia Lodge',logo_url:null}:[]}));
  await page.goto(base+'/group');await page.getByRole('heading',{name:'Safari Collection',exact:true}).waitFor();await page.screenshot({path:path.join(web,'../../docs/screenshots/safarios-group-overview.png'),fullPage:true});
  await page.getByRole('button',{name:'Open lodge',exact:true}).click();await page.waitForURL('**/tasks');await page.getByRole('heading',{name:'Tasks',exact:true}).waitFor();assert.equal(await page.evaluate(()=>localStorage.getItem('active_lodge_id')),lodge);
  await page.getByRole('link',{name:'Group overview',exact:true}).click();await page.waitForURL('**/group');await page.getByRole('heading',{name:'Safari Collection',exact:true}).waitFor();
  await page.goto(base+'/super-admin/groups');await page.getByRole('heading',{name:'Access denied',exact:true}).waitFor();assert.equal(requests.filter(u=>u.includes('/platform/')).length,0);
 }finally{await context.close()}
});

test('Super Admin creates a lodge group and confirms suspension with action feedback',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';const {context,page}=await accountPage({id:'platform-owner',full_name:'Platform Owner',is_super_admin:true,mfa_enabled:true,memberships:[]});let groups=[],created,suspensions=0;
 try{
  await page.route('**/api/v1/platform/lodges',route=>route.fulfill({json:[{id:lodge,name:'Acacia Lodge'}]}));
  await page.route('**/api/v1/platform/groups**',async route=>{const method=route.request().method();
   if(method==='POST'){created=route.request().postDataJSON();groups=[{id:'group-1',name:created.name,is_active:true,lodge_ids:created.lodge_ids,administrator:{id:'owner-1',name:created.admin_name,email:created.admin_email,account_status:'pending_activation'}}];return route.fulfill({json:{...groups[0],activation_email_queued:true,delivery_status:'pending'}})}
   if(method==='PATCH'){const body=route.request().postDataJSON();if(body.is_active===false)suspensions++;groups=[{...groups[0],...body}];return route.fulfill({json:groups[0]})}
   return route.fulfill({json:groups});
  });
  await page.goto(base+'/super-admin/groups');await page.getByRole('button',{name:'Create group',exact:true}).click();await page.getByLabel('Group name',{exact:true}).fill('Safari Collection');await page.getByLabel('Group Admin name',{exact:true}).fill('Collection Owner');await page.getByLabel('Group Admin email',{exact:true}).fill('owner@business.example');await page.getByLabel('Acacia Lodge',{exact:true}).check();
  await page.getByRole('button',{name:'Create group and invite',exact:true}).click();await page.getByRole('heading',{name:'Safari Collection',exact:true}).waitFor();await page.getByText('Invitation queued',{exact:true}).waitFor();assert.deepEqual(created.lodge_ids,[lodge]);assert.equal(created.admin_email,'owner@business.example');assert.equal(created.password,undefined);
  await page.getByRole('button',{name:'Suspend',exact:true}).click();await page.getByRole('heading',{name:'Suspend group access?',exact:true}).waitFor();assert.equal(suspensions,0);await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(suspensions,0);
  await page.getByRole('button',{name:'Suspend',exact:true}).click();await page.getByRole('button',{name:'Suspend group',exact:true}).click();await page.getByRole('button',{name:'Restore access',exact:true}).waitFor();assert.equal(suspensions,1);await page.getByText('Saved successfully',{exact:true}).waitFor();
 }finally{await context.close()}
});

test('Group Admin resends and removes or restores a Lodge Admin with clear popups',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',gid='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
 const user={id:'group-owner',full_name:'Group Owner',is_super_admin:false,groups:[{id:gid,name:'Safari Collection'}],memberships:[{lodge_id:lodge,role:'Group Admin',role_key:'group_admin',permissions:['tasks.view'],entitlements:['tasks']}]};
 const {context,page}=await accountPage(user);let enabled=true,resends=0,removed=0,restored=0;
 try{
  await page.route('**/api/v1/groups/**',route=>route.fulfill({json:{id:gid,name:'Safari Collection',totals:{},lodges:[{id:lodge,name:'Acacia Lodge',location:'Kenya',package:'Basic',subscription_status:'Active',metrics:{},administrators:[{id:'local-admin',name:'Local Owner',email:'local@business.example',access_enabled:enabled,account_status:'pending_activation'}]}]}}));
  await page.route('**/api/v1/lodges/**/administrators/**',route=>{const p=new URL(route.request().url()).pathname;if(p.endsWith('/resend'))resends++;if(p.endsWith('/revoke-access')){enabled=false;removed++}if(p.endsWith('/restore-access')){enabled=true;restored++}return route.fulfill({json:{ok:true,delivery_status:'pending'}})});
  await page.goto(base+'/group');await page.getByText('Local Owner',{exact:true}).waitFor();await page.getByRole('button',{name:'Resend invitation',exact:true}).click();await page.getByText('Invitation queued',{exact:true}).waitFor();assert.equal(resends,1);
  await page.getByRole('button',{name:'Remove access',exact:true}).click();await page.getByRole('heading',{name:'Remove Lodge Admin access?',exact:true}).waitFor();assert.equal(removed,0);await page.getByRole('dialog').getByRole('button',{name:'Remove access',exact:true}).click();await page.getByRole('button',{name:'Restore access',exact:true}).waitFor();await page.getByText('Account access removed',{exact:true}).waitFor();assert.equal(removed,1);
  await page.getByRole('button',{name:'Restore access',exact:true}).click();await page.getByRole('button',{name:'Resend invitation',exact:true}).waitFor();await page.getByText('Account access restored',{exact:true}).waitFor();assert.equal(restored,1);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 }finally{await context.close()}
});

test('scoped reports hide unavailable feature sections and handle restricted data',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';const {context,page}=await accountPage({id:'department-owner',full_name:'Department Manager',is_super_admin:false,memberships:[{lodge_id:lodge,role:'Department Manager',permissions:['reports.view'],entitlements:['reports','tasks']}]});
 try{
  await page.route('**/api/v1/lodges/**/reports/summary**',route=>route.fulfill({json:{tasks:{created:4,completed:2,completion_rate:50,average_completion_hours:3},maintenance:{created:1,completed:0,critical:0,cost_cents:0},guest_requests:{created:0,resolved:0},fleet:null,stays:null,rooms:null,safari:{activities:0,transfers:0,wildlife_sightings:null}}}));
  await page.goto(base+'/reports');await page.getByText('Tasks completed',{exact:true}).waitFor();assert.equal(await page.getByText('Fuel used',{exact:true}).count(),0);assert.equal(await page.getByRole('heading',{name:'Safari & Fleet',exact:true}).count(),0);assert.equal(await page.getByRole('heading',{name:'Room status now',exact:true}).count(),0);
  await page.getByRole('button',{name:'Run report',exact:true}).click();await page.getByText('Report updated',{exact:true}).waitFor();await page.getByText('Tasks completed',{exact:true}).waitFor();
 }finally{await context.close()}
});

test('login uses inline validation, password visibility and human API errors',async()=>{
  const context=await browser.newContext();const page=await context.newPage();
  try {
    let calls=0;
    await page.route('**/api/v1/auth/login',async route=>{calls++;await route.fulfill({status:422,json:{detail:[{type:'value_error',loc:['body','email'],msg:'value is not a valid email address',input:'private'}]}})});
    await page.goto(base+'/login');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByText('This field is required.').first().waitFor();assert.equal(calls,0);
    await page.getByLabel('Email',{exact:true}).fill('owner@example.com');
    await page.getByLabel('Password',{exact:true}).fill('long-test-passphrase');
    await page.getByRole('button',{name:'Show password',exact:true}).click();
    assert.equal(await page.getByLabel('Password',{exact:true}).getAttribute('type'),'text');
    await page.getByRole('button',{name:'Hide password',exact:true}).click();
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByText('Enter a valid email address.',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('Email',{exact:true}).getAttribute('aria-invalid'),'true');
    assert.equal(await page.getByText('value_error',{exact:false}).count(),0);
    assert.equal(await page.locator('form').getAttribute('novalidate'),'');
  } finally {await context.close()}
});

test('guest drawer labels, inline server validation and focus return',async()=>{
  const user={id:'guest-admin',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'guest-lodge',role_key:'lodge_admin',permissions:['guests.view','guests.manage'],entitlements:['guests']}]};
  const {context,page}=await accountPage(user);
  try {
    let calls=0;
    await page.route('**/api/v1/lodges/guest-lodge/guests',async route=>{
      if(route.request().method()==='POST'){calls++;await route.fulfill({status:422,json:{detail:[{loc:['body','email'],type:'value_error',msg:'invalid email'}]}})}else await route.fulfill({json:[]});
    });
    await page.goto(base+'/guests');await page.getByRole('button',{name:'+ Guest',exact:true}).click();
    await page.getByRole('button',{name:'Create guest',exact:true}).click();
    await page.getByText('This field is required.').first().waitFor();assert.equal(calls,0);
    await page.getByLabel('First name',{exact:false}).fill('Maya');await page.getByLabel('Last name',{exact:false}).fill('Laurent');
    await page.getByLabel('Email',{exact:true}).fill('maya@example.com');
    assert.equal(await page.getByLabel('Phone',{exact:true}).getAttribute('type'),'tel');
    await page.getByRole('button',{name:'Create guest',exact:true}).click();
    await page.getByText('Enter a valid email address.',{exact:true}).waitFor();
    await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
    await page.waitForFunction(()=>document.activeElement?.textContent==='+ Guest');
  } finally {await context.close()}
});

test('shared error formatter hides server internals and handles malformed validation details',()=>{
  const source=fs.readFileSync(path.join(web,'lib/api.ts'),'utf8');
  const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const copySource=fs.readFileSync(path.join(web,'lib/strings/forms.ts'),'utf8');
  const copyJs=ts.transpileModule(copySource,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const copy={};new Function('exports',copyJs)(copy);
  const output={};new Function('exports','require',js)(output,name=>name.includes('strings/forms')?copy:name.includes('action-feedback')?{actionFeedback:()=>{}}:name.includes('form-submission')?{originatingForm:()=>null}:{toast:{}});
  assert.equal(output.formatApiError(500,{detail:'psycopg SECRET'}).message,copy.formCopy.unavailable);
  assert.deepEqual(output.formatApiError(422,{detail:[null,{loc:['body','email'],msg:'email invalid'}]}).fieldErrors,{email:copy.formCopy.email});
  assert.equal(output.formatApiError(403,{detail:{private:'data'}}).message,copy.formCopy.forbidden);
});
