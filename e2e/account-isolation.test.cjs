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
  fs.cpSync(path.join(web,'public'),path.join(web,'.next/standalone/public'),{recursive:true});
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
    if(url.endsWith('/platform/plans')) return route.fulfill({json:['Basic','Standard','Premium'].map((key,i)=>({key,name:key,description:key==='Standard'?'Expanded lodge workflows, departments, staff HR, feedback and operational coordination.':'Daily lodge operations.',features:[],planned_features:[],feature_catalog:[],revision:1,lodge_count:i+1}))});
    if(url.endsWith('/role-catalog'))return route.fulfill({json:{default_staff_role_key:'general_staff',presets:[{key:'general_staff',name:'General Staff',description:'Own assigned work',assignable:true,permission_keys:[],copy_base_role_key:'general_staff',copy_permission_keys:[]}],permissions:[],scopes:[],can_manage_custom_roles:false}});
    if(url.endsWith('/api/v1/auth/me'))await route.fulfill({json:user});
    else{requests.push(url);await route.fulfill({json:[]})}
  });
  return {context,page,requests};
}

async function openAccountMenu(page){
 const desktop=page.locator('.sidebar .userMenu summary');
 const control=await desktop.isVisible()?desktop:page.locator('.mobileUserMenu .userMenu summary');
 if((await control.locator('..').getAttribute('open'))===null)await control.click();
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
    await openAccountMenu(page);await page.getByRole('button',{name:'Sign out',exact:true}).click();
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
  assert.equal(await page.locator('html').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(23, 24, 28)');
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(18, 19, 23)');
  assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(23, 24, 28)');
  assert.equal(await page.locator('.surfaceBackdrop i').first().evaluate(el=>getComputedStyle(el).display),'none');
  assert.equal(await page.locator('.sidebar .navItem.active .navIcon').evaluate(el=>getComputedStyle(el).color),'rgb(240, 236, 226)');
  assert.equal(await page.locator('.propertyCard').count(),0);
  assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).backdropFilter),'none');
  const primary=page.getByRole('button',{name:/Register lodge/});
  assert.deepEqual(await primary.evaluate(el=>({background:getComputedStyle(el).backgroundColor,text:getComputedStyle(el).color})),{background:'rgb(196, 160, 103)',text:'rgb(23, 24, 28)'});
  assert.match(await page.getByRole('heading',{name:'Lodges',exact:true}).evaluate(el=>getComputedStyle(el).fontFamily),/^"?Outfit"?(?:,|$)/);
  assert.match(await page.locator('body').evaluate(el=>getComputedStyle(el).fontFamily),/Inter/);

  assert.equal(await page.locator('.sidebar').evaluate(el=>Math.round(el.getBoundingClientRect().left)),0);
  await page.getByRole('button',{name:'Collapse sidebar',exact:true}).click();
  assert.equal(await page.locator('html').getAttribute('data-sidebar'),'collapsed');
  assert.equal(await page.evaluate(()=>{const button=document.querySelector('.collapseSidebar').getBoundingClientRect(),mark=document.querySelector('.sidebar .safariMark').getBoundingClientRect();return button.left>=mark.right||button.top>=mark.bottom||button.bottom<=mark.top}),true,'collapsed navigation control must not overlap the brand');
  await page.getByRole('button',{name:'Expand sidebar',exact:true}).click();
  await openAccountMenu(page);await page.getByRole('button',{name:'Toggle light and dark theme'}).click();await page.keyboard.press('Escape');
  assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  assert.equal(await page.locator('html').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(246, 243, 236)');
  assert.deepEqual(await primary.evaluate(el=>({background:getComputedStyle(el).backgroundColor,text:getComputedStyle(el).color})),{background:'rgb(196, 160, 103)',text:'rgb(23, 24, 28)'});

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
  assert.equal(await page.locator('.collectionToolbar .searchField').evaluate(el=>getComputedStyle(el).borderRadius),'12px');
  assert.ok(await page.locator('.collectionToolbar .searchField').evaluate(el=>el.getBoundingClientRect().height<=48));
  await capture('safarios-lodges.png');
  const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.getByRole('button',{name:'Manage branding',exact:true}).click();
  assert.equal(await page.locator('.glassOverlay').evaluate(el=>getComputedStyle(el).backdropFilter),'blur(8px)');
  assert.equal(await page.locator('.glassDialog .drawer').evaluate(el=>getComputedStyle(el).paddingLeft),'0px');
  await page.getByLabel('Workspace display name').fill('   ');await page.getByRole('button',{name:'Save branding',exact:true}).click();
  await page.getByText('Enter a workspace name.',{exact:true}).waitFor();
  await page.getByLabel('Workspace display name').fill('Acacia River Lodge');await page.getByLabel('Workspace display name').blur();
  await capture('safarios-branding.png');
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
  await openAccountMenu(page);await page.getByRole('button',{name:'Toggle light and dark theme'}).click();await page.keyboard.press('Escape');await capture('safarios-lodges-light.png');
  const lightAudit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(lightAudit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.setViewportSize({width:390,height:844});await capture('safarios-lodges-mobile.png');
  await page.goto(base+'/login');await page.getByRole('button',{name:'Sign in',exact:true}).waitFor();await capture('safarios-login-mobile.png');
  await page.setViewportSize({width:1440,height:1000});await capture('safarios-login.png');
  const loginAudit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(loginAudit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);
  await page.route('**/api/**',route=>{const url=route.request().url();return route.fulfill({json:url.endsWith('/auth/me')?{id:'manager',full_name:'Lodge Manager',email:'manager@example.test',is_super_admin:false,mfa_enabled:false,memberships:[{lodge_id:lodge.id,lodge_name:lodge.name,role:'Lodge Admin',subscription_status:'Active',permissions:['dashboard.view'],entitlements:['dashboard']}]}:url.endsWith('/dashboard')?{lodge:{name:lodge.name},metrics:{guests_in_house:0,arrivals_today:0,open_tasks:0,maintenance_open:0,activities_today:0,transfers_today:0,vehicles_unavailable:0,overdue_tasks:0},attention:[],events:[],subscription:{package:'Premium',status:'Active',expiry_date:'2027-10-20'}}:url.endsWith('/branding')?{display_name:lodge.name,logo_url:null}:[]})});
  await page.goto(base+'/dashboard');await page.getByRole('heading',{name:/Good (morning|afternoon|evening), Lodge/}).waitFor();
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
  await page.getByRole('button',{name:'Cancel',exact:true}).last().click();assert.equal(writes,0);await page.waitForFunction(()=>document.activeElement?.textContent==='Save branding');
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
   if(p.endsWith('/role-catalog'))return route.fulfill({json:{default_staff_role_key:'general_staff',presets:[{key:'general_staff',name:'General Staff',description:'Own assigned work',assignable:true,permission_keys:[],copy_base_role_key:'general_staff',copy_permission_keys:[]}],can_manage_custom_roles:false}});
   if(p.endsWith('/staff')){if(route.request().method()==='POST'){created=route.request().postDataJSON();return route.fulfill({json:{id:'new-staff',delivery_status:'pending'}})}return route.fulfill({json:created?[{id:'new-staff',full_name:created.full_name,email:created.email,job_title:'',phone:'',employment_status:'active',operational_status:'available',has_login:true,account_status:'pending_activation',delivery_status:'pending'}]:[]})}
   if(p.endsWith('/branding'))return route.fulfill({json:{display_name:'Acacia Lodge',logo_url:null}});
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/staff');await page.getByRole('button',{name:'+ Staff member'}).click();
  assert.equal(await page.locator('select[name="role_key"] option[value="department_manager"]').count(),0);
  await page.locator('input[name="full_name"]').fill('Staff Owner');await page.locator('input[name="email"]').fill('owner@business.example');
  assert.equal(await page.locator('input[type="password"]').count(),0);
  await page.getByRole('button',{name:'Create and invite',exact:true}).click();
  await page.getByText('Awaiting account activation',{exact:true}).waitFor();assert.equal(created.invite_role_key,'general_staff');assert.equal(created.email,'owner@business.example');assert.equal(created.password,undefined);
  await page.getByRole('button',{name:'Resend invitation',exact:true}).click();await page.getByText(/Replacement invitation Pending/).waitFor();assert.equal(resends,1);
 }finally{await context.close()}
});

test('locked modules and hidden HR subfeatures avoid forbidden requests; saving shows a popup',async()=>{
 const lodge='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
 const user={id:'hr-owner',full_name:'Lodge Owner',is_super_admin:false,memberships:[{lodge_id:lodge,permissions:['staff.view','staff.contact.view','staff.hr.view','staff.hr.manage','staff.roster.manage','staff.performance.manage','fuel.view'],entitlements:['staff','staff_hr']}]};
 const {context,page}=await accountPage(user);let saved=false,disabledCalls=0;
 try{
  await page.route('**/api/v1/lodges/**',async route=>{const p=new URL(route.request().url()).pathname;
   if(p.endsWith('/feature-access'))return route.fulfill({json:{feature:{name:'Fuel',description:'Fuel records'},status:'plan_required',unlocking_plans:[{key:'Standard',name:'Standard'}]}});
   if(/\/(shifts|incidents|performance|fuel)$/.test(p)){disabledCalls++;return route.fulfill({status:403,json:{detail:'Feature is not enabled for this lodge subscription'}})}
   if(p.endsWith('/staff'))return route.fulfill({json:[{id:'staff-1',full_name:'Team Member',employment_status:'active',operational_status:'available'}]});
   if(p.endsWith('/hr/leaves')){if(route.request().method()==='POST'){saved=true;return route.fulfill({json:{id:'leave-1',status:'pending'}})}return route.fulfill({json:saved?[{id:'leave-1',staff_name:'Team Member',leave_type:'annual',start_date:'2026-11-01',end_date:'2026-11-02',status:'pending'}]:[]})}
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/hr');await page.getByRole('heading',{name:'Staff HR',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Roster',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Performance',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Incidents',exact:true}).count(),0);
  await page.getByRole('button',{name:'Safari & Fleet',exact:true}).click();assert.equal(await page.getByRole('link',{name:'Fuel',exact:true}).count(),1);
  await page.locator('select[name="staff_id"]').selectOption('staff-1');await page.locator('input[name="start_date"]').fill('2026-11-01');await page.locator('input[name="end_date"]').fill('2026-11-02');
  await page.getByRole('button',{name:'Create request',exact:true}).click();await page.getByText('Leave request created',{exact:true}).waitFor();await page.locator('.taskRow').getByText('Team Member',{exact:true}).waitFor();assert.equal(saved,true);assert.equal(await page.locator('input[name="start_date"]').inputValue(),'');
  await page.goto(base+'/fuel');await page.getByRole('heading',{name:'Available on Standard',exact:true}).waitFor();assert.equal(new URL(page.url()).pathname,'/fuel');assert.equal(disabledCalls,0);
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
  await page.getByRole('button',{name:'Suspend',exact:true}).click();await page.getByRole('button',{name:'Suspend group',exact:true}).click();await page.getByRole('button',{name:'Restore access',exact:true}).waitFor();assert.equal(suspensions,1);await page.getByText('Lodge group updated',{exact:true}).waitFor();
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
  assert.deepEqual(output.formatApiError(422,{detail:[{loc:['body','timezone'],type:'value_error',msg:'secret internal detail'},{loc:['body','capacity'],type:'greater_than_equal',ctx:{ge:1}},{loc:['body','start_date'],type:'date_from_datetime_parsing'}]}).fieldErrors,{timezone:copy.formCopy.timezoneChoice,capacity:copy.formCopy.minimum(1),start_date:copy.formCopy.date});
});

test('empty lodge shows permission-aware setup and hides single-lodge selector',async()=>{
 const lodge='setup-lodge';const {context,page,requests}=await accountPage({id:'setup-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:lodge,lodge_name:'New Lodge',role_key:'lodge_admin',permissions:['dashboard.view','units.view','units.manage','guests.view','guests.manage','staff.view','staff.manage','stays.view','stays.manage'],entitlements:['dashboard','units','guests','staff','stays']}]});
 try {
  await page.route('**/api/v1/lodges/setup-lodge/staff',r=>r.fulfill({json:[{id:'profile-only',full_name:'Profile without an account',has_login:false}]}));
  await page.route('**/api/v1/lodges/setup-lodge/dashboard',r=>r.fulfill({json:{lodge:{name:'New Lodge'},metrics:{},events:[]}}));
  await page.goto(base+'/dashboard');await page.getByRole('heading',{name:'Make this lodge your own'}).waitFor();await page.getByText('0 of 4 essentials ready').waitFor();
  assert.equal(await page.getByLabel('ACTIVE LODGE',{exact:true}).count(),0);
  assert.equal(await page.getByText('Operational pulse',{exact:true}).count(),0);
  assert.equal(requests.filter(x=>x.endsWith('/activities')).length,0);
  await page.getByRole('link',{name:'Add rooms',exact:true}).click();await page.waitForURL('**/rooms');
 } finally {await context.close()}
});

test('maintenance creation uses a focus-managed drawer',async()=>{
 const {context,page}=await accountPage({id:'maintenance-owner',full_name:'Owner',is_super_admin:false,memberships:[{lodge_id:'maintenance-lodge',permissions:['maintenance.view','maintenance.manage'],entitlements:['maintenance']}]});
 try {await page.goto(base+'/maintenance');await page.getByRole('button',{name:'+ Add ticket',exact:true}).click();await page.getByRole('dialog').waitFor();await page.getByLabel('Title',{exact:true}).fill('Inspect pump');await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});await page.waitForFunction(()=>document.activeElement?.textContent==='+ Add ticket');} finally {await context.close()}
});

test('MFA enrolment renders a local QR, shows codes once, downloads and regenerates',async()=>{
 let enabled=false,regenerated=0;const user={id:'mfa-owner',full_name:'Owner',is_super_admin:true,mfa_enabled:false,memberships:[]};
 const {context,page}=await accountPage(user);const codes=Array.from({length:10},(_,i)=>`ABCDE-ABCDE-ABCDE-${String(i).padStart(5,'0')}`);
 try{
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{...user,mfa_enabled:enabled}}));
  await page.route('**/api/v1/auth/mfa/**',async r=>{const p=new URL(r.request().url()).pathname;assert.equal(r.request().method(),'POST');
   if(p.endsWith('/setup'))return r.fulfill({json:{secret:'JBSWY3DPEHPK3PXP',otpauth_uri:'otpauth://totp/SafariOS%3Aowner%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=SafariOS'}});
   if(p.endsWith('/confirm')){enabled=true;return r.fulfill({json:{enabled:true,recovery_codes:codes}})}
   if(p.endsWith('/recovery-codes')){regenerated++;assert.equal(r.request().postDataJSON().current_password,'Secure-test-passphrase');return r.fulfill({json:{recovery_codes:codes.map(x=>x.replace('ABCDE','BCDEF'))}})}
   throw Error('Unexpected MFA request');
  });
  await page.goto(base+'/settings');await page.getByText('Your invitation is activated.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Set up authenticator',exact:true}).click();
  const qr=page.getByRole('img',{name:'SafariOS authenticator setup QR code',exact:true});await qr.waitFor();assert.match(await qr.getAttribute('src'),/^data:image\/png;base64,/);
  await page.getByLabel('6-digit authenticator code',{exact:true}).fill('123456');await page.getByRole('button',{name:'Confirm MFA',exact:true}).click();
  await page.getByRole('heading',{name:'Save your recovery codes',exact:true}).waitFor();
  const downloading=page.waitForEvent('download');await page.getByRole('button',{name:'Download recovery codes',exact:true}).click();const download=await downloading;
  assert.equal(download.suggestedFilename(),'safarios-recovery-codes.txt');const contents=fs.readFileSync(await download.path(),'utf8');assert.ok(contents.includes(codes[9]));
  assert.equal(await page.evaluate(code=>JSON.stringify(localStorage).includes(code),codes[0]),false);
  await page.getByRole('button',{name:'I have saved my codes',exact:true}).click();assert.equal(await page.getByText(codes[0],{exact:true}).count(),0);
  await page.getByRole('button',{name:'Generate new recovery codes',exact:true}).click();await page.getByLabel('6-digit authenticator code',{exact:true}).fill('234567');await page.getByLabel('Current password',{exact:true}).fill('Secure-test-passphrase');await page.getByRole('button',{name:'Generate new recovery codes',exact:true}).click();await page.getByText(codes[0].replace('ABCDE','BCDEF'),{exact:true}).waitFor();assert.equal(regenerated,1);
  await page.reload();await page.getByRole('heading',{name:'Security settings',exact:true}).waitFor();assert.equal(await page.getByRole('heading',{name:'Save your recovery codes',exact:true}).count(),0);
 }finally{await context.close()}
});

test('login offers a recovery code after the password challenge',async()=>{
 const {context,page}=await accountPage({id:'mfa-user',full_name:'User',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'mfa-lodge',permissions:['tasks.view'],entitlements:['tasks']}]});let body;
 try{
  await page.route('**/api/v1/auth/login',async r=>{body=r.request().postDataJSON();return body.recovery_code?r.fulfill({json:{ok:true}}):r.fulfill({status:401,json:{detail:'MFA_REQUIRED'}})});
  await page.goto(base+'/login');await page.getByLabel('Email',{exact:true}).fill('owner@example.com');await page.getByLabel('Password',{exact:true}).fill('Secure-test-passphrase');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Use a recovery code',exact:true}).click();
  await page.getByLabel('Recovery code',{exact:true}).fill('ABCDE-ABCDE-ABCDE-ABCDE');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/tasks');assert.equal(body.recovery_code,'ABCDE-ABCDE-ABCDE-ABCDE');assert.equal(body.otp,undefined);
 }finally{await context.close()}
});

test('read-only rooms, stays and requests do not call unauthorized lookup endpoints',async()=>{
 for(const [module,feature,permission,title] of [['rooms','units','units.view','Rooms & Units'],['stays','stays','stays.view','Stays'],['requests','guest_requests','requests.view','Guest Requests']]){
  const {context,page,requests}=await accountPage({id:'scoped-'+module,full_name:'Reader',is_super_admin:false,memberships:[{lodge_id:'scope-lodge',permissions:[permission],entitlements:[feature,'guests','units','departments','staff']}]});
  try{await page.goto(base+'/'+module);await page.getByRole('heading',{name:title,exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:/^\+ /}).count(),0);assert.deepEqual(requests.filter(x=>!x.endsWith('/branding')&&!x.endsWith('/'+module)),[]);}finally{await context.close()}
 }
});

test('lodge registration defaults dates and searchable timezone, formats errors and confirms success',async()=>{
 const {context,page}=await accountPage({id:'registrar',full_name:'Registrar',is_super_admin:true,mfa_enabled:true,memberships:[]});let calls=0,created;
 try {
  await page.route('**/api/v1/platform/lodges',async r=>{
   if(r.request().method()==='POST'){calls++;const body=r.request().postDataJSON();if(calls===1)return r.fulfill({status:422,json:{detail:[{loc:['body','admin_email'],type:'value_error',msg:'invalid email address'}]}});created=body;return r.fulfill({json:{id:'registered-lodge',activation_email_queued:true,delivery_status:'pending'}})}
   return r.fulfill({json:created?[{id:'registered-lodge',name:created.name,location:created.location,subscription_status:'Active',subscription:{package:created.package,expiry_date:created.expiry_date}}]:[]});
  });
  await page.goto(base+'/super-admin/lodges');await page.getByRole('button',{name:'+ Register lodge',exact:true}).click();
  assert.equal(await page.getByLabel('Time zone',{exact:true}).inputValue(),await page.evaluate(()=>Intl.DateTimeFormat().resolvedOptions().timeZone));assert.equal(await page.getByLabel('Time zone',{exact:true}).getAttribute('role'),'combobox');
  await page.getByLabel('Time zone',{exact:true}).fill('Not a real zone');await page.getByRole('status').filter({hasText:'No matching time zones'}).waitFor();
  await page.getByLabel('Time zone',{exact:true}).fill('Karachi');await page.getByRole('option',{name:'Asia/Karachi',exact:true}).click();assert.equal(await page.getByLabel('Time zone',{exact:true}).inputValue(),'Asia/Karachi');
  await page.getByLabel('Time zone',{exact:true}).focus();await page.keyboard.press('ArrowDown');assert.equal(await page.getByLabel('Time zone',{exact:true}).getAttribute('aria-expanded'),'true');await page.keyboard.press('Escape');assert.equal(await page.getByLabel('Time zone',{exact:true}).getAttribute('aria-expanded'),'false');await page.getByLabel('Time zone',{exact:true}).click();assert.equal(await page.getByLabel('Time zone',{exact:true}).getAttribute('aria-expanded'),'true');await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),1);
  await page.getByLabel('Lodge name',{exact:true}).fill('Test River Lodge');
  await page.getByLabel('Time zone',{exact:true}).fill('Unknown/Region');await page.getByRole('button',{name:'Continue',exact:true}).click();await page.getByText('Choose a time zone from the list.',{exact:true}).waitFor();assert.equal(calls,0);
  await page.getByLabel('Time zone',{exact:true}).fill('Karachi');await page.getByRole('option',{name:'Asia/Karachi',exact:true}).click();await page.getByRole('button',{name:'Continue',exact:true}).click();
  const start=await page.getByLabel('Start date',{exact:true}).inputValue(),expiry=await page.getByLabel('Expiry date',{exact:true}).inputValue();assert.ok(start);assert.equal(Number(expiry.slice(0,4)),Number(start.slice(0,4))+1);
  await page.getByLabel('Package',{exact:true}).selectOption('Standard');await page.getByText('Expanded lodge workflows, departments, staff HR, feedback and operational coordination.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Continue',exact:true}).click();await page.getByLabel('Full name',{exact:true}).fill('Lodge Owner');await page.getByLabel('Email address',{exact:true}).fill('owner@example.com');
  await page.getByRole('button',{name:'Register lodge',exact:true}).click();await page.getByText('Enter a valid email address.',{exact:true}).waitFor();assert.equal(await page.getByLabel('Email address',{exact:true}).getAttribute('aria-invalid'),'true');
  await page.getByLabel('Email address',{exact:true}).fill('newowner@example.com');await page.getByRole('button',{name:'Register lodge',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await page.getByText('Lodge registered',{exact:true}).waitFor();assert.equal(created.package,'Standard');assert.equal(created.start_date,start);assert.equal(created.timezone,'Asia/Karachi');
 }finally{await context.close()}
});

test('guest creation uses a country picker and a specific confirmation',async()=>{
 const {context,page}=await accountPage({id:'guest-writer',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'guest-create',permissions:['guests.view','guests.manage'],entitlements:['guests']}]});let created;
 try{
  await page.route('**/api/v1/lodges/guest-create/guests',async r=>{if(r.request().method()==='POST'){created=r.request().postDataJSON();return r.fulfill({json:{id:'guest-1',...created}})}return r.fulfill({json:created?[{id:'guest-1',...created,name:created.first_name+' '+created.last_name,completed_stays:0}]:[]})});
  await page.goto(base+'/guests');await page.getByRole('button',{name:'+ Guest',exact:true}).click();await page.getByLabel('First name',{exact:true}).fill('Maya');await page.getByLabel('Last name',{exact:true}).fill('Laurent');await page.getByLabel('Nationality',{exact:true}).selectOption('Kenya');await page.getByRole('button',{name:'Create guest',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await page.getByText('Guest created',{exact:true}).waitFor();await page.getByText('Maya Laurent',{exact:true}).waitFor();assert.equal(created.nationality,'Kenya');
 }finally{await context.close()}
});

test('lodge preferences save only allowed fields and apply date and currency formatting',async()=>{
 const {context,page}=await accountPage({id:'format-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'format-lodge',role_key:'lodge_admin',permissions:['lodge.settings.manage','fuel.view'],entitlements:['fuel']}]});let preferences={date_format:'locale',currency:'ZAR',timezone:'Africa/Johannesburg'},saved;
 try{
  await page.route('**/api/v1/lodges/format-lodge/preferences',async r=>{if(r.request().method()==='PATCH'){saved=r.request().postDataJSON();preferences={...preferences,...saved}}return r.fulfill({json:preferences})});
  await page.goto(base+'/settings');await page.getByLabel('Date format',{exact:true}).selectOption('dd/MM/yyyy');await page.getByLabel('Currency',{exact:true}).selectOption('USD');await page.getByRole('button',{name:'Save lodge preferences',exact:true}).click();await page.getByText('Lodge preferences saved',{exact:true}).waitFor();assert.deepEqual(saved,{currency:'USD',date_format:'dd/MM/yyyy'});
  await page.route('**/api/v1/auth/me',r=>r.fulfill({json:{id:'format-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'format-lodge',permissions:['fuel.view'],entitlements:['fuel'],...preferences}]}}));
  await page.route('**/api/v1/lodges/format-lodge/fuel',r=>r.fulfill({json:[{id:'fuel-1',recorded_at:'2026-10-22T12:00:00Z',litres:10,odometer_km:100,cost_cents:12345,vehicle_name:'Cruiser',fuel_type:'diesel'}]}));
  await page.goto(base+'/fuel');await page.getByText('$123.45',{exact:true}).waitFor();await page.getByText(/^22\/10\/2026 · (14:00|2:00 PM)$/).waitFor();
 }finally{await context.close()}
});

test('date-only values retain their calendar day and event labels hide technical keys',()=>{
 const vm=require('node:vm');
 function load(file,extras={}){const exports={};const source=fs.readFileSync(path.join(web,file),'utf8');const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;vm.runInNewContext(js,{exports,...extras});return exports}
 const stored=new Map([['active_user_id','u'],['active_lodge_id','l'],['lodge-format:u:l',JSON.stringify({date_format:'dd/MM/yyyy',timezone:'America/Los_Angeles',currency:'USD'})]]);
 const formats=load('lib/formatting.ts',{window:{},localStorage:{getItem:key=>stored.get(key),setItem:(key,value)=>stored.set(key,value)},navigator:{language:'en-GB'}});
 assert.equal(formats.formatDate('2026-10-22'),'22/10/2026');assert.equal(formats.formatDate('not-a-date'),'—');
 formats.storeFormatting({date_format:'yyyy-MM-dd',timezone:'Legacy/Invalid',currency:'USD'});assert.equal(formats.formatDate('2026-10-22'),'2026-10-22');assert.doesNotThrow(()=>formats.formatDateTime('2026-10-22T12:00:00Z'));
 const labels=load('lib/strings/content.ts');assert.equal(labels.readableLabel('development_link'),'Invitation link ready');assert.equal(labels.eventLabel('lodge.created','lodge.created . lodge').title,'Lodge created');assert.equal(labels.eventLabel('task.completed').title,'Task completed');
});

test('premium shared surfaces stay accessible at all requested widths and both themes',async()=>{
 const lodges={id:'visual-admin',full_name:'Visual Admin',is_super_admin:true,mfa_enabled:true,memberships:[]};
 const {context,page}=await accountPage(lodges);
 try{
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){
   await page.setViewportSize({width,height:1000});await page.addInitScript(theme=>localStorage.setItem('theme',theme),theme);
   await page.goto(base+'/super-admin/lodges');await page.getByRole('button',{name:'+ Register lodge',exact:true}).click();await page.getByLabel('Lodge name',{exact:true}).waitFor();
   await page.waitForTimeout(450);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`page overflow at ${width}/${theme}`);
   const dialog=page.getByRole('dialog');const box=await dialog.boundingBox();assert.ok(box&&box.x>=-1&&box.x+box.width<=width+1,`dialog overflow at ${width}/${theme}`);
   await dialog.evaluate(el=>{const controls=[...el.querySelectorAll('button,input,select,textarea,a[href]')].filter(x=>!x.disabled&&x.tabIndex>=0&&x.getClientRects().length);controls[controls.length-1].focus()});await page.keyboard.press('Tab');assert.ok(await dialog.evaluate(el=>el.contains(document.activeElement)),'dialog must trap keyboard focus');
   const submitBox=await page.getByRole('button',{name:'Continue',exact:true}).boundingBox();assert.ok(submitBox&&submitBox.y>=0&&submitBox.y+submitBox.height<=1001,`sticky action offscreen at ${width}/${theme}`);
   const material=await dialog.evaluate(el=>({radius:parseFloat(getComputedStyle(el).borderTopLeftRadius),blur:getComputedStyle(el).backdropFilter}));assert.ok(material.radius>=24);assert.match(material.blur,/blur/);
   await page.getByLabel('Lodge name',{exact:true}).focus();await page.screenshot({path:path.join(web,`../../docs/screenshots/safarios-registration-${width}-${theme}.png`),fullPage:true});
   if(width===375||width===1440){const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],`registration accessibility at ${width}/${theme}`)}
   await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
  }
 }finally{await context.close()}
 const {context:guestContext,page:guestPage}=await accountPage({id:'visual-lodge',full_name:'Lodge Admin',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'visual-lodge',role_key:'lodge_admin',permissions:['guests.view','guests.manage'],entitlements:['guests']}]});
 try{
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){
   await guestPage.setViewportSize({width,height:1000});await guestPage.addInitScript(theme=>localStorage.setItem('theme',theme),theme);await guestPage.goto(base+'/guests');await guestPage.getByRole('button',{name:'+ Guest',exact:true}).click();await guestPage.getByLabel('Nationality',{exact:true}).waitFor();await guestPage.waitForTimeout(450);
   assert.ok(await guestPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`guest page overflow at ${width}/${theme}`);
   const guestAction=await guestPage.getByRole('button',{name:'Create guest',exact:true}).boundingBox();assert.ok(guestAction&&guestAction.y>=0&&guestAction.y+guestAction.height<=1001,`guest sticky action offscreen at ${width}/${theme}`);
   await guestPage.screenshot({path:path.join(web,`../../docs/screenshots/safarios-guest-${width}-${theme}.png`),fullPage:true});
   if(width===375||width===1440){const violations=(await new AxeBuilder({page:guestPage}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],`guest accessibility at ${width}/${theme}`)}
   await guestPage.keyboard.press('Escape');await guestPage.getByRole('dialog').waitFor({state:'hidden'});
  }
 }finally{await guestContext.close()}
});

test('guest profile edits show inline errors and read-only accounts cannot edit',async()=>{
 const guest={id:'guest-profile',name:'Maya Laurent',first_name:'Maya',last_name:'Laurent',phone:'',nationality:'Kenya',vip:false,dietary_requirements:'',allergies:'',preferences:'',notes:'',completed_stays:0};
 for(const manage of [true,false]){
  const {context,page}=await accountPage({id:'profile-'+manage,full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'profile-lodge',permissions:['guests.view',...(manage?['guests.manage']:[])],entitlements:['guests']}]});let writes=0;
  try{
   await page.route('**/api/v1/lodges/profile-lodge/guests**',async r=>{if(r.request().url().includes('/communications'))return r.fulfill({json:{items:[],has_more:false}});if(r.request().method()==='PATCH'){writes++;return r.fulfill({status:422,json:{detail:[{loc:['body','notes'],type:'string_too_long',ctx:{max_length:4000}}]}})}return r.fulfill({json:[guest]})});
   await page.goto(base+'/guests');await page.getByRole('button',{name:'Maya Laurent',exact:true}).click();await page.getByRole('dialog').waitFor();
   if(manage){await page.getByLabel('Internal notes',{exact:true}).fill('Updated notes');await page.getByRole('button',{name:'Save profile',exact:true}).click();await page.getByText('Use no more than 4000 characters.',{exact:true}).waitFor();assert.equal(await page.getByLabel('Internal notes',{exact:true}).getAttribute('aria-invalid'),'true');assert.equal(writes,1)}
   else {assert.equal(await page.getByRole('button',{name:'Save profile',exact:true}).count(),0);assert.equal(await page.getByLabel('Internal notes',{exact:true}).isDisabled(),true);assert.equal(await page.getByRole('button',{name:'+ Guest',exact:true}).count(),0);assert.equal(writes,0)}
  }finally{await context.close()}
 }
});

test('role preset copy edits, staff assignment and deactivation use server metadata',async()=>{
 const lodge='role-lodge';const user={id:'role-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:lodge,permissions:['staff.view','staff.manage','roles.custom.manage'],entitlements:['staff','custom_roles']}]};
 const {context,page}=await accountPage(user);let roles=[],assigned=null,updates=0;
 const catalog={default_staff_role_key:'general_staff',can_manage_custom_roles:true,presets:[{key:'general_staff',name:'General Staff',description:'Assigned tasks',permission_keys:['tasks.view'],copy_permission_keys:['tasks.view'],copy_base_role_key:'general_staff',assignable:true}],scopes:[{key:'general_staff',label:'Only their own work',description:'Assigned tasks only.'}],permissions:[{key:'tasks.view',label:'View tasks',area:'tasks',area_name:'Tasks',level:'view',can_grant:true},{key:'tasks.own.manage',label:'Update assigned tasks',area:'tasks',area_name:'Tasks',level:'edit',can_grant:true}]};
 try {
  await page.route('**/api/v1/lodges/role-lodge/**',async r=>{const path=new URL(r.request().url()).pathname;
   if(path.endsWith('/role-catalog'))return r.fulfill({json:catalog});
   if(path.includes('/custom-roles')){if(r.request().method()==='POST'){const body=r.request().postDataJSON();assert.deepEqual(body.permission_keys,['tasks.view']);roles=[{id:'role-1',...body,is_active:true,staff_count:0}];return r.fulfill({json:{id:'role-1'}})}if(r.request().method()==='PATCH'){const body=r.request().postDataJSON();updates++;roles=[{...roles[0],...body}];if(body.is_active===false)assigned=null;return r.fulfill({json:{id:'role-1'}})}return r.fulfill({json:roles})}
   if(path.endsWith('/custom-role')){assigned=r.request().postDataJSON().custom_role_id;roles[0].staff_count=assigned?1:0;return r.fulfill({json:{}})}
   if(path.endsWith('/staff'))return r.fulfill({json:[{id:'staff-1',full_name:'Test Worker',phone:'',job_title:'',employment_status:'active',operational_status:'available',has_login:true,custom_role_id:assigned,custom_role_name:assigned?roles[0].name:null}]});
   return r.fulfill({json:[]});
  });
  await page.goto(base+'/roles');await page.getByRole('button',{name:'Duplicate and customise',exact:true}).click();await page.getByLabel('Role name',{exact:true}).fill('Task colleague');assert.equal(await page.getByRole('button',{name:'Tasks: Can view',exact:true}).getAttribute('aria-pressed'),'true');await page.getByRole('button',{name:'Create custom role',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Edit',exact:true}).click();await page.getByLabel('Role name',{exact:true}).fill('Task collaborator');await page.getByRole('button',{name:'Save role',exact:true}).click();await page.getByRole('button',{name:'Save role',exact:true}).last().click();await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(updates,1);
  await page.goto(base+'/staff');await page.getByRole('button',{name:'Edit staff access',exact:true}).click();await page.getByLabel('Custom role (optional)',{exact:true}).selectOption('role-1');await page.getByRole('button',{name:'Save role',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(assigned,'role-1');
  await page.goto(base+'/roles');await page.getByText('1 staff use this role',{exact:false}).waitFor();await page.getByRole('button',{name:'Deactivate',exact:true}).click();await page.getByText('This changes access for 1 people immediately.',{exact:false}).waitFor();await page.getByRole('button',{name:'Deactivate',exact:true}).last().click();await page.getByRole('button',{name:'Reactivate',exact:true}).waitFor();assert.equal(assigned,null);
 }finally{await context.close()}
});


test('Super Admin reviews affected lodges before editing a server-defined plan',async()=>{
 const {context,page}=await accountPage({id:'plan-operator',full_name:'Operator',is_super_admin:true,mfa_enabled:true,memberships:[]});let writes=0;
 const plan={key:'Standard',name:'Standard',description:'Server plan description',features:['fuel'],planned_features:['ai'],revision:4,lodge_count:7,feature_catalog:[{key:'fuel',name:'Fuel records',description:'Vehicle fuel logs',area:'Safari and fleet',available:true},{key:'ai',name:'AI assistant',description:'Future assistant',area:'Reports and AI',available:false}]};
 try{
  await page.route('**/api/v1/platform/plans',r=>r.fulfill({json:[plan]}));
  await page.route('**/api/v1/platform/plans/Standard',r=>{writes++;const body=r.request().postDataJSON();assert.equal(body.expected_revision,4);assert.equal(body.expected_lodge_count,7);assert.deepEqual(body.features,[]);return r.fulfill({json:{...plan,...body,revision:5}})});
  for(const [width,theme] of [[1440,'dark'],[375,'light']]){await page.setViewportSize({width,height:1000});await page.addInitScript(theme=>localStorage.setItem('theme',theme),theme);await page.goto(base+'/super-admin/packages');await page.getByRole('button',{name:'Edit plan: Standard',exact:true}).waitFor();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:`/tmp/safarios-packages-${width}-${theme}.png`,fullPage:true});}
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/super-admin/packages');await page.getByRole('button',{name:'Edit plan: Standard',exact:true}).click();
  const editor=page.getByRole('dialog');await editor.getByText('This changes 7 lodges on this plan. Lodge exceptions still apply.',{exact:true}).waitFor();
  await editor.getByRole('checkbox',{name:'Fuel records',exact:true}).uncheck();assert.equal(await editor.getByRole('checkbox',{name:/AI assistant/}).isDisabled(),true);
  await editor.getByRole('button',{name:'Save plan',exact:true}).click();assert.equal(writes,0);
  const confirmation=page.getByRole('dialog').filter({has:page.getByRole('heading',{name:'Save plan',exact:true})});await confirmation.getByText('This changes 7 lodges on this plan. Lodge exceptions still apply.',{exact:true}).waitFor();
  await confirmation.getByRole('button',{name:'Save plan',exact:true}).click();await page.getByText('Package updated',{exact:true}).waitFor();assert.equal(writes,1);
 }finally{await context.close()}
});

test('AI outage shows a real unavailable state while core navigation works',async()=>{
 const {context,page}=await accountPage({id:'ai-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'ai-lodge',permissions:['ai.use','tasks.view'],entitlements:['ai','tasks']}]});
 try{
  await page.route('**/api/v1/lodges/ai-lodge/ai/status',r=>r.fulfill({json:{state:'unavailable',provider:'vllm',scope:{lodge_id:'ai-lodge',lodge_name:'AI Lodge'},tools:[]}}));
  await page.goto(base+'/lodge-ai');await page.getByRole('heading',{name:'Lodge AI is unavailable',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).count(),0);
  await page.getByRole('button',{name:'Today',exact:true}).click();await page.getByRole('link',{name:'Tasks',exact:true}).click();await page.getByRole('heading',{name:'Tasks',exact:true}).waitFor();
 }finally{await context.close()}
});

test('AI workspace sends a scoped question and displays server provenance',async()=>{
 const {context,page}=await accountPage({id:'ai-reader',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'ai-scope',permissions:['ai.use','tasks.view'],entitlements:['ai','tasks']}]});let sent,rows=[],revoked=false;
 try{
  await page.route('**/api/v1/lodges/ai-scope/ai/**',async r=>{const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/status'))return r.fulfill({json:{state:'ready',provider:'vllm',scope:{lodge_id:'ai-scope',lodge_name:'River Lodge'},tools:[{name:'get_tasks',suggestion:'Which tasks are overdue?'}]}});
   if(p.endsWith('/conversations'))return r.fulfill({json:r.request().method()==='POST'?{id:'conversation-1',created_at:'2026-10-23T08:00:00Z'}:[]});
   if(p.endsWith('/messages')){if(r.request().method()==='POST'){if(revoked)return r.fulfill({status:403,json:{detail:'Your AI access was revoked'}});sent=r.request().postDataJSON();assert.deepEqual(Object.keys(sent).sort(),['content','request_id']);rows=[{id:'m1',role:'user',content:sent.content},{id:'m2',role:'assistant',content:'Test fixture summary of approved tasks.',sources:[{kind:'live',label:'Tasks',lodge_id:'ai-scope',tool:'get_tasks',retrieved_at:'2026-10-23T08:00:00Z'},{kind:'memory',label:'Recorded operational history',lodge_id:'ai-scope',tool:'get_operational_history',partial:true,period:{start_date:'2026-10-01',end_date:'2026-10-23'},references:[{id:'4bd39b56-5b8a-4ac4-ac6c-e317b02fe648',resource_type:'task',resource_id:'task-1',recorded_at:'2026-10-22T08:00:00Z'}],retrieved_at:'2026-10-23T08:00:00Z'},{kind:'document',label:'Approved lodge documents',lodge_id:'ai-scope',tool:'search_lodge_knowledge',references:[{id:'8431a2a9-f9e5-4e26-a1a9-2af1090194f2',document_id:'document-1',title:'Emergency SOP',locator:'Page 1',sha256:'test-fixture-checksum'}],retrieved_at:'2026-10-23T08:00:00Z'}]}];return r.fulfill({json:rows[1]});}return r.fulfill({json:rows});}
   throw Error('Unexpected AI route');
  });
  await page.goto(base+'/lodge-ai');await page.getByRole('button',{name:'Which tasks are overdue?',exact:true}).click();assert.equal(await page.getByLabel('Your question',{exact:true}).inputValue(),'Which tasks are overdue?');
  await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).click();await page.getByText('Test fixture summary of approved tasks.',{exact:true}).waitFor();assert.equal(sent.content,'Which tasks are overdue?');
  await page.getByText('Sources checked',{exact:true}).click();await page.locator('.aiMessage li').getByText(/Tasks/).waitFor();assert.equal(await page.getByText('Record created',{exact:true}).count(),0);await page.getByText(/Recorded event 4bd39b56-5b8a-4ac4-ac6c-e317b02fe648/).waitFor();await page.getByText(/History period:/).waitFor();await page.getByText(/Limited coverage/).waitFor();await page.getByText(/Approved document: Emergency SOP/).waitFor();await page.getByText(/Page 1.*Passage 8431a2a9/).waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(500);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);await page.screenshot({path:`/tmp/safarios-ai-${width}-${theme}.png`,fullPage:true});}
  revoked=true;await page.getByLabel('Your question',{exact:true}).fill('Check again');await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).click();await page.getByRole('alert').filter({hasText:'Your AI access was revoked'}).waitFor();assert.equal(await page.getByText('Test fixture summary of approved tasks.',{exact:true}).count(),0);
 }finally{await context.close()}
});

test('knowledge documents upload privately, process, share and remove with scoped feedback',async()=>{
 const user={id:'knowledge-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'knowledge-lodge',role_key:'lodge_admin',permissions:['ai.use','knowledge.view','knowledge.manage'],entitlements:['ai','ai_knowledge','document_knowledge']}]};
 const {context,page}=await accountPage(user);let docs=[],uploaded=false,removed=false,shared=false,processed=false,denied=false;
 try{
  await page.route('**/api/v1/lodges/knowledge-lodge/ai/**',async r=>{
   const p=new URL(r.request().url()).pathname,m=r.request().method();
   if(p.endsWith('/status'))return r.fulfill({json:{state:'unavailable',tools:[],knowledge_enabled:true}});
   if(p.endsWith('/conversations'))return r.fulfill({json:[]});
   if(p.endsWith('/knowledge')){
    if(m==='POST'){assert.match(r.request().headers()['content-type'],/^multipart\/form-data; boundary=/);assert.equal(r.request().headers()['x-expected-user-id'],'knowledge-owner');const body=r.request().postData();assert.match(body,/procedure\.txt/);assert.match(body,/name="visibility"\r\n\r\nprivate/);uploaded=true;docs=[{id:'doc1',title:'Emergency SOP',file_name:'procedure.txt',visibility:'private',status:'uploaded',can_manage:true,can_retry:true,created_at:'2026-10-23T08:00:00Z'}];return r.fulfill({json:docs[0]});}
    return r.fulfill({json:{items:docs,departments:[{id:'dep1',name:'Operations'}],can_share_lodge:true,processing_available:true,partial:false}});
   }
   if(p.endsWith('/doc1/process')){processed=true;docs[0].status='ready';docs[0].can_retry=false;return r.fulfill({json:{status:'queued'}});}
   if(p.endsWith('/doc1')&&m==='PATCH'){if(denied)return r.fulfill({status:403,json:{detail:'Document access changed'}});assert.deepEqual(r.request().postDataJSON(),{visibility:'lodge',department_id:null});shared=true;docs[0].visibility='lodge';return r.fulfill({json:{status:'updated'}});}
   if(p.endsWith('/doc1')&&m==='DELETE'){removed=true;docs=[];return r.fulfill({json:{status:'removed'}});}
   throw Error('Unexpected knowledge request '+p);
  });
  await page.goto(base+'/lodge-ai');await page.getByRole('heading',{name:'Lodge knowledge',exact:true}).waitFor();await page.getByRole('button',{name:'Upload document',exact:true}).click();
  await page.getByLabel('Document title',{exact:true}).fill('Emergency SOP');await page.getByLabel('Document file',{exact:true}).setInputFiles({name:'procedure.txt',mimeType:'text/plain',buffer:Buffer.from('Check the emergency radio.')});assert.equal(await page.getByLabel('Who can read this?',{exact:true}).inputValue(),'private');
  await page.getByRole('dialog').getByRole('button',{name:'Upload document',exact:true}).click();await page.getByText('Document uploaded',{exact:true}).waitFor();assert.ok(uploaded);await page.getByRole('heading',{name:'Emergency SOP',exact:true}).waitFor();
  await page.getByRole('button',{name:'Process document',exact:true}).click();await page.getByText('Document processing queued',{exact:true}).waitFor();assert.ok(processed);await page.getByRole('button',{name:'Download document',exact:true}).waitFor();
  await page.getByRole('button',{name:'Change sharing',exact:true}).click();await page.getByRole('dialog').getByLabel('Who can read this?',{exact:true}).selectOption('lodge');await page.getByRole('button',{name:'Save sharing',exact:true}).click();await page.getByText('Document sharing updated',{exact:true}).waitFor();assert.ok(shared);
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(500);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`/tmp/safarios-knowledge-${width}-${theme}.png`,fullPage:true});}
  denied=true;await page.getByRole('button',{name:'Change sharing',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Save sharing',exact:true}).click();await page.getByRole('alert').filter({hasText:'Document access changed'}).waitFor();assert.equal(await page.getByRole('dialog').count(),0);assert.equal(await page.getByRole('heading',{name:'Emergency SOP',exact:true}).count(),0);denied=false;await page.getByRole('button',{name:'Refresh documents',exact:true}).click();await page.getByRole('heading',{name:'Emergency SOP',exact:true}).waitFor();
  await page.getByRole('button',{name:'Remove document',exact:true}).click();await page.getByRole('dialog').getByRole('heading',{name:/Remove this document/}).waitFor();await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);assert.equal(removed,false);
  await page.getByRole('button',{name:'Remove document',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Remove document',exact:true}).click();await page.getByText('Document removed',{exact:true}).waitFor();assert.ok(removed);await page.getByText('No documents are visible to your account.',{exact:true}).waitFor();
 }finally{await context.close()}
});

test('Group Owner AI opens explicit group scope, shows property sources and clears revoked answers',async()=>{
 const gid='group-ai-group',anchor='group-ai-anchor',second='group-ai-second';let created=false,revoked=false;
 const user={id:'group-ai-owner',full_name:'Group Owner',is_super_admin:false,mfa_enabled:true,groups:[{id:gid,name:'Safari Collection'}],memberships:[anchor,second].map((id,i)=>({lodge_id:id,lodge_name:i?'River Lodge':'Acacia Lodge',role:'Group Admin',role_key:'group_admin',permissions:['ai.use','ai.group.view','dashboard.view'],entitlements:['ai','advanced_ai','dashboard']}))};
 const groupReply={id:'group-answer',role:'assistant',content:'Test fixture: River Lodge has five overdue tasks; Acacia Lodge has two.',sources:[{kind:'group',label:'Group operational comparison',group_id:gid,group_name:'Safari Collection',partial:true,excluded_count:1,contributors:{overdue_tasks:[anchor,second],open_tasks:[anchor]},retrieved_at:'2026-10-24T08:00:00Z',references:[{lodge_id:anchor,lodge_name:'Acacia Lodge',timezone:'Africa/Johannesburg',current_date:'2026-10-24'},{lodge_id:second,lodge_name:'River Lodge',timezone:'Africa/Johannesburg',current_date:'2026-10-24'}]}]};
 const {context,page}=await accountPage(user);
 try{
  await page.route('**/api/v1/groups/*/overview',r=>r.fulfill({json:{id:gid,name:'Safari Collection',totals:{open_tasks:7},lodges:[{id:anchor,name:'Acacia Lodge',package:'Premium',subscription_status:'Active',metrics:{open_tasks:2},administrators:[]},{id:second,name:'River Lodge',package:'Premium',subscription_status:'Active',metrics:{open_tasks:5},administrators:[]}]}}));
  await page.route(`**/api/v1/lodges/${anchor}/ai/**`,async r=>{
   const url=new URL(r.request().url()),p=url.pathname,m=r.request().method();
   if(p.endsWith('/status')){const isGroup=url.searchParams.get('scope')==='group';return r.fulfill({json:{state:isGroup?'ready':'unavailable',provider:'vllm',scope:isGroup?{type:'group',lodge_id:anchor,group_id:gid,group_name:'Safari Collection',lodges:[{lodge_id:anchor,lodge_name:'Acacia Lodge',timezone:'Africa/Johannesburg'},{lodge_id:second,lodge_name:'River Lodge',timezone:'Africa/Johannesburg'}],excluded_count:1}:{type:'lodge',lodge_id:anchor,lodge_name:'Acacia Lodge'},tools:isGroup?[{name:'get_group_overview',suggestion:'Which of my lodges has the most overdue tasks?'}]:[]}});}
   if(p.endsWith('/conversations')){if(m==='POST'){assert.deepEqual(r.request().postDataJSON(),{scope:'group'});created=true;return r.fulfill({json:{id:'group-conversation',created_at:'2026-10-24T08:00:00Z'}});}assert.equal(url.searchParams.get('scope'),'group');return r.fulfill({json:[]});}
   if(p.endsWith('/messages')&&m==='GET')return r.fulfill({json:[groupReply]});
   if(p.endsWith('/messages')&&m==='POST'){assert.deepEqual(Object.keys(r.request().postDataJSON()).sort(),['content','request_id']);if(revoked)return r.fulfill({status:409,json:{detail:'Group access changed. Start a new conversation'}});return r.fulfill({json:groupReply});}
   throw Error('Unexpected group AI request '+p);
  });
  await page.goto(base+'/group');await page.getByRole('button',{name:'Compare lodges with AI',exact:true}).click();await page.getByRole('heading',{name:'Ask Group Owner AI',exact:true}).waitFor();assert.match(page.url(),/scope=group/);await page.locator('.aiGroupScope > summary').click();await page.getByText('Included lodges: Acacia Lodge, River Lodge',{exact:true}).waitFor();await page.getByText(/1 assigned lodge is excluded/).first().waitFor();await page.locator('.aiGroupScope > summary').click();
  await page.getByRole('button',{name:'Which of my lodges has the most overdue tasks?',exact:true}).click();await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).click();await page.getByText('Test fixture: River Lodge has five overdue tasks; Acacia Lodge has two.',{exact:true}).waitFor();assert.ok(created);await page.getByText('Sources checked',{exact:true}).click();await page.locator('.aiMessage li').getByText(/River Lodge.*Africa\/Johannesburg/).waitFor();await page.getByText('Metric coverage',{exact:true}).click();await page.getByText(/Overdue tasks: Acacia Lodge, River Lodge/i).waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(500);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`/tmp/safarios-group-ai-${width}-${theme}.png`,fullPage:true});}
  revoked=true;await page.getByLabel('Your question',{exact:true}).fill('Compare again');await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).click();await page.getByRole('alert').filter({hasText:/Group access changed/}).waitFor();assert.equal(await page.getByText('Test fixture: River Lodge has five overdue tasks; Acacia Lodge has two.',{exact:true}).count(),0);
 }finally{await context.close()}
});

test('conversational AI shows pending turns, formats answers safely, preserves drafts and supports mobile history',async()=>{
 const {context,page}=await accountPage({id:'chat-user',full_name:'Maya',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'chat-lodge',permissions:['ai.use'],entitlements:['ai']}]});
 let release,submissions=0,sent,rows=[];const gate=new Promise(resolve=>release=resolve),external=[];
 const answer='Here is what needs attention.\n\n### Open tasks\n\n1. **Room readiness check** — due today.\n2. **Vehicle inspection** — awaiting assignment.\n\n| Task | Status |\n| --- | --- |\n| Room check | In progress |\n| Vehicle inspection | Assigned |\n\n[External reference](https://chat-external.invalid/leak)\n\n![Remote image](https://chat-external.invalid/pixel.png)\n\n<script>window.chatInjected=true</script>';
 const history=Array.from({length:6},(_,i)=>({id:'old-'+i,title:i===2?'Vehicle notes':'Previous conversation '+i,created_at:'2026-11-08T10:00:00Z'}));
 try{
  page.on('request',r=>{if(r.url().includes('chat-external.invalid'))external.push(r.url());});
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  await page.route('**/api/v1/lodges/chat-lodge/ai/**',async r=>{
   const p=new URL(r.request().url()).pathname,m=r.request().method();
   if(p.endsWith('/status'))return r.fulfill({json:{state:'ready',knowledge_enabled:true,scope:{type:'lodge',lodge_id:'chat-lodge',lodge_name:'Ndlovu House'},tools:[{name:'get_tasks',suggestion:'What needs attention today?'},{name:'get_room_status',suggestion:'Which rooms are ready?'},{name:'get_current_stays',suggestion:'Who is arriving today?'},{name:'get_maintenance_status',suggestion:'Any maintenance to follow up?'}]}});
   if(p.endsWith('/conversations'))return r.fulfill({json:m==='POST'?{id:'new-chat',title:null,created_at:'2026-11-09T08:00:00Z'}:history});
   if(p.endsWith('/messages')){
    if(m==='POST'){submissions++;sent=r.request().postDataJSON();await gate;rows=[{id:'user-turn',role:'user',content:sent.content},{id:'assistant-turn',role:'assistant',content:answer,sources:[{kind:'live',label:'Tasks',tool:'get_tasks',retrieved_at:'2026-11-09T08:00:00Z'}]}];return r.fulfill({json:rows[1]});}
    return r.fulfill({json:p.includes('/old-2/')?[{id:'old-answer',role:'assistant',content:'Previously checked vehicle notes.',sources:[]}]:rows});
   }
   throw Error('Unexpected chat route '+p);
  });
  await page.goto(base+'/lodge-ai');await page.getByRole('heading',{name:'What can I help you with?',exact:true}).waitFor();
  for(const [width,theme] of [[1440,'dark'],[375,'light']]){await page.setViewportSize({width,height:900});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(200);await page.screenshot({path:`/tmp/safarios-chat-welcome-${width}-${theme}.png`,fullPage:true});}await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  const input=page.getByLabel('Your question',{exact:true});await input.fill('Which tasks');await input.press('Shift+Enter');await input.pressSequentially('need attention?');assert.equal(await input.inputValue(),'Which tasks\nneed attention?');assert.equal(submissions,0);
  const started=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));await input.press('Enter');await started;await page.locator('.aiUserMessage').getByText('Which tasks need attention?',{exact:true}).waitFor();await page.getByRole('status').filter({hasText:'Checking authorised sources'}).waitFor();assert.equal(submissions,1);
  assert.equal(await page.getByRole('heading',{name:'What can I help you with?',exact:true}).count(),0);
  await input.fill('A draft for my next question');await input.press('Enter');assert.equal(submissions,1);
  release();await page.getByRole('heading',{name:'Open tasks',exact:true}).waitFor();assert.equal(await input.inputValue(),'A draft for my next question');
  assert.equal(await page.locator('.aiMarkdown strong').getByText('Room readiness check',{exact:true}).count(),1);
  assert.equal(await page.getByRole('table').getByRole('row').count(),3);
  assert.equal(await page.locator('.aiMarkdown a,.aiMarkdown img,.aiMarkdown script').count(),0);assert.equal(await page.evaluate(()=>window.chatInjected),undefined);assert.deepEqual(external,[]);
  await page.getByRole('button',{name:'Copy response',exact:true}).click();await page.getByRole('button',{name:'Copied',exact:true}).waitFor();assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),answer);
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:900});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(500);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const composer=await page.locator('.aiComposer').boundingBox();assert.ok(composer.y+composer.height<=900-(width<=1023?80:0));const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);await page.screenshot({path:`/tmp/safarios-chat-conversation-${width}-${theme}.png`,fullPage:true});}
  await page.setViewportSize({width:375,height:760});await page.getByRole('button',{name:'Open conversation history',exact:true}).click();await page.getByRole('dialog').getByLabel('Search conversations',{exact:true}).fill('Vehicle');assert.equal(await page.getByRole('dialog').locator('.aiThread').count(),1);
  await page.keyboard.press('Escape');await page.waitForFunction(()=>document.activeElement?.getAttribute('aria-label')==='Open conversation history');
  await page.getByRole('button',{name:'Open conversation history',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:/Vehicle notes/}).click();await page.getByText('Previously checked vehicle notes.',{exact:true}).waitFor();assert.equal(await page.getByRole('dialog').count(),0);
  await page.locator('.aiHeaderNew').click();await page.getByRole('heading',{name:'What can I help you with?',exact:true}).waitFor();assert.equal(await input.inputValue(),'');assert.equal(await page.locator('.aiMessage').count(),0);
 }finally{release();await context.close()}
});

test('conversational AI recovers failed questions and discards late answers after a lodge switch',async()=>{
 const {context,page}=await accountPage({id:'chat-recovery',full_name:'Maya',is_super_admin:false,mfa_enabled:true,groups:[{id:'chat-group',name:'Safari Collection'}],memberships:['recover-lodge','other-lodge'].map((lodge_id,i)=>({lodge_id,lodge_name:i?'Other lodge':'Original lodge',role_key:'group_admin',role:'Group Admin',permissions:['ai.use'],entitlements:['ai']}))});
 let fail=true,release,posted=0;const gate=new Promise(resolve=>release=resolve);
 try{
  await page.route('**/api/v1/lodges/*/ai/**',async r=>{
   const p=new URL(r.request().url()).pathname,m=r.request().method();
   if(p.endsWith('/status'))return r.fulfill({json:{state:'ready',tools:[{name:'get_tasks',suggestion:'Check tasks'}],scope:{type:'lodge',lodge_name:p.includes('other-lodge')?'Other lodge':'Original lodge'}}});
   if(p.endsWith('/conversations'))return r.fulfill({json:m==='POST'?{id:'recover-conversation',created_at:'2026-11-09T08:00:00Z'}:[]});
   if(m==='POST'&&p.endsWith('/messages')){posted++;if(fail)return r.fulfill({status:503,json:{detail:'The AI connection is temporarily unavailable.'}});await gate;return r.fulfill({json:{id:'late',role:'assistant',content:'PRIVATE OLD LODGE ANSWER',sources:[]}})}
   return r.fulfill({json:[]});
  });
  await page.goto(base+'/lodge-ai');const input=page.getByLabel('Your question',{exact:true});await input.fill('Check today’s tasks');await input.press('Enter');
  await page.getByRole('alert').filter({hasText:'Something went wrong. Please try again shortly.'}).waitFor();assert.equal(await input.inputValue(),'Check today’s tasks');assert.equal(await page.locator('.aiUserMessage').count(),0);
  fail=false;const sent=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith('/messages'));await input.press('Enter');await sent;await page.waitForFunction(()=>document.querySelector('.aiThinking'));await input.fill('Private draft');
  await page.evaluate(()=>{localStorage.setItem('active_lodge_id','other-lodge');window.dispatchEvent(new Event('safarios-lodge-changed'))});await page.locator('.aiChatHeading').getByText('Other lodge',{exact:true}).waitFor();assert.equal(await input.inputValue(),'');assert.equal(await page.locator('.aiMessage').count(),0);
  release();await page.waitForTimeout(300);assert.equal(await page.getByText('PRIVATE OLD LODGE ANSWER',{exact:true}).count(),0);assert.equal(await input.inputValue(),'');assert.equal(posted,2);
 }finally{release();await context.close()}
});

test('AI actions require an explicit review and confirmation and cannot submit twice',async()=>{
 const {context,page}=await accountPage({id:'ai-actions-user',full_name:'Maya',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'ai-actions-lodge',permissions:['ai.use','ai.actions'],entitlements:['ai','ai_actions']}]});
 let confirmed=0,reviewed=0,discarded=0,release;const gate=new Promise(resolve=>release=resolve);
 let proposal={id:'action-1',action:'create_task',status:'pending',expires_at:new Date(Date.now()+600000).toISOString(),preview:{fields:[{key:'title',value:'Inspect water pump'},{key:'priority',value:'high'},{key:'proof_required',value:true}]}};
 const message=()=>({id:'action-answer',role:'assistant',content:'Review the proposed change below. Nothing has been changed yet.',sources:[],actions:[proposal]});
 try{
  await page.route('**/api/v1/lodges/ai-actions-lodge/ai/**',async r=>{
   const p=new URL(r.request().url()).pathname,m=r.request().method();
   if(p.endsWith('/status'))return r.fulfill({json:{state:'ready',tools:[{name:'get_tasks',suggestion:'Prepare a task'}]}});
   if(p.endsWith('/conversations'))return r.fulfill({json:m==='POST'?{id:'action-chat',created_at:new Date().toISOString()}:[]});
   if(p.endsWith('/messages'))return r.fulfill({json:m==='POST'?message():[message()]});
   if(p.endsWith('/review')){reviewed++;return r.fulfill({json:{...proposal,token:'opaque-review-token-for-this-proposal-only'}})}
   if(p.endsWith('/confirm')){assert.deepEqual(r.request().postDataJSON(),{token:'opaque-review-token-for-this-proposal-only'});confirmed++;await gate;proposal={...proposal,status:'confirmed',result:{id:'task-made',status:'created'}};return r.fulfill({json:proposal})}
   if(p.endsWith('/cancel')){discarded++;proposal={...proposal,status:'cancelled'};return r.fulfill({json:proposal})}
   throw Error('Unexpected action URL '+p);
  });
  await page.goto(base+'/lodge-ai');await page.getByLabel('Your question',{exact:true}).fill('Prepare a task for the pump');await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).click();await page.getByRole('button',{name:'Review change',exact:true}).waitFor();assert.equal(confirmed,0);
  await page.getByRole('button',{name:'Review change',exact:true}).click();await page.getByRole('dialog').getByText('Inspect water pump',{exact:true}).waitFor();assert.equal(reviewed,1);assert.equal(confirmed,0);
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:900});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(450);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const applyBox=await page.getByRole('dialog').getByRole('button',{name:'Confirm and apply',exact:true}).boundingBox();assert.ok(applyBox&&applyBox.y>=0&&applyBox.y+applyBox.height<=901);const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);await page.screenshot({path:`/tmp/safarios-action-${width}-${theme}.png`,fullPage:true});}
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(confirmed,0);await page.waitForFunction(()=>document.activeElement?.textContent==='Review change');
  await page.getByRole('button',{name:'Review change',exact:true}).click();const apply=page.getByRole('dialog').getByRole('button',{name:'Confirm and apply',exact:true});await apply.click();await page.getByRole('button',{name:'Applying change…',exact:true}).waitFor();assert.equal(confirmed,1);await page.getByRole('button',{name:'Applying change…',exact:true}).dispatchEvent('click');assert.equal(confirmed,1);release();await page.getByText('Task created',{exact:true}).waitFor();await page.getByRole('dialog').waitFor({state:'hidden'});await page.getByText('Change applied',{exact:true}).waitFor();assert.equal(discarded,0);assert.equal(await page.getByRole('button',{name:'Review change',exact:true}).count(),0);
 }finally{release();await context.close()}
});

test('private AI reports schedule, queue, read, download and clear revoked content',async()=>{
 const {context,page}=await accountPage({id:'report-user',full_name:'Maya',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'report-lodge',permissions:['ai.use','ai.reports.manage'],entitlements:['ai','ai_daily_summary','ai_weekly_report','ai_insights']}]});
 let schedules=[],runs=[],saved,queued=0,denied=false;
 const rid='6a6d7b84-8d40-4c0d-93a9-d8a43a798661';
 const detail={id:rid,kind:'daily',scope:'lodge',generated_at:'2026-11-09T04:20:00Z',period:{timezone:'Africa/Johannesburg',local_date:'2026-11-09'},insights_enabled:true,insights:[{key:'overdue_tasks',count:3}],message:{id:'report-answer',role:'assistant',content:'Test fixture: three overdue tasks need review.\n\n### Priorities\n\n- Review overdue work.\n- Check room readiness.',sources:[{kind:'live',label:'Operational overview',tool:'get_dashboard_summary',retrieved_at:'2026-11-09T04:20:00Z'}]}};
 try{
  await page.route('**/api/v1/lodges/report-lodge/ai/**',async r=>{
   const p=new URL(r.request().url()).pathname,m=r.request().method();
   if(p.endsWith('/status'))return r.fulfill({json:{state:'ready',knowledge_enabled:true,report_kinds:['daily','weekly'],scope:{lodge_name:'Ndlovu House'},tools:[{name:'get_tasks',suggestion:'Check tasks'}]}});
   if(p.endsWith('/conversations'))return r.fulfill({json:[]});
   if(p.endsWith('/reports'))return r.fulfill({json:{kinds:['daily','weekly'],timezone:'Africa/Johannesburg',schedules,runs}});
   if(p.endsWith('/schedules')){saved=r.request().postDataJSON();assert.deepEqual(Object.keys(saved).sort(),['enabled','hour','kind','minute','scope','weekday']);schedules=[{id:'schedule-1',...saved,timezone:'Africa/Johannesburg',next_run_at:'2026-11-10T04:15:00Z'}];return r.fulfill({json:schedules[0]})}
   if(p.endsWith('/run')){queued++;runs=[{id:rid,schedule_id:'schedule-1',kind:'daily',status:'queued',scheduled_for:'2026-11-09T04:15:00Z',generated_at:null}];return r.fulfill({json:{id:rid,status:'queued'}})}
   if(p.endsWith('/'+rid))return denied?r.fulfill({status:409,json:{detail:'Your access changed. This saved report is no longer available'}}):r.fulfill({json:detail});
   throw Error('Unexpected report URL '+p);
  });
  await page.goto(base+'/lodge-ai');await page.getByRole('button',{name:'Reports',exact:true}).click();await page.getByText('Choose when your first report should arrive.',{exact:true}).waitFor();await page.getByRole('button',{name:'Add schedule',exact:true}).click();await page.getByRole('dialog').getByLabel('Lodge time',{exact:true}).fill('06:15');await page.getByRole('button',{name:'Save schedule',exact:true}).click();await page.getByText('Report schedule saved',{exact:true}).waitFor();assert.equal(saved.hour,6);assert.equal(saved.minute,15);assert.equal(saved.scope,'lodge');
  await page.getByRole('button',{name:'Generate now',exact:true}).click();await page.getByText('Report queued',{exact:true}).waitFor();await page.getByRole('status').filter({hasText:'Queued'}).waitFor();assert.equal(queued,1);
  runs=[{...runs[0],status:'complete',generated_at:detail.generated_at}];await page.getByRole('button',{name:'Refresh reports',exact:true}).click();await page.getByRole('button',{name:'Open report',exact:true}).click();await page.getByRole('heading',{name:'Priorities',exact:true}).waitFor();await page.getByText('Sources checked',{exact:true}).click();await page.getByText(/Operational overview/).waitFor();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download report',exact:true}).click();assert.match((await download).suggestedFilename(),/^SafariOS-daily-/);
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(450);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),[]);await page.screenshot({path:`/tmp/safarios-report-${width}-${theme}.png`,fullPage:true});}
  denied=true;await page.getByRole('button',{name:'Download report',exact:true}).click();await page.getByRole('alert').filter({hasText:/Your access changed/}).waitFor();assert.equal(await page.getByText('Test fixture: three overdue tasks need review.',{exact:true}).count(),0);
 }finally{await context.close()}
});

test('guest profile occasions and private communication log use guarded forms',async()=>{
 const user={id:'guest-profile-owner',full_name:'Owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'guest-profile-lodge',role_key:'lodge_admin',permissions:['guests.view','guests.manage'],entitlements:['guests']}]};
 const {context,page}=await accountPage(user);let created,updated,logged,logs=[],denied=false;
 try{
  await page.route('**/api/v1/lodges/guest-profile-lodge/guests**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.pathname.endsWith('/communications')){
    if(denied)return route.fulfill({status:403,json:{detail:'Your role does not permit this action'}});
    if(req.method()==='POST'){logged=req.postDataJSON();logs=[{id:'interaction-1',...logged,occurred_at:'2026-11-09T08:00:00Z',created_at:'2026-11-09T08:00:00Z'}];return route.fulfill({json:logs[0]})}
    return route.fulfill({json:{items:logs,has_more:false}});
   }
   if(req.method()==='POST'){created=req.postDataJSON();return route.fulfill({json:{id:'profile-guest',...created}})}
   if(req.method()==='PATCH'){updated=req.postDataJSON();created={...created,...updated};return route.fulfill({json:{id:'profile-guest',...created}})}
   return route.fulfill({json:created?[{id:'profile-guest',...created,name:created.first_name+' '+created.last_name,completed_stays:2}]:[]});
  });
  await page.goto(base+'/guests');await page.getByRole('button',{name:'+ Guest',exact:true}).click();
  await page.getByLabel('First name',{exact:true}).fill('Maya');await page.getByLabel('Last name',{exact:true}).fill('Laurent');
  await page.getByLabel('Birthday',{exact:true}).fill('1985-03-21');await page.getByLabel('Anniversary',{exact:true}).fill('2012-09-18');
  await page.getByLabel('Repeat guest / previous visits',{exact:true}).check();await page.getByLabel('Safari preferences',{exact:true}).fill('Birding at sunrise');
  await page.getByRole('button',{name:'Create guest',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  assert.equal(created.birthday,'1985-03-21');assert.equal(created.anniversary,'2012-09-18');assert.equal(created.repeat_guest,true);assert.equal(created.safari_preferences,'Birding at sunrise');
  await page.getByRole('button',{name:'Maya Laurent',exact:true}).click();
  assert.equal(await page.getByLabel('Birthday',{exact:true}).inputValue(),'1985-03-21');
  await page.getByLabel('Birthday',{exact:true}).fill('');await page.getByRole('button',{name:'Save profile',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(updated.birthday,null);
  await page.getByRole('button',{name:'Maya Laurent',exact:true}).click();await page.getByText('No interactions recorded yet.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Log interaction',exact:true}).click();await page.getByRole('button',{name:'Record interaction',exact:true}).click();
  await page.getByText('This field is required.').first().waitFor();assert.equal(logged,undefined);
  await page.getByLabel('Channel',{exact:true}).selectOption('phone');await page.getByLabel('Direction',{exact:true}).selectOption('inbound');
  await page.getByLabel('Subject',{exact:true}).fill('Arrival confirmation');await page.getByLabel('Interaction notes',{exact:true}).fill('Private arrival confirmation recorded by phone.');
  await page.getByRole('button',{name:'Record interaction',exact:true}).click();await page.getByText('Guest interaction recorded',{exact:true}).waitFor();await page.getByRole('heading',{name:'Arrival confirmation',exact:true}).waitFor();
  await page.evaluate(()=>window.dispatchEvent(new StorageEvent('storage',{key:'theme',newValue:'light'})));await page.getByRole('heading',{name:'Arrival confirmation',exact:true}).waitFor();
  assert.match(logged.client_reference,/^[0-9a-f-]{36}$/);assert.deepEqual(Object.keys(logged).sort(),['channel','client_reference','direction','message','subject']);
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){
   await page.setViewportSize({width,height:1000});await page.evaluate(theme=>{document.documentElement.dataset.theme=theme;localStorage.setItem('theme',theme)},theme);
   await page.waitForTimeout(450);await page.getByRole('heading',{name:'Communication history',exact:true}).scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`guest overflow ${width}/${theme}`);
   const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();assert.deepEqual(axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),[],`guest accessibility ${width}/${theme}`);
   if(width===375||width===1440)await page.screenshot({path:`/tmp/safarios-guest-profile-${width}-${theme}.png`,fullPage:true});
  }
  await page.setViewportSize({width:375,height:1000});await page.waitForTimeout(450);assert.equal(await page.getByRole('dialog').evaluate(el=>getComputedStyle(el,'::after').display),'none');
  denied=true;await page.getByRole('button',{name:'Log interaction',exact:true}).click();await page.getByLabel('Subject',{exact:true}).fill('Do not publish');await page.getByLabel('Interaction notes',{exact:true}).fill('Denied message');await page.getByRole('button',{name:'Record interaction',exact:true}).click();
  await page.getByText('Your role does not permit this action',{exact:true}).first().waitFor();assert.equal(await page.getByText('Private arrival confirmation recorded by phone.',{exact:true}).count(),0);
  await page.evaluate(()=>{localStorage.setItem('active_lodge_id','different-lodge');window.dispatchEvent(new StorageEvent('storage',{key:'active_lodge_id',newValue:'different-lodge'}))});await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(await page.getByRole('button',{name:'Maya Laurent',exact:true}).count(),0);
 }finally{await context.close()}
});

test('task assignment, linked work and lifecycle history use guarded accessible drawers',async()=>{
 const lodge='task-lodge',user={id:'task-manager',full_name:'Task manager',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:lodge,role_key:'lodge_admin',permissions:['tasks.view','tasks.manage','staff.view','departments.view','units.view','guests.view','vehicles.view','maintenance.view'],entitlements:['tasks','staff','departments','units','guests','fleet','maintenance','advanced_tasks']}]};
 const {context,page}=await accountPage(user);let record,created,updated,events=[];
 const after=()=>({...record,assigned_staff_name:record.assigned_staff_id==='staff-2'?'Sipho':'Lerato',vehicle_name:record.vehicle_id?'Cruiser 02':null,maintenance_title:record.maintenance_ticket_id?'Brake inspection':null});
 try{
  await page.route('**/api/v1/lodges/task-lodge/**',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   if(p.endsWith('/tasks')){
    if(req.method()==='POST'){created=req.postDataJSON();record={id:'task-1',...created,assigned_staff_name:'Lerato',department_name:'Operations',status:'assigned',can_transition:true,created_at:'2026-11-09T06:00:00Z',assigned_at:'2026-11-09T06:00:00Z'};events=[{id:'event-1',kind:'created',actor:'Task manager',occurred_at:record.created_at,changed_fields:[],before:null,after:after()}];return route.fulfill({json:{id:record.id,status:record.status}})}
    return route.fulfill({json:record?[record]:[]});
   }
   if(p.endsWith('/tasks/task-1')&&req.method()==='PATCH'){
    assert.equal(req.headers()['x-expected-user-id'],'task-manager');updated=req.postDataJSON();const before=after();record={...record,...updated,assigned_staff_name:updated.assigned_staff_id==='staff-2'?'Sipho':record.assigned_staff_name,assigned_at:'2026-11-09T06:10:00Z'};
    events.push({id:'event-'+(events.length+1),kind:'updated',actor:'Task manager',occurred_at:record.assigned_at,changed_fields:Object.keys(updated).filter(key=>JSON.stringify(before[key])!==JSON.stringify(after()[key])),before,after:after()});return route.fulfill({json:{id:record.id,status:record.status}});
   }
   if(p.endsWith('/history'))return route.fulfill({json:{items:events,has_more:false,timing:{...after(),completion_seconds:null,overdue_seconds:3600}}});
   if(p.endsWith('/staff'))return route.fulfill({json:[{id:'staff-1',full_name:'Lerato',employment_status:'active'},{id:'staff-2',full_name:'Sipho',employment_status:'active'}]});
   if(p.endsWith('/departments'))return route.fulfill({json:[{id:'dep-1',name:'Operations',is_active:true}]});
   if(p.endsWith('/vehicles'))return route.fulfill({json:[{id:'vehicle-1',name:'Cruiser 02',registration:'NDL 202'}]});
   if(p.endsWith('/maintenance'))return route.fulfill({json:[{id:'ticket-1',title:'Brake inspection'}]});
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/tasks');await page.getByRole('button',{name:'+ Task',exact:true}).click();await page.getByLabel('Title',{exact:true}).fill('Inspect Cruiser');await page.getByLabel('Assign staff',{exact:true}).selectOption('staff-1');await page.getByLabel('Department',{exact:true}).selectOption('dep-1');await page.getByLabel('Vehicle',{exact:true}).selectOption('vehicle-1');await page.getByLabel('Maintenance ticket',{exact:true}).selectOption('ticket-1');
  await page.getByRole('button',{name:'Create task',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(created.vehicle_id,'vehicle-1');assert.equal(created.maintenance_ticket_id,'ticket-1');assert.equal(created.priority,'normal');
  await page.getByRole('button',{name:'Inspect Cruiser',exact:true}).click();await page.getByRole('heading',{name:'Task history',exact:true}).waitFor();await page.getByRole('heading',{name:'Lifecycle timing',exact:true}).waitFor();await page.getByText('Cruiser 02',{exact:true}).first().waitFor();
  await page.getByLabel('Assign staff',{exact:true}).selectOption('staff-2');await page.getByRole('button',{name:'Save task details',exact:true}).click();await page.getByText('Assigned to: Lerato → Sipho',{exact:true}).waitFor();assert.equal(updated.assigned_staff_id,'staff-2');
  await page.getByLabel('Vehicle',{exact:true}).selectOption('');await page.getByLabel('Maintenance ticket',{exact:true}).selectOption('');await page.getByRole('button',{name:'Save task details',exact:true}).click();await page.getByText('Task updated',{exact:true}).first().waitFor();assert.equal(updated.vehicle_id,null);assert.equal(updated.maintenance_ticket_id,null);
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){
   await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(450);await page.getByRole('heading',{name:'Task history',exact:true}).scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`task overflow ${width}/${theme}`);
   const issues=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(issues.map(i=>({id:i.id,nodes:i.nodes.map(n=>n.target)})),[],`task accessibility ${width}/${theme}`);
   if(width===375||width===1440)await page.screenshot({path:`/tmp/safarios-task-history-${width}-${theme}.png`,fullPage:true});
  }
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
 }finally{await context.close()}
});

test('task read-only views avoid forbidden lookups and discard late history after a lodge change',async()=>{
 const {context,page}=await accountPage({id:'task-reader',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'task-readonly',permissions:['tasks.view'],entitlements:['tasks','staff','departments','fleet','maintenance','units','guests']}]});const forbidden=[];let release;
 try{
  await page.route('**/api/v1/lodges/task-readonly/**',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(/\/(staff|departments|vehicles|maintenance|rooms|guests)$/.test(p))forbidden.push(p);
   if(p.endsWith('/tasks'))return route.fulfill({json:[{id:'read-task',title:'Read-only task',description:'',status:'assigned',priority:'normal',can_transition:false}]});
   if(p.endsWith('/history')){await new Promise(resolve=>release=resolve);return route.fulfill({json:{items:[{id:'late-history',kind:'created',actor:'Private former context',occurred_at:'2026-11-09T06:00:00Z',changed_fields:[],after:{status:'assigned'}}],has_more:false,timing:{}}})}
   return route.fulfill({json:[]});
  });
  await page.goto(base+'/tasks');await page.getByRole('button',{name:'Read-only task',exact:true}).click();await page.getByText('Loading task history…',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'+ Task',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Save task details',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Accepted',exact:true}).count(),0);assert.deepEqual(forbidden,[]);
  await page.evaluate(()=>{localStorage.setItem('active_lodge_id','other-property');window.dispatchEvent(new StorageEvent('storage',{key:'active_lodge_id',newValue:'other-property'}))});release();await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(await page.getByText('Private former context',{exact:false}).count(),0);
 }finally{release?.();await context.close()}
});

// Presentation fixtures only; no customer data or real service credentials.
function premiumTestAccount(platform=false){
 const sources=fs.readdirSync(path.join(web,'components')).filter(f=>f.endsWith('.tsx')).map(f=>fs.readFileSync(path.join(web,'components',f),'utf8')).join('\n');
 const permissions=[...new Set([...sources.matchAll(/["']([a-z_]+\.[a-z_.]+)["']/g)].map(m=>m[1]))];
 const entitlements=['dashboard','guests','stays','units','guest_requests','guest_feedback','staff','staff_hr','staff_roster','staff_performance','custom_roles','departments','tasks','advanced_tasks','task_attachments','housekeeping','housekeeping_full','maintenance','maintenance_workshop','fb_operations','activities','transfers','ranger','fleet','fuel','wildlife','reports','notifications','ai','advanced_ai','ai_knowledge'];
 return {id:'premium-design-owner',full_name:'Maya Laurent',email:'maya@example.test',is_super_admin:platform,mfa_enabled:true,groups:[],memberships:platform?[]:[{lodge_id:'premium-lodge',lodge_name:'Ndlovu House',role:'Lodge Admin',role_key:'lodge_admin',permissions,entitlements,subscription_status:'Active'}]};
}
async function premiumFixtures(page){
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url()),p=url.pathname;
  if(p.endsWith('/auth/me')||p.endsWith('/platform/plans')||p.endsWith('/role-catalog'))return route.fallback();
  if(p.endsWith('/branding'))return route.fulfill({json:{display_name:'Ndlovu House',logo_url:null}});
  if(p.endsWith('/preferences')&&!p.includes('notification'))return route.fulfill({json:{currency:'ZAR',date_format:'dd/MM/yyyy',timezone:'Africa/Johannesburg'}});
  if(p.endsWith('/dashboard'))return route.fulfill({json:{lodge:{name:'Ndlovu House'},metrics:{guests_in_house:0,arrivals_today:0,open_tasks:0,overdue_tasks:0,maintenance_open:0,activities_today:0,transfers_today:0,vehicles_unavailable:0},attention:[],events:[],subscription:{status:'Active',package:'Premium',expiry_date:'2027-11-09'}}});
  if(p.endsWith('/reports/summary'))return route.fulfill({json:{tasks:{created:0,completed:0,completion_rate:0},maintenance:{created:0,completed:0,critical:0,cost_cents:0},guest_requests:{created:0,resolved:0},fleet:{vehicles:0,fuel_litres:0,fuel_cost_cents:0},stays:{created:0},rooms:{},safari:{activities:0,transfers:0,wildlife_sightings:0}}});
  if(p.endsWith('/ranger/today'))return route.fulfill({json:{staff:{id:'staff-1',name:'Maya Laurent',operational_status:'available'},activities:[],tasks:[]}});
  if(p.endsWith('/ai/status'))return route.fulfill({json:{state:'ready',scope:{lodge_id:'premium-lodge',lodge_name:'Ndlovu House'},tools:[{name:'get_tasks',suggestion:'Which tasks need attention?'}]}});
  if(p.endsWith('/notification-preferences'))return route.fulfill({json:{email_enabled:false,email_min_severity:'normal',email_verified:true,email_configured:false}});
  if(p.endsWith('/unread-count'))return route.fulfill({json:{count:0}});
  if(p.endsWith('/email/status'))return route.fulfill({json:{configured:false,account_deliveries:[]}});
  return route.fulfill({json:[]});
 });
}

test('premium design covers every lodge module and platform screen in both themes',async()=>{
 const modules=['dashboard','guests','stays','rooms','requests','feedback','staff','hr','roles','departments','tasks','housekeeping','maintenance','food-beverage','activities','transfers','ranger','fleet','fuel','wildlife','reports','memory','lodge-ai','notifications','settings'];
 const platform=['','lodges','groups','users','subscriptions','packages','audit','notifications','settings'].map(p=>'/super-admin'+(p?'/'+p:''));
 const audit=[];
 for(const isPlatform of [false,true]){
  const {context,page}=await accountPage(premiumTestAccount(isPlatform));const crashes=[];
  page.on('pageerror',e=>crashes.push(e.message));
  await context.addInitScript(()=>{const theme=new URL(location.href).searchParams.get('visualTheme');if(theme)localStorage.setItem('theme',theme)});
  try{
   await premiumFixtures(page);
   for(const route of isPlatform?platform:modules.map(m=>'/'+m))for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){
    await page.setViewportSize({width,height:1000});await page.goto(base+route+'?visualTheme='+theme);
    await page.locator('.content h1').first().waitFor().catch(async e=>{throw new Error(`${route} ${width}/${theme}: ${e.message}; ${await page.locator('body').innerText()}`)});await page.waitForTimeout(120);
    assert.equal(await page.getByText('Access denied',{exact:true}).count(),0,route+' unexpected access block');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${route} overflow ${width}/${theme}`);
    assert.deepEqual(crashes,[],`${route} crashed ${width}/${theme}`);
    if((width===375&&theme==='light')||(width===1440&&theme==='dark')){
     const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;
     assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],`${route} accessibility ${width}/${theme}`);
    }
    audit.push({route,width,theme});
   }
  }finally{await context.close()}
 }
 fs.writeFileSync('/tmp/safarios-premium-route-matrix.json',JSON.stringify(audit,null,2));
});

test('premium dashboard uses the acacia brand and accurate task health without unknown zero cards',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());
 let restricted=false;
 const brandResponse=await fetch(base+'/branding/safarios-mark.svg');assert.equal(brandResponse.status,200);assert.match(await brandResponse.text(),/<svg/);
 try{
  await premiumFixtures(page);
  const today=new Date().toISOString().slice(0,10);
  await page.route('**/api/v1/lodges/premium-lodge/dashboard',r=>r.fulfill({json:{lodge:{name:'Ndlovu House'},metrics:{guests_in_house:1,arrivals_today:1,open_tasks:restricted?null:5,overdue_tasks:restricted?null:2,maintenance_open:1,activities_today:1,transfers_today:1,vehicles_unavailable:restricted?null:1},attention:[{title:'Room readiness',detail:'One room needs an inspection',priority:'high'}],events:[],subscription:{status:'Active',package:'Premium',expiry_date:'2027-11-09'}}}));
  for(const [key,value] of Object.entries({rooms:[{id:'room-1',name:'Suite 01',status:'ready'}],guests:[{id:'guest-1',name:'Test guest'}],staff:[{id:'staff-1',full_name:'Maya Laurent',has_login:true}],stays:[{id:'stay-1',guest_name:'Test guest',arrival_date:today,departure_date:today,status:'in_house'}],activities:[{id:'drive-1',title:'Morning game drive',starts_at:today+'T06:00:00Z',ends_at:today+'T08:00:00Z',status:'scheduled'}]}))await page.route('**/api/v1/lodges/premium-lodge/'+key,r=>r.fulfill({json:value}));
  await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);
  for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){
   await page.setViewportSize({width,height:1000});await page.goto(base+'/dashboard');await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.getByRole('img',{name:'On track: 60%',exact:true}).waitFor();
   assert.equal(await page.locator('.premiumMetric').count(),4);assert.equal(await page.locator('.safariBrand[aria-label="SafariOS"] svg path').count()>0,true);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   const violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze()).violations;assert.deepEqual(violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],`dashboard ${width}/${theme}`);
   await page.waitForTimeout(600);await page.screenshot({path:`/tmp/safarios-premium-dashboard-${width}-${theme}.png`,fullPage:true});
  }
  restricted=true;await page.goto(base+'/dashboard');await page.getByRole('heading',{name:/Good (morning|afternoon|evening), Maya/}).waitFor();await page.waitForTimeout(150);assert.equal(await page.locator('.premiumMetric').count(),4);assert.equal(await page.locator('.commandMetrics').getByText('Unavailable',{exact:true}).count(),2);assert.equal(await page.getByRole('heading',{name:'Task health',exact:true}).count(),0);
  await page.setViewportSize({width:844,height:390});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'landscape overflow');
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.safariBrand').evaluate(el=>getComputedStyle(el).animationName),'none');
 }finally{await context.close()}
});


test('Super Admin cannot enter lodge workspaces through stale selection or forged membership',async()=>{
 const user={...premiumTestAccount(true),memberships:[{lodge_id:'premium-lodge',lodge_name:'Legacy selection',permissions:['dashboard.view','guests.view'],entitlements:['dashboard','guests']} ]};
 const {context,page,requests}=await accountPage(user);
 await context.addInitScript(()=>{localStorage.setItem('active_user_id','premium-design-owner');localStorage.setItem('active_lodge_id','premium-lodge');localStorage.setItem('active_lodge_name','Legacy selection')});
 try{
  for(const path of ['/dashboard','/guests','/tasks','/rooms','/lodge-ai','/reports','/memory','/hr']){
   await page.goto(base+path);await page.getByRole('heading',{name:'Platform account only',exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>localStorage.getItem('active_lodge_id')),null);
   assert.equal(await page.locator('.sidebar .navItem[href="/guests"]').count(),0);
   assert.equal(requests.filter(url=>/\/api\/v1\/lodges\//.test(url)).length,0,'blocked children must not fetch lodge data');
  }
  await page.getByRole('link',{name:'Return to Super Admin',exact:true}).click();await page.waitForURL('**/super-admin');
  await page.goto(base+'/super-admin/lodges');await page.getByRole('heading',{name:'Lodges',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Open lodge',exact:true}).count(),0);
  await page.goto(base+'/settings');await page.getByRole('heading',{name:'Security settings',exact:true}).waitFor();
  assert.equal(requests.filter(url=>/\/api\/v1\/lodges\//.test(url)).length,0);
 }finally{await context.close()}
});

test('read-only module screens hide write controls and avoid forbidden reference lookups',async()=>{
 const user=premiumTestAccount();user.memberships[0].permissions=['activities.view','transfers.view','fuel.view','vehicles.view','departments.view','wildlife.view','feedback.view','fb.view','ranger.view'];
 const {context,page,requests}=await accountPage(user);
 try{
  await premiumFixtures(page);
  for(const [route,button] of [['activities','+ Activity'],['transfers','+ Transfer'],['fuel','+ Fuel record'],['fleet','+ Vehicle'],['departments','+ Department'],['wildlife','+ Sighting'],['feedback','+ Feedback'],['food-beverage','+ Meal service'],['ranger','Pre-drive checklist']]){
   requests.length=0;const forbidden=[];
   const monitor=request=>{const path=new URL(request.url()).pathname;if(path.startsWith('/api/v1/lodges/')&&/\/(staff|guests|stays|departments|vehicles)$/.test(path)&&!((route==='departments'&&path.endsWith('/departments'))||(route==='fleet'&&path.endsWith('/vehicles'))))forbidden.push(path)};
   page.on('request',monitor);
   await page.goto(base+'/'+route);await page.locator('.content h1').first().waitFor();await page.waitForTimeout(150);
   assert.equal(await page.getByRole('button',{name:button,exact:true}).count(),0,route+' showed unauthorized create action');
   assert.equal(await page.locator('.pageHeader .button.primary').count(),0,route+' exposed a write control');assert.deepEqual(forbidden,[],route+' fetched unauthorized reference data');page.off('request',monitor);
  }
 }finally{await context.close()}
});

test('assigned guide and driver see only server-authorized workflow actions without scheduling controls',async()=>{
 for(const module of ['activities','transfers']){
  const user=premiumTestAccount();user.memberships[0].permissions=[module+'.view',module+'.own.manage'];
  const {context,page}=await accountPage(user);const mutations=[],lookups=[];
  try{
   await premiumFixtures(page);
   const common={status:'scheduled',vehicle_name:'Vehicle 02',can_transition:true};
   const record=module==='activities'?{...common,id:'own',title:'Morning drive',activity_type:'drive',starts_at:'2026-11-09T06:00:00Z',ends_at:'2026-11-09T08:00:00Z',meeting_point:'Reception',guests:[]}:{...common,id:'own',guest_name:'Assigned guest',scheduled_at:'2026-11-09T06:00:00Z',pickup_location:'Airport',dropoff_location:'Lodge'};
   await page.route('**/api/v1/lodges/premium-lodge/'+module+'**',route=>{
    if(route.request().method()==='PATCH'){mutations.push({path:new URL(route.request().url()).pathname,body:route.request().postDataJSON()});return route.fulfill({json:{id:'own',status:'confirmed'}})}
    return route.fulfill({json:[record,{...record,id:'other',can_transition:false}]});
   });
   page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/v1/lodges/')&&/\/(staff|guests|stays|vehicles)$/.test(new URL(r.url()).pathname))lookups.push(r.url())});
   await page.goto(base+'/'+module);await page.locator('.content h1').first().waitFor();
   await page.getByRole('button',{name:'Confirmed',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Confirmed',exact:true}).count(),1);
   assert.equal(await page.getByRole('button',{name:module==='activities'?'+ Activity':'+ Transfer',exact:true}).count(),0);
   await page.getByRole('button',{name:'Confirmed',exact:true}).click();await page.waitForTimeout(150);
   assert.deepEqual(mutations,[{path:'/api/v1/lodges/premium-lodge/'+module+'/own',body:{status:'confirmed'}}]);assert.deepEqual(lookups,[]);
  }finally{await context.close()}
 }
});

test('revoking lookup access closes the editor and discards a late staff response',async()=>{
 const user=premiumTestAccount();user.memberships[0].permissions=['activities.view','activities.manage','staff.view'];
 const {context,page}=await accountPage(user);let release,staffRequests=0;
 try{
  await premiumFixtures(page);
  await page.route('**/api/v1/lodges/premium-lodge/staff',async route=>{staffRequests++;await new Promise(resolve=>release=resolve);return route.fulfill({json:[{id:'old-staff',full_name:'Private staff from previous access',employment_status:'active'}]})});
  await page.goto(base+'/activities');await page.getByRole('button',{name:'+ Activity',exact:true}).click();await page.getByRole('dialog').waitFor();
  await page.waitForFunction(()=>document.querySelector('select[name="guide_staff_id"]'));
  assert.equal(staffRequests,1);
  user.memberships[0].permissions=['activities.view','activities.manage'];await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await page.getByRole('dialog').waitFor({state:'hidden'});await page.getByRole('button',{name:'+ Activity',exact:true}).click();await page.getByRole('dialog').waitFor();
  release();await page.waitForTimeout(200);
  assert.equal(await page.getByText('Private staff from previous access',{exact:true}).count(),0);assert.equal(staffRequests,1);
 }finally{release?.();await context.close()}
});

test('canvas record views search, filter, save and review existing authorized records without writes',async()=>{
 const user=premiumTestAccount();user.memberships[0].permissions=['vehicles.view'];
 const {context,page}=await accountPage(user);const writes=[];
 try{
  await premiumFixtures(page);
  await page.route('**/api/v1/lodges/premium-lodge/vehicles',r=>{if(r.request().method()!=='GET')writes.push(r.request().method());return r.fulfill({json:[{id:'v1',name:'Vehicle 01',registration:'NDL 01',make:'Toyota',model:'Cruiser',odometer_km:1000,status:'ready',notes:''},{id:'v2',name:'Vehicle 02',registration:'NDL 02',make:'Toyota',model:'Cruiser',odometer_km:2000,status:'maintenance',notes:''}]})});
  await page.goto(base+'/fleet');const collection=page.locator('[data-collection="FleetPage"]');await collection.locator('.recordCard').first().waitFor();assert.equal(await collection.locator('.recordCard').count(),2);
  await page.getByRole('searchbox',{name:'Search records',exact:true}).fill('Vehicle 01');assert.equal(await collection.locator('.recordCard').count(),1);
  await page.getByRole('combobox',{name:'Saved views',exact:true}).selectOption('save');
  await page.getByRole('button',{name:'Clear filters',exact:true}).click();assert.equal(await collection.locator('.recordCard').count(),2);
  await page.getByRole('combobox',{name:'Saved views',exact:true}).selectOption('saved');assert.equal(await collection.locator('.recordCard').count(),1);
  await page.getByRole('button',{name:'Clear filters',exact:true}).click();await page.getByRole('combobox',{name:'All statuses',exact:true}).selectOption('ready');assert.equal(await collection.locator('.recordCard').count(),1);
  await collection.getByRole('checkbox').check();await page.getByRole('button',{name:'Review selected',exact:true}).click();await page.getByRole('dialog').waitFor();await page.getByRole('dialog').getByText('Vehicle 01',{exact:true}).waitFor();assert.equal(await page.getByRole('dialog').getByRole('combobox',{name:'Status',exact:true}).count(),0);
  await page.getByRole('button',{name:'Close details',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'Board',exact:true}).click();assert.equal(await collection.locator('.recordCard').count(),1);await page.getByRole('button',{name:'List',exact:true}).click();assert.equal(await collection.locator('tbody tr').count(),1);assert.deepEqual(writes,[]);
 }finally{await context.close()}
});

test('canvas navigation persists collapsed groups and keeps the active group open',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());
 try{
  await premiumFixtures(page);await page.goto(base+'/fleet');await page.getByRole('heading',{name:'Fleet',exact:true}).waitFor();
  const guests=page.getByRole('button',{name:'Guests',exact:true}),safari=page.getByRole('button',{name:'Safari & Fleet',exact:true});
  assert.equal(await guests.getAttribute('aria-expanded'),'false');assert.equal(await safari.getAttribute('aria-expanded'),'true');
  await guests.click();await page.reload();await page.getByRole('heading',{name:'Fleet',exact:true}).waitFor();assert.equal(await guests.getAttribute('aria-expanded'),'true');
  await safari.click();assert.equal(await safari.getAttribute('aria-expanded'),'true');
  await page.getByRole('button',{name:'Collapse sidebar',exact:true}).click();await page.getByRole('button',{name:'Expand sidebar',exact:true}).click();assert.equal(await safari.getAttribute('aria-expanded'),'true');
 }finally{await context.close()}
});

test('canvas MFA visual digit cells preserve the existing OTP submission contract',async()=>{
 const {context,page}=await accountPage({id:'otp-canvas',full_name:'User',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'otp-lodge',permissions:['tasks.view'],entitlements:['tasks']}]});let sent;
 try{
  await page.route('**/api/v1/auth/login',r=>{sent=r.request().postDataJSON();return sent.otp?r.fulfill({json:{ok:true}}):r.fulfill({status:401,json:{detail:'MFA_REQUIRED'}})});
  await page.goto(base+'/login');await page.getByLabel('Email',{exact:true}).fill('owner@example.com');await page.getByLabel('Password',{exact:true}).fill('Secure-test-passphrase');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByLabel('Authenticator code',{exact:true}).fill('123456');assert.equal(await page.locator('.codeInputBoxes span').count(),6);assert.deepEqual(await page.locator('.codeInputBoxes span').allTextContents(),['1','2','3','4','5','6']);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('**/tasks');assert.equal(sent.otp,'123456');assert.equal(sent.recovery_code,undefined);
 }finally{await context.close()}
});

test('canvas task calendar opens the existing protected task detail without write controls',async()=>{
 const user=premiumTestAccount();user.memberships[0].permissions=['tasks.view'];
 const {context,page}=await accountPage(user);const writes=[];
 try{
  await premiumFixtures(page);const due=new Date();due.setHours(12,0,0,0);
  await page.route('**/api/v1/lodges/premium-lodge/tasks**',r=>{const p=new URL(r.request().url()).pathname;if(r.request().method()!=='GET')writes.push(r.request().method());if(p.endsWith('/tasks'))return r.fulfill({json:[{id:'calendar-task',title:'Inspect Unit 4',description:'Room inspection',status:'assigned',priority:'high',due_at:due.toISOString(),can_transition:false}]});if(p.endsWith('/history'))return r.fulfill({json:{items:[],has_more:false,timing:{}}});return r.fulfill({json:[]})});
  await page.goto(base+'/tasks');await page.getByRole('button',{name:'Calendar',exact:true}).click();await page.locator('.calendarAgenda').getByRole('button',{name:'Inspect Unit 4',exact:true}).click();await page.getByRole('dialog').waitFor();await page.getByRole('dialog').getByRole('heading',{name:'Inspect Unit 4',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Save task details',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'+ Task',exact:true}).count(),0);assert.deepEqual(writes,[]);
 }finally{await context.close()}
});

test('canvas wildlife shows real scoped pending records while offline without issuing a write',async()=>{
 const user=premiumTestAccount();user.memberships[0].permissions=['wildlife.view','wildlife.manage'];user.memberships[0].entitlements.push('offline_mobile');
 const {context,page}=await accountPage(user);const writes=[];
 try{
  await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/wildlife',r=>{if(r.request().method()!=='GET')writes.push(r.request().method());return r.fulfill({json:[]})});
  await page.goto(base+'/wildlife');await page.getByRole('heading',{name:'Wildlife sightings',exact:true}).waitFor();await context.setOffline(true);
  await page.getByRole('button',{name:'+ Sighting',exact:true}).click();await page.getByLabel('Species',{exact:true}).fill('Elephant');await page.getByLabel('Observed at',{exact:true}).fill('2026-11-10T09:00');await page.getByRole('button',{name:'Save offline',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  await page.locator('.queuedRecord').getByRole('heading',{name:'Elephant',exact:true}).waitFor();assert.equal(await page.locator('.queuedRecord').getByText('Waiting to sync',{exact:true}).count(),1);assert.deepEqual(writes,[]);
 }finally{await context.setOffline(false);await context.close()}
});

test('instant cache deduplicates scoped reads, clones results, retries failures and rejects overtaken snapshots',async()=>{
 const output={};const js=ts.transpileModule(fs.readFileSync(path.join(web,'lib/data-cache.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;new Function('exports',js)(output);
 let calls=0,release;const first=()=>{calls++;return new Promise(r=>release=r)};
 const a=output.cachedRead('user-a:lodge-a:tasks',first),b=output.cachedRead('user-a:lodge-a:tasks',first);release([{id:'one'}]);
 const [one,two]=await Promise.all([a,b]);assert.equal(calls,1);one[0].id='changed';assert.equal(two[0].id,'one');
 assert.deepEqual(await output.cachedRead('user-b:lodge-a:tasks',async()=>[{id:'private-b'}]),[{id:'private-b'}]);
 output.invalidateData();let attempts=0;
 await assert.rejects(output.cachedRead('failure',async()=>{attempts++;throw Error('unavailable')}));
 assert.equal(await output.cachedRead('failure',async()=>{attempts++;return 'recovered'}),'recovered');assert.equal(attempts,2);
 let finish,reads=0;const old=output.cachedRead('late',()=>{reads++;return reads===1?new Promise(r=>finish=r):Promise.resolve('fresh')});
 output.invalidateData();finish('stale');assert.equal(await old,'fresh');assert.equal(reads,2);
});

test('instant task status rolls back, prevents duplicate submits and retries with the original scoped endpoint',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let status='assigned',calls=0,release,reject=true;
 try{
  await premiumFixtures(page);
  await page.route('**/api/v1/lodges/premium-lodge/tasks**',async r=>{
   const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/tasks'))return r.fulfill({json:[{id:'instant-task',title:'Inspect water pump',description:'',status,priority:'normal',can_transition:true}]});
   if(p.endsWith('/instant-task')&&r.request().method()==='PATCH'){calls++;assert.equal(r.request().headers()['x-expected-user-id'],'premium-design-owner');const body=r.request().postDataJSON();await new Promise(resolve=>release=resolve);if(reject)return r.fulfill({status:500,json:{detail:'internal'}});status=body.status;return r.fulfill({json:{id:'instant-task',status}})}
   return r.fulfill({json:[]});
  });
  await page.goto(base+'/tasks');await page.getByRole('button',{name:'Accepted',exact:true}).click();
  await page.getByText('Saving…',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Started',exact:true}).isDisabled(),true);assert.equal(calls,1);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));assert.equal(calls,1);release();
  await page.getByRole('button',{name:'Accepted',exact:true}).waitFor();await page.getByRole('button',{name:'Retry',exact:true}).click();await page.getByText('Saving…',{exact:true}).waitFor();assert.equal(calls,2);reject=false;release();
  await page.getByText('Task updated',{exact:true}).waitFor();await page.getByRole('button',{name:'Started',exact:true}).waitFor();assert.equal(status,'accepted');assert.equal(await page.getByRole('button',{name:'Undo',exact:true}).count(),0);
 }finally{release?.();await context.close()}
});

test('instant maintenance supports a real reverse transition with Undo and preserves records during focus refresh',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let status='in_progress',writes=[],release,hold=false;
 try{
  await premiumFixtures(page);
  await page.route('**/api/v1/lodges/premium-lodge/maintenance**',async r=>{
   const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/maintenance')){if(hold)await new Promise(resolve=>release=resolve);return r.fulfill({json:[{id:'instant-maint',title:'Repair gate',status,priority:'normal',category:'general'}]})}
   if(p.endsWith('/instant-maint')){status=r.request().postDataJSON().status;writes.push(status);return r.fulfill({json:{id:'instant-maint',status}})}
   return r.fulfill({json:[]});
  });
  await page.goto(base+'/maintenance');await page.getByRole('button',{name:'Waiting',exact:true}).click();await page.getByRole('button',{name:'Undo',exact:true}).click();await page.getByText('Change undone',{exact:true}).waitFor();assert.deepEqual(writes,['waiting','in_progress']);
  hold=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await page.waitForFunction(()=>document.querySelector('h1')?.textContent==='Maintenance');assert.equal(await page.getByText('Repair gate',{exact:true}).isVisible(),true);hold=false;release?.();
 }finally{release?.();await context.close()}
});

test('instant notification read updates its badge immediately and rolls back on rejection',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let read=false,release;
 try{
  await premiumFixtures(page);await page.route('**/api/v1/auth/notifications**',async r=>{
   const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/summary'))return r.fulfill({json:{unread:read?0:1}});
   if(p.endsWith('/read')){await new Promise(resolve=>release=resolve);return r.fulfill({status:500,json:{detail:'internal'}})}
   return r.fulfill({json:[{id:'instant-notice',title:'Task assigned to you',body:'Review your assigned work.',severity:'normal',created_at:'2026-11-10T06:00:00Z',read_at:read?'2026-11-10T07:00:00Z':null}]});
  });
  await page.goto(base+'/notifications');await page.getByRole('link',{name:'Notifications, 1 unread',exact:true}).waitFor();await page.getByRole('button',{name:'Mark read',exact:true}).click();await page.getByRole('button',{name:'Saving…',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Saving…',exact:true}).isDisabled(),true);await page.getByRole('link',{name:'Notifications',exact:true}).first().waitFor();await page.evaluate(()=>window.dispatchEvent(new Event('safarios-data-refresh')));await page.waitForTimeout(100);assert.equal(await page.getByRole('link',{name:'Notifications, 1 unread',exact:true}).count(),0);release();
  await page.getByRole('button',{name:'Mark read',exact:true}).waitFor();await page.getByRole('link',{name:'Notifications, 1 unread',exact:true}).waitFor();await page.getByRole('button',{name:'Retry',exact:true}).waitFor();
 }finally{release?.();await context.close()}
});

test('instant request reassignment uses the existing endpoint and offers Undo only for an existing assignee',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let assigned='staff-a';const writes=[];
 try{
  await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/staff',r=>r.fulfill({json:[{id:'staff-a',full_name:'Alex',employment_status:'active'},{id:'staff-b',full_name:'Bea',employment_status:'active'}]}));
  await page.route('**/api/v1/lodges/premium-lodge/requests**',async r=>{
   if(r.request().method()==='PATCH'){const body=r.request().postDataJSON();assert.deepEqual(Object.keys(body),['assigned_staff_id']);assigned=body.assigned_staff_id;writes.push(assigned);return r.fulfill({json:{id:'request-assign',status:'assigned'}})}
   return r.fulfill({json:[{id:'request-assign',guest_name:'Fixture guest',description:'Extra towels',request_type:'housekeeping',priority:'normal',status:'assigned',assigned_staff_id:assigned,assigned_staff_name:assigned==='staff-a'?'Alex':'Bea',resolution:''}]});
  });
  await page.goto(base+'/requests');await page.getByLabel('Assign request Extra towels',{exact:true}).selectOption('staff-b');await page.getByRole('button',{name:'Undo',exact:true}).click();await page.getByText('Change undone',{exact:true}).waitFor();assert.deepEqual(writes,['staff-b','staff-a']);
 }finally{await context.close()}
});

test('instant room and housekeeping changes retain pending controls and roll back rejected writes',async()=>{
 for(const module of ['rooms','housekeeping']){
  const {context,page}=await accountPage(premiumTestAccount());let release,writes=0;
  try{
   await premiumFixtures(page);const endpoint=module==='rooms'?'rooms':'housekeeping-jobs';
   await page.route(`**/api/v1/lodges/premium-lodge/${endpoint}**`,async r=>{
    if(r.request().method()==='PATCH'){writes++;await new Promise(resolve=>release=resolve);return r.fulfill({status:500,json:{detail:'internal'}})}
    return r.fulfill({json:module==='rooms'?[{id:'room-instant',name:'Marula',unit_type:'Suite',status:'available',notes:''}]:[{id:'hk-instant',unit_id:'room-instant',unit_name:'Marula',job_type:'cleaning',status:'assigned',notes:''}]});
   });
   await page.goto(base+'/'+module);
   if(module==='rooms')await page.getByRole('combobox',{name:/^Move to…/}).selectOption('cleaning');else await page.getByRole('button',{name:'Accepted',exact:true}).click();
   await page.getByText('Saving…',{exact:true}).waitFor();assert.equal(writes,1);
   if(module==='rooms')assert.equal(await page.getByRole('combobox',{name:/^Move to…/}).isDisabled(),true);else assert.equal(await page.getByRole('button',{name:'In progress',exact:true}).isDisabled(),true);
   release();await page.getByRole('button',{name:'Retry',exact:true}).waitFor();
   if(module==='rooms')assert.equal(await page.locator('.roomCard .statusPill').innerText(),'Available');else await page.getByRole('button',{name:'Accepted',exact:true}).waitFor();
  }finally{release?.();await context.close()}
 }
});

test('instant AI dismissal rolls back on rejection and retry never confirms an action',async()=>{
 const {context,page}=await accountPage({id:'instant-ai-owner',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'instant-ai-lodge',permissions:['ai.use','ai.actions'],entitlements:['ai','ai_actions']}]});let release,fail=true,cancels=0,confirms=0;
 const proposal={id:'instant-action',action:'create_task',status:'pending',expires_at:new Date(Date.now()+600000).toISOString(),preview:{fields:[{key:'title',value:'Check radio'}]}};
 try{
  await page.route('**/api/v1/lodges/instant-ai-lodge/ai/**',async r=>{
   const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/status'))return r.fulfill({json:{state:'ready',tools:[{name:'get_tasks',suggestion:'Prepare a task'}]}});
   if(p.endsWith('/conversations'))return r.fulfill({json:r.request().method()==='POST'?{id:'instant-chat'}:[]});
   if(p.endsWith('/messages')){const msg={id:'instant-reply',role:'assistant',content:'Review this proposal.',sources:[],actions:[proposal]};return r.fulfill({json:r.request().method()==='POST'?msg:[msg]})}
   if(p.endsWith('/cancel')){cancels++;await new Promise(resolve=>release=resolve);return fail?r.fulfill({status:500,json:{detail:'internal'}}):r.fulfill({json:{...proposal,status:'cancelled'}})}
   if(p.endsWith('/confirm')){confirms++;throw Error('Dismissal must never confirm')}
   return r.fulfill({json:[]});
  });
  await page.goto(base+'/lodge-ai');await page.getByLabel('Your question',{exact:true}).fill('Prepare a task');await page.getByRole('button',{name:'Ask Lodge AI',exact:true}).click();await page.getByRole('button',{name:'Discard proposal',exact:true}).click();await page.getByRole('button',{name:'Dismissing…',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Dismissing…',exact:true}).isDisabled(),true);release();await page.getByRole('button',{name:'Discard proposal',exact:true}).waitFor();await page.getByRole('button',{name:'Retry',exact:true}).click();await page.getByRole('button',{name:'Dismissing…',exact:true}).waitFor();fail=false;release();await page.locator('.aiActionState').getByText('Proposal discarded',{exact:true}).waitFor();assert.equal(cancels,2);assert.equal(confirms,0);
 }finally{release?.();await context.close()}
});

test('instant API cache clears on logout and lodge selection and never caches auth checks',async()=>{
 const vm=require('node:vm');const cache={};new Function('exports',ts.transpileModule(fs.readFileSync(path.join(web,'lib/data-cache.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(cache);
 const storage=new Map([['active_user_id','cache-owner'],['active_lodge_id','cache-lodge']]);const calls=[];const api={};
 const sandbox={exports:api,process:{env:{}},Headers,FormData,structuredClone,window:{dispatchEvent:()=>{}},document:{cookie:''},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},fetch:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>url.endsWith('/auth/me')?{id:'cache-owner',memberships:[{lodge_id:storage.get('active_lodge_id')}]}:url.endsWith('/rooms')?[{id:'private-room'}]:{}}},require:name=>name.includes('data-cache')?cache:name.includes('form-submission')?{originatingForm:()=>null}:name.includes('action-feedback')?{actionFeedback:()=>{}}:name.includes('formatting')?{storeFormatting:()=>{}}:name==='sonner'?{toast:{error:()=>{}}}:{formCopy:{}}};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(web,'lib/api.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,sandbox);
 await api.authApi.me();await api.authApi.me();assert.equal(calls.filter(c=>c.url.endsWith('/auth/me')).length,2);
 await api.lodgeApi.rooms();await api.lodgeApi.rooms();assert.equal(calls.filter(c=>c.url.endsWith('/rooms')).length,1);
 await api.authApi.logout();assert.equal(storage.has('active_user_id'),false);storage.set('active_user_id','cache-owner');storage.set('active_lodge_id','cache-lodge');await api.lodgeApi.rooms();assert.equal(calls.filter(c=>c.url.endsWith('/rooms')).length,2);
 api.setActiveLodgeId('other-lodge');await api.lodgeApi.rooms();assert.equal(calls.at(-1).url,'/api/v1/lodges/other-lodge/rooms');assert.equal(calls.at(-1).options.headers.get('X-Expected-User-Id'),'cache-owner');
});

test('instant late mutation rejection cannot restore data or show an old error after a lodge switch',async()=>{
 const user=premiumTestAccount();user.groups=[{id:'instant-group',name:'Assigned group'}];user.memberships.push({...user.memberships[0],lodge_id:'second-instant-lodge',lodge_name:'Second lodge'});
 const {context,page}=await accountPage(user);let release;
 try{
  await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/tasks**',async r=>{
   if(r.request().method()==='PATCH'){await new Promise(resolve=>release=resolve);return r.fulfill({status:500,json:{detail:'Former property private failure'}})}
   return r.fulfill({json:[{id:'late-instant',title:'Former property work',status:'assigned',priority:'normal',description:'',can_transition:true}]});
  });
  await page.goto(base+'/tasks');await page.getByRole('button',{name:'Accepted',exact:true}).click();await page.getByText('Saving…',{exact:true}).waitFor();
  await page.evaluate(()=>{localStorage.setItem('active_lodge_id','second-instant-lodge');window.dispatchEvent(new Event('safarios-lodge-changed'))});await page.getByRole('heading',{name:'Tasks',exact:true}).waitFor();release();await page.waitForTimeout(200);
  assert.equal(await page.getByText('Former property work',{exact:true}).count(),0);assert.equal(await page.getByText('Former property private failure',{exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Retry',exact:true}).count(),0);
 }finally{release?.();await context.close()}
});

test('instant stale controls do not submit under a newly selected lodge before navigation catches up',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let writes=0;
 try{
  await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/housekeeping-jobs**',async r=>{
   if(r.request().method()==='PATCH'){writes++;return r.fulfill({json:{id:'stale-hk',status:'accepted'}})}
   return r.fulfill({json:[{id:'stale-hk',unit_id:'room-a',unit_name:'Marula',job_type:'cleaning',status:'assigned',notes:''}]});
  });
  await page.goto(base+'/housekeeping');await page.getByRole('button',{name:'Accepted',exact:true}).waitFor();await page.evaluate(()=>localStorage.setItem('active_lodge_id','new-lodge-before-navigation'));await page.getByRole('button',{name:'Accepted',exact:true}).click();assert.equal(writes,0);assert.equal(await page.getByText('Saving…',{exact:true}).count(),0);
 }finally{await context.close()}
});

test('instant focus refresh waits for a creation drawer to close and preserves typed values',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let name='Marula',reads=0;
 try{
  await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/rooms',r=>{reads++;return r.fulfill({json:[{id:'refresh-room',name,unit_type:'Suite',status:'available',notes:''}]})});
  await page.goto(base+'/rooms');await page.getByText('Marula',{exact:true}).waitFor();await page.getByRole('button',{name:'+ Room / Unit',exact:true}).click();const input=page.getByRole('dialog').getByLabel('Name',{exact:true});await input.fill('Draft room name');const before=reads;name='Updated on server';await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await page.waitForTimeout(100);assert.equal(await input.inputValue(),'Draft room name');assert.equal(reads,before);await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});await page.getByText('Updated on server',{exact:true}).waitFor();assert.ok(reads>before);
 }finally{await context.close()}
});

test('instant notification badge resumes refresh when navigating away during a pending read',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let release;
 try{
  await premiumFixtures(page);await page.route('**/api/v1/auth/notifications**',async r=>{
   const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/summary'))return r.fulfill({json:{unread:1}});
   if(p.endsWith('/read')){await new Promise(resolve=>release=resolve);return r.fulfill({status:500,json:{detail:'internal'}})}
   return r.fulfill({json:[{id:'away-notice',title:'Review assigned work',body:'A private notification.',severity:'normal',created_at:'2026-11-10T06:00:00Z',read_at:null}]});
  });
  await page.goto(base+'/notifications');await page.getByRole('link',{name:'Notifications, 1 unread',exact:true}).waitFor();await page.getByRole('button',{name:'Mark read',exact:true}).click();await page.getByRole('button',{name:'Saving…',exact:true}).waitFor();await page.getByRole('link',{name:'Tasks',exact:true}).click();await page.getByRole('heading',{name:'Tasks',exact:true}).waitFor();release();await page.getByRole('link',{name:'Notifications, 1 unread',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Retry',exact:true}).count(),0);
 }finally{release?.();await context.close()}
});

async function statusBoardFixture(module,{initial,deny=false,readOnly=false,expired=false}={}){
 const user=premiumTestAccount();if(readOnly)user.memberships[0].permissions=['tasks.view','requests.view','maintenance.view','housekeeping.view','units.view'];if(expired)user.memberships[0].subscription_status='Expired';
 const {context,page}=await accountPage(user);await page.setViewportSize({width:1440,height:1000});await premiumFixtures(page);
 const endpoint=module==='housekeeping'?'housekeeping-jobs':module;
 const row={id:'board-record',title:'Board work',name:'Marula',guest_name:'Board guest',description:'Check lodge supplies',status:initial||({tasks:'assigned',requests:'in_progress',maintenance:'in_progress',housekeeping:'assigned',rooms:'available'})[module],priority:'normal',request_type:'general',category:'general',unit_type:'Suite',unit_name:'Marula',job_type:'cleaning',assigned_staff_id:'staff-a',assigned_staff_name:'Alex',can_transition:true,notes:'',resolution:'',inspector_staff_id:null};
 const state={row,writes:[],deny};
 await page.route(`**/api/v1/lodges/premium-lodge/${endpoint}**`,async r=>{
  const p=new URL(r.request().url()).pathname;
  if(p.endsWith('/'+endpoint)&&r.request().method()==='GET')return r.fulfill({json:[state.row]});
  if(p.endsWith('/board-record')&&r.request().method()==='PATCH'){
   const body=r.request().postDataJSON();state.writes.push(body);assert.equal(r.request().headers()['x-expected-user-id'],'premium-design-owner');
   if(state.deny)return r.fulfill({status:409,json:{detail:'The record changed. Review its current status.'}});
   state.row={...state.row,...body};return r.fulfill({json:{id:'board-record',status:state.row.status}});
  }
  return r.fallback();
 });
 await page.goto(base+'/'+module);await page.getByRole('heading',{name:({tasks:'Tasks',requests:'Guest Requests',maintenance:'Maintenance',housekeeping:'Housekeeping workflow',rooms:'Rooms & Units'})[module],exact:true}).waitFor();
 if(module==='tasks')await page.getByRole('button',{name:'Board',exact:true}).click();
 await page.locator('.statusBoardItem').first().waitFor();
 return {context,page,state};
}
async function dragStatusCard(page,target,expected){
 const handle=page.locator('.statusDragHandle').first();await handle.scrollIntoViewIfNeeded();const from=await handle.boundingBox(),to=await page.locator(`.statusColumn[data-status="${target}"]`).boundingBox();assert.ok(from&&to);
 await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();await page.mouse.move(from.x+from.width/2+12,from.y+from.height/2,{steps:3});await page.locator('[data-dragging]').waitFor();await page.mouse.move(to.x+to.width/2,to.y+65,{steps:15});await page.locator(`.statusColumn[data-status="${target}"][data-over]`).waitFor();if(expected)assert.equal(await page.locator(`.statusColumn[data-status="${target}"]`).getAttribute('data-drop-state'),expected);await page.mouse.up();
}

test('status board keyboard Space arrows Space updates a task through its guarded endpoint',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks');
 try{
  const handle=page.getByRole('button',{name:'Move Board work',exact:true});await handle.focus();await page.keyboard.press('Space');await page.locator('[data-dragging]').waitFor();await page.locator('.statusColumn[data-status="assigned"][data-over]').waitFor();await page.keyboard.press('ArrowRight');await page.locator('.statusColumn[data-status="accepted"][data-over]').waitFor();await page.keyboard.press('Space');await page.getByText('Board work moved to Accepted.',{exact:true}).waitFor();assert.deepEqual(state.writes,[{status:'accepted'}]);assert.equal(await page.locator('.statusColumn[data-status="accepted"] .statusBoardItem').count(),1);await page.waitForFunction(()=>document.activeElement?.classList.contains('statusBoardItem'));
 }finally{await context.close()}
});

test('status board pointer drop refuses illegal columns and rolls back a server-rejected valid transition',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks',{deny:true});
 try{
  await dragStatusCard(page,'created','refused');await page.getByText('Cannot move to Created.',{exact:true}).waitFor();assert.deepEqual(state.writes,[]);
  await dragStatusCard(page,'accepted','allowed');await page.getByText('Board work was not moved. Review the message and try a permitted action.',{exact:true}).waitFor();assert.deepEqual(state.writes,[{status:'accepted'}]);assert.equal(await page.locator('.statusColumn[data-status="assigned"] .statusBoardItem').count(),1);assert.equal(await page.locator('.statusColumn[data-status="accepted"] .statusBoardItem').count(),0);
  state.deny=false;await dragStatusCard(page,'accepted','allowed');await page.getByText('Board work moved to Accepted.',{exact:true}).waitFor();assert.equal(state.row.status,'accepted');
 }finally{await page.mouse.up();await context.close()}
});

test('status board Move to works on phone widths in all workflows and required resolution notes are retained',async()=>{
 for(const [module,target] of [['requests','resolved'],['maintenance','completed'],['housekeeping','accepted'],['rooms','cleaning']]){
  const {context,page,state}=await statusBoardFixture(module);
  try{
   await page.setViewportSize({width:375,height:1000});
   if(['requests','maintenance'].includes(module))page.once('dialog',dialog=>dialog.accept('Verified work and recorded resolution.'));
   const response=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().endsWith('/board-record'));await page.getByRole('combobox',{name:/^Move to…/}).selectOption(target);await response;await page.getByRole('status').filter({hasText:/ moved to /}).waitFor();
   assert.equal(state.writes.length,1,module);assert.equal(state.writes[0].status,target,module);if(['requests','maintenance'].includes(module))assert.equal(state.writes[0].resolution,'Verified work and recorded resolution.');await page.locator(`.statusColumn[data-status="${target}"] .statusBoardItem`).waitFor();await page.waitForFunction(()=>{const node=document.querySelector('.statusBoardItem'),rect=node?.getBoundingClientRect();return rect&&rect.left>=0&&rect.right<=innerWidth+1});
   await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);
   for(const width of [375,768,1366,1440])for(const theme of ['dark','light']){await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.waitForTimeout(450);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${module} ${width}/${theme}`);if((width===375&&theme==='light')||(width===1440&&theme==='dark')){const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();assert.deepEqual(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),[],`${module} ${width}/${theme}`);if(module==='rooms'&&width===375)await page.screenshot({path:'/tmp/safarios-status-board-mobile-light.png',fullPage:true});if(module==='maintenance'&&width===1440)await page.screenshot({path:'/tmp/safarios-status-board-desktop-dark.png',fullPage:true});}}

   await page.waitForFunction(()=>document.querySelectorAll('[data-sonner-toast]').length===0);const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();assert.deepEqual(audit.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),[],module);
   await page.screenshot({path:`/tmp/safarios-status-board-${module}.png`,fullPage:true});
  }finally{await context.close()}
 }
});

test('status board persists collapse and view without storing records and read-only or expired users cannot move',async()=>{
 const {context,page}=await statusBoardFixture('rooms');
 try{
  await page.getByRole('button',{name:'Collapse Available',exact:true}).click();await page.reload();await page.getByRole('button',{name:'Expand Available',exact:true}).waitFor();await page.getByRole('button',{name:'Expand Available',exact:true}).click();await page.getByRole('button',{name:'Cards',exact:true}).click();await page.reload();await page.getByRole('button',{name:'Cards',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Cards',exact:true}).getAttribute('aria-pressed'),'true');const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('safarios-board:premium-design-owner:premium-lodge:rooms')));assert.deepEqual(Object.keys(saved).sort(),['collapsed','view']);assert.equal(saved.view,'cards');assert.equal(JSON.stringify(saved).includes('Marula'),false);
 }finally{await context.close()}
 for(const option of [{readOnly:true},{expired:true}]){
  const {context,page,state}=await statusBoardFixture('rooms',option);
  try{assert.equal(await page.getByRole('combobox',{name:/^Move to…/}).isDisabled(),true);assert.equal(await page.getByRole('button',{name:'Move Marula',exact:true}).isDisabled(),true);assert.deepEqual(state.writes,[])}finally{await context.close()}
 }
});

test('status board cancellation requires confirmation and Escape leaves the record unchanged',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks');
 try{
  await page.getByRole('combobox',{name:/^Move to…/}).selectOption('cancelled');await page.getByRole('dialog').getByRole('heading',{name:'Cancel this record?',exact:true}).waitFor();assert.deepEqual(state.writes,[]);await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});assert.deepEqual(state.writes,[]);
  await page.getByRole('combobox',{name:/^Move to…/}).selectOption('cancelled');await page.getByRole('dialog').getByRole('button',{name:'Cancel record',exact:true}).click();await page.getByText('Board work moved to Cancelled.',{exact:true}).waitFor();assert.deepEqual(state.writes,[{status:'cancelled'}]);
 }finally{await context.close()}
});

test('status board touch sensor moves a card and keyboard Escape cancels without writing',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks');let client;
 try{
  const handle=page.getByRole('button',{name:'Move Board work',exact:true});await handle.focus();await page.keyboard.press('Space');await page.locator('[data-dragging]').waitFor();await page.locator('.statusColumn[data-status="assigned"][data-over]').waitFor();await page.keyboard.press('ArrowRight');await page.locator('.statusColumn[data-status="accepted"][data-over]').waitFor();await page.keyboard.press('Escape');await page.locator('[data-dragging]').waitFor({state:'hidden'});assert.deepEqual(state.writes,[]);await page.getByText('Move cancelled.',{exact:true}).waitFor();
  client=await context.newCDPSession(page);await client.send('Emulation.setTouchEmulationEnabled',{enabled:true});await handle.scrollIntoViewIfNeeded();const from=await handle.boundingBox(),to=await page.locator('.statusColumn[data-status="accepted"]').boundingBox();assert.ok(from&&to);
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:from.x+from.width/2,y:from.y+from.height/2,id:1}]});await page.locator('[data-dragging]').waitFor();await page.locator('.statusColumn[data-status="assigned"][data-over]').waitFor();await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:to.x+to.width/2,y:to.y+65,id:1}]});await page.locator('.statusColumn[data-status="accepted"][data-over]').waitFor();await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.getByText('Board work moved to Accepted.',{exact:true}).waitFor();assert.deepEqual(state.writes,[{status:'accepted'}]);
 }finally{if(client)await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]}).catch(()=>{});await context.close()}
});

test('status board requires an assignee for task assignment and inspection before housekeeping completion',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks',{initial:'created'});
 try{
  state.row.assigned_staff_id=null;await page.reload();await page.getByRole('combobox',{name:/^Move to…/}).waitFor();assert.equal(await page.getByRole('combobox',{name:/^Move to…/}).locator('option[value="assigned"]').isDisabled(),true);assert.deepEqual(state.writes,[]);
 }finally{await context.close()}
 const hk=await statusBoardFixture('housekeeping',{initial:'in_progress'});
 try{hk.state.row.inspector_staff_id='named-inspector';await hk.page.reload();await hk.page.getByRole('combobox',{name:/^Move to…/}).waitFor();assert.equal(await hk.page.getByRole('combobox',{name:/^Move to…/}).locator('option[value="completed"]').isDisabled(),true);assert.equal(await hk.page.getByRole('combobox',{name:/^Move to…/}).locator('option[value="awaiting_inspection"]').isDisabled(),false);assert.deepEqual(hk.state.writes,[])}finally{await hk.context.close()}
});

test('status board changing lodge during a drag cancels the old gesture without submitting',async()=>{
 const user=premiumTestAccount();user.groups=[{id:'board-group',name:'Assigned group'}];user.memberships.push({...user.memberships[0],lodge_id:'board-second-lodge',lodge_name:'Second lodge'});
 const {context,page}=await accountPage(user);const writes=[];
 try{
  await page.setViewportSize({width:1440,height:1000});await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/tasks**',r=>{if(r.request().method()==='PATCH'){writes.push(r.request().url());return r.fulfill({json:{id:'scoped-board',status:'accepted'}})}if(new URL(r.request().url()).pathname.endsWith('/tasks'))return r.fulfill({json:[{id:'scoped-board',title:'Former lodge task',status:'assigned',priority:'normal',description:'',assigned_staff_id:'staff-a',can_transition:true}]});return r.fallback()});
  await page.goto(base+'/tasks');await page.getByRole('button',{name:'Board',exact:true}).click();const handle=page.getByRole('button',{name:'Move Former lodge task',exact:true});await handle.focus();await page.keyboard.press('Space');await page.locator('[data-dragging]').waitFor();await page.evaluate(()=>{localStorage.setItem('active_lodge_id','board-second-lodge');window.dispatchEvent(new Event('safarios-lodge-changed'))});await page.getByRole('heading',{name:'Tasks',exact:true}).waitFor();await page.keyboard.press('ArrowRight');await page.keyboard.press('Space');assert.deepEqual(writes,[]);assert.equal(await page.getByText('Former lodge task',{exact:true}).count(),0);
 }finally{await context.close()}
});

test('status board card view retains its Move menu and persists the selected presentation',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks');
 try{
  await page.getByRole('button',{name:'Cards',exact:true}).click();await page.reload();await page.getByRole('combobox',{name:/^Move to…/}).waitFor();assert.equal(await page.getByRole('button',{name:'Cards',exact:true}).getAttribute('aria-pressed'),'true');assert.equal(await page.locator('.statusColumn').count(),0);assert.equal(await page.getByRole('button',{name:'Move Board work',exact:true}).isDisabled(),true);await page.getByRole('combobox',{name:/^Move to…/}).selectOption('accepted');await page.getByText('Board work moved to Accepted.',{exact:true}).waitFor();assert.deepEqual(state.writes,[{status:'accepted'}]);
 }finally{await context.close()}
});

test('status board does not adopt another account or lodge presentation settings',async()=>{
 const first=await statusBoardFixture('rooms');let saved;
 try{await first.page.getByRole('button',{name:'Cards',exact:true}).click();saved=await first.page.evaluate(()=>Object.entries(localStorage));}finally{await first.context.close()}
 for(const otherLodge of [false,true]){
  const user=premiumTestAccount();if(otherLodge)user.memberships[0].lodge_id='other-board-lodge';else user.id='other-board-user';
  const {context,page}=await accountPage(user);
  try{
   await context.addInitScript(pairs=>{for(const [key,value] of pairs)localStorage.setItem(key,value)},saved);await premiumFixtures(page);await page.route('**/api/v1/lodges/*/rooms',r=>r.fulfill({json:[{id:'other-board-room',name:'Other scoped room',unit_type:'Suite',status:'available',notes:''}]}));
   await page.goto(base+'/rooms');await page.getByText('Other scoped room',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Status board',exact:true}).getAttribute('aria-pressed'),'true');assert.equal(await page.getByRole('button',{name:'Cards',exact:true}).getAttribute('aria-pressed'),'false');assert.equal(await page.getByText('Marula',{exact:true}).count(),0);
  }finally{await context.close()}
 }
});

test('status board a delayed move does not steal focus or overwrite a newly opened form',async()=>{
 const {context,page}=await accountPage(premiumTestAccount());let release,status='available';
 try{
  await premiumFixtures(page);await page.route('**/api/v1/lodges/premium-lodge/rooms**',async r=>{
   if(r.request().method()==='PATCH'){await new Promise(resolve=>release=resolve);status=r.request().postDataJSON().status;return r.fulfill({json:{id:'focus-room',status}})}
   return r.fulfill({json:[{id:'focus-room',name:'Marula',unit_type:'Suite',status,notes:''}]});
  });
  await page.goto(base+'/rooms');await page.getByRole('combobox',{name:/^Move to…/}).selectOption('cleaning');await page.getByRole('button',{name:'+ Room / Unit',exact:true}).click();const input=page.getByRole('dialog').getByLabel('Name',{exact:true});await input.fill('New room draft');release();await page.getByText('Marula moved to Cleaning.',{exact:true}).waitFor();assert.equal(await input.inputValue(),'New room draft');assert.equal(await input.evaluate(node=>node===document.activeElement),true);
 }finally{release?.();await context.close()}
});

test('status board assigned staff can progress owned work but cannot assign or cancel it',async()=>{
 const user={id:'board-staff',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'owned-board-lodge',role_key:'general_staff',permissions:['tasks.view','tasks.own.manage'],entitlements:['tasks']}]};
 const {context,page,requests}=await accountPage(user);let status='assigned';const writes=[];
 try{
  await page.route('**/api/v1/lodges/owned-board-lodge/tasks**',r=>{if(r.request().method()==='PATCH'){const body=r.request().postDataJSON();writes.push(body);status=body.status;return r.fulfill({json:{id:'own-board-task',status}})}return r.fulfill({json:[{id:'own-board-task',title:'Owned task',description:'',priority:'normal',status,assigned_staff_id:'staff-a',can_transition:true}]})});
  await page.goto(base+'/tasks');const menu=page.getByRole('combobox',{name:/^Move to…/});await menu.waitFor();assert.equal(await menu.locator('option[value="cancelled"]').isDisabled(),true);await page.getByRole('button',{name:'Board',exact:true}).click();await page.getByRole('button',{name:'Move Owned task',exact:true}).focus();await page.keyboard.press('Space');for(let i=0;i<4;i++)await page.keyboard.press('ArrowRight');await page.keyboard.press('Space');await page.getByText('Cannot move to Cancelled.',{exact:true}).waitFor();await page.waitForFunction(()=>{const r=document.querySelector('.statusBoardItem')?.getBoundingClientRect();return r&&r.left>=0&&r.right<=innerWidth+1});assert.deepEqual(writes,[]);await menu.selectOption('accepted');await page.getByText('Owned task moved to Accepted.',{exact:true}).waitFor();assert.deepEqual(writes,[{status:'accepted'}]);status='created';await page.reload();await menu.waitFor();assert.equal(await menu.isDisabled(),true);assert.equal(await menu.locator('option[value="assigned"]').isDisabled(),true);assert.equal(requests.some(p=>/\/(staff|guests|departments|rooms)$/.test(p)),false);
 }finally{await context.close()}
});

test('status board rapid keyboard pick move drop and cancel do not lose input',async()=>{
 const {context,page,state}=await statusBoardFixture('tasks');
 try{
  const handle=page.getByRole('button',{name:'Move Board work',exact:true});await handle.focus();await page.keyboard.press('Space');await page.keyboard.press('ArrowRight');await page.keyboard.press('Space');await page.getByText('Board work moved to Accepted.',{exact:true}).waitFor();assert.deepEqual(state.writes,[{status:'accepted'}]);
  await handle.focus();await page.keyboard.press('Space');await page.keyboard.press('ArrowRight');await page.keyboard.press('Escape');await page.getByText('Move cancelled.',{exact:true}).waitFor();assert.equal(await page.locator('[data-dragging]').count(),0);assert.deepEqual(state.writes,[{status:'accepted'}]);
 }finally{await context.close()}
});

test('status board room-status permission allows status updates without room configuration controls',async()=>{
 const {context,page}=await accountPage({id:'room-status-user',is_super_admin:false,mfa_enabled:true,memberships:[{lodge_id:'room-status-lodge',permissions:['units.view','units.status.manage'],entitlements:['units'],subscription_status:'Active'}]});let status='available';const writes=[];
 try{
  await page.route('**/api/v1/lodges/room-status-lodge/rooms**',r=>{if(r.request().method()==='PATCH'){const body=r.request().postDataJSON();writes.push(body);status=body.status;return r.fulfill({json:{id:'status-only-room',status}})}return r.fulfill({json:[{id:'status-only-room',name:'Acacia',unit_type:'Suite',status,notes:''}]})});
  await page.goto(base+'/rooms');const menu=page.getByRole('combobox',{name:'Move to… Acacia',exact:true});await menu.waitFor();assert.equal(await page.getByRole('button',{name:'+ Room / Unit',exact:true}).count(),0);assert.equal(await menu.isDisabled(),false);await menu.selectOption('cleaning');await page.getByText('Acacia moved to Cleaning.',{exact:true}).waitFor();assert.deepEqual(writes,[{status:'cleaning'}]);
 }finally{await context.close()}
});
