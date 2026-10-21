import {actionFeedback} from "./action-feedback";
import {toast} from "sonner";
// Same-origin requests keep session/CSRF cookies on the application domain.
export const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

function readCookie(name:string){
  if(typeof document==='undefined') return '';
  const row=document.cookie.split('; ').find(v=>v.startsWith(name+'='));
  return row?decodeURIComponent(row.split('=').slice(1).join('=')):'';
}
export function getActiveLodgeId(){return typeof window==='undefined'?'':localStorage.getItem('active_lodge_id')||''}
export function setActiveLodgeId(id:string){if(typeof window!=='undefined')localStorage.setItem('active_lodge_id',id)}
export function getActiveUserId(){return typeof window==='undefined'?'':localStorage.getItem('active_user_id')||''}
function clearAccountContext(){
  if(typeof window==='undefined')return;
  for(const key of ['active_user_id','active_lodge_id','active_lodge_name'])localStorage.removeItem(key);
}
function bindAccount(user:any){
  if(typeof window==='undefined')return user;
  const previousUser=getActiveUserId(),previousLodge=getActiveLodgeId();
  if(getActiveUserId()!==user.id)clearAccountContext();
  localStorage.setItem('active_user_id',user.id);
  if(!user.is_super_admin&&!user.memberships?.some((m:any)=>m.lodge_id===getActiveLodgeId())){
    localStorage.removeItem('active_lodge_id');
    if(user.memberships?.[0])setActiveLodgeId(user.memberships[0].lodge_id);
  }
  if(previousUser===user.id&&previousLodge&&previousLodge!==getActiveLodgeId())window.dispatchEvent(new Event('safarios-lodge-changed'));
  return user;
}

async function request<T>(path:string, init:RequestInit={}){
  const headers=new Headers(init.headers||{});
  const expectedUser=getActiveUserId();
  const activeLodge=getActiveLodgeId();if(activeLodge&&path!=="/api/v1/auth/me"&&!headers.has("X-Lodge-Context"))headers.set("X-Lodge-Context",activeLodge);
  if(expectedUser&&path!=='/api/v1/auth/me'&&!headers.has('X-Expected-User-Id'))headers.set('X-Expected-User-Id',expectedUser);
  if(init.body) headers.set('Content-Type','application/json');
  if(init.method && !['GET','HEAD'].includes(init.method.toUpperCase())){
    const csrf=readCookie('lodge_csrf');
    if(csrf)headers.set('X-CSRF-Token',csrf);
  }
  const res=await fetch(`${API_URL}${path}`,{...init,headers,credentials:'include',cache:'no-store'}).catch(error=>{if(init.method&&!['GET','HEAD'].includes(init.method.toUpperCase())&&!path.startsWith('/api/v1/auth/'))toast.error('Connection interrupted. Check the record before trying again.',{id:`action:${path}`});throw error});
  if(res.status===401 && typeof window!=='undefined' && !location.pathname.startsWith('/login') && !location.pathname.startsWith('/activate')) location.href='/login';
  if(!res.ok){let message=`Request failed (${res.status})`;try{const body=await res.json();message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail||message)}catch{}if(res.status===403&&message.includes('not enabled for this lodge subscription')&&typeof window!=='undefined'){if(init.method&&!['GET','HEAD'].includes(init.method.toUpperCase()))toast.info('This action is no longer available. Your changes were not saved.',{id:`action:${path}`});window.dispatchEvent(new Event('safarios-feature-unavailable'));throw new Error('')}
if(init.method&&!['GET','HEAD'].includes(init.method.toUpperCase())&&!path.startsWith('/api/v1/auth/'))toast.error(message,{id:`action:${path}`});throw new Error(message)}
  const result=res.status===204?undefined:await res.json();
  actionFeedback(path,(init.method||'GET').toUpperCase(),result);
  return result as T;
}
const lodgePath=(suffix:string)=>{const id=getActiveLodgeId();if(!id)throw new Error('No lodge selected');return `/api/v1/lodges/${id}/${suffix}`};
type AccountScope={userId:string;lodgeId:string};
const scopedPath=(name:string,scope?:AccountScope)=>scope?`/api/v1/lodges/${scope.lodgeId}/${name}`:lodgePath(name);
const scopedHeaders=(scope?:AccountScope)=>scope?{'X-Expected-User-Id':scope.userId}:undefined;
const tenantCollection=(name:string)=>({
 list:<T=any[]>()=>request<T>(lodgePath(name)),
 create:<T=any>(body:any,scope?:AccountScope)=>request<T>(scopedPath(name,scope),{method:'POST',headers:scopedHeaders(scope),body:JSON.stringify(body)}),
 update:<T=any>(recordId:string,body:any)=>request<T>(lodgePath(`${name}/${recordId}`),{method:'PATCH',body:JSON.stringify(body)})
});

export const authApi={
 login:(email:string,password:string,otp?:string)=>request('/api/v1/auth/login',{method:'POST',body:JSON.stringify({email,password,otp:otp||undefined})}),
 previewInvitation:(token:string)=>request<any>('/api/v1/auth/invitations/preview',{method:'POST',body:JSON.stringify({token})}),
 activate:(token:string,password:string)=>request('/api/v1/auth/activate',{method:'POST',body:JSON.stringify({token,password})}),
 logout:async()=>{await request('/api/v1/auth/logout',{method:'POST'});clearAccountContext()},
 me:()=>request<any>('/api/v1/auth/me').then(bindAccount),
 requestPasswordReset:(email:string)=>request<any>('/api/v1/auth/password-reset/request',{method:'POST',body:JSON.stringify({email})}),
 confirmPasswordReset:(token:string,password:string)=>request<any>('/api/v1/auth/password-reset/confirm',{method:'POST',body:JSON.stringify({token,password})}),
 mfaSetup:()=>request<any>('/api/v1/auth/mfa/setup',{method:'POST'}),
 mfaConfirm:(code:string)=>request<any>('/api/v1/auth/mfa/confirm',{method:'POST',body:JSON.stringify({code})}),
 mfaDisable:(code:string,current_password:string)=>request<any>('/api/v1/auth/mfa/disable',{method:'POST',body:JSON.stringify({code,current_password})})
};

export const lodgeApi:any={
 dashboard:()=>request<any>(lodgePath('dashboard').replace(/\/dashboard$/,'/dashboard')),
 guests:tenantCollection('guests').list,
 createGuest:tenantCollection('guests').create,
 updateGuest:tenantCollection('guests').update,
 tasks:tenantCollection('tasks').list,
 createTask:tenantCollection('tasks').create,
 updateTask:tenantCollection('tasks').update,
 rooms:tenantCollection('rooms').list,
 createRoom:tenantCollection('rooms').create,
 updateRoom:tenantCollection('rooms').update,
 maintenance:tenantCollection('maintenance').list,
 createMaintenance:tenantCollection('maintenance').create,
 updateMaintenance:tenantCollection('maintenance').update,
};

export const operationsApi={
 staff:{...tenantCollection('staff'),resendInvitation:(id:string)=>request<any>(lodgePath(`staff/${id}/invitation/resend`),{method:'POST'}),invite:(id:string,role_key:string)=>request<any>(lodgePath(`staff/${id}/invite`),{method:'POST',body:JSON.stringify({role_key})}),assignCustomRole:(id:string,custom_role_id:string|null)=>request<any>(lodgePath(`staff/${id}/custom-role`),{method:'PATCH',body:JSON.stringify({custom_role_id})})},
 departments:tenantCollection('departments'),
 stays:tenantCollection('stays'),
 requests:{...tenantCollection('requests'),createTask:(id:string)=>request(lodgePath(`requests/${id}/create-task`),{method:'POST'})},
 vehicles:tenantCollection('vehicles'),
 checklists:tenantCollection('vehicle-checklists'),
 fuel:tenantCollection('fuel'),
 activities:tenantCollection('activities'),
 transfers:tenantCollection('transfers'),
 wildlife:{...tenantCollection('wildlife'),uploadUrl:(body:any,scope?:AccountScope)=>request<any>(scopedPath('wildlife/media/upload-url',scope),{method:'POST',headers:scopedHeaders(scope),body:JSON.stringify(body)}),registerMedia:(body:any,scope?:AccountScope)=>request<any>(scopedPath('wildlife/media',scope),{method:'POST',headers:scopedHeaders(scope),body:JSON.stringify(body)}),downloadUrl:(id:string)=>request<any>(lodgePath(`wildlife/media/${id}/download-url`))},
 rangerToday:()=>request<any>(lodgePath('ranger/today')),
 hr:{leaves:{list:()=>request<any[]>(lodgePath('hr/leaves')),create:(body:any)=>request<any>(lodgePath('hr/leaves'),{method:'POST',body:JSON.stringify(body)}),update:(id:string,body:any)=>request<any>(lodgePath(`hr/leaves/${id}`),{method:'PATCH',body:JSON.stringify(body)})},credentials:{list:()=>request<any[]>(lodgePath('hr/credentials')),create:(body:any)=>request<any>(lodgePath('hr/credentials'),{method:'POST',body:JSON.stringify(body)})},training:{list:()=>request<any[]>(lodgePath('hr/training')),create:(body:any)=>request<any>(lodgePath('hr/training'),{method:'POST',body:JSON.stringify(body)})},shifts:{list:()=>request<any[]>(lodgePath('hr/shifts')),create:(body:any)=>request<any>(lodgePath('hr/shifts'),{method:'POST',body:JSON.stringify(body)}),update:(id:string,body:any)=>request<any>(lodgePath(`hr/shifts/${id}`),{method:'PATCH',body:JSON.stringify(body)})},incidents:{list:()=>request<any[]>(lodgePath('hr/incidents')),create:(body:any)=>request<any>(lodgePath('hr/incidents'),{method:'POST',body:JSON.stringify(body)})},performance:{list:()=>request<any[]>(lodgePath('hr/performance')),create:(body:any)=>request<any>(lodgePath('hr/performance'),{method:'POST',body:JSON.stringify(body)})}},
 roles:{list:()=>request<any[]>(lodgePath('custom-roles')),permissions:()=>request<any[]>(lodgePath('available-permissions')),create:(body:any)=>request<any>(lodgePath('custom-roles'),{method:'POST',body:JSON.stringify(body)}),update:(id:string,body:any)=>request<any>(lodgePath(`custom-roles/${id}`),{method:'PATCH',body:JSON.stringify(body)})},
 housekeeping:{list:()=>request<any[]>(lodgePath('housekeeping-jobs')),create:(body:any)=>request<any>(lodgePath('housekeeping-jobs'),{method:'POST',body:JSON.stringify(body)}),update:(id:string,body:any)=>request<any>(lodgePath(`housekeeping-jobs/${id}`),{method:'PATCH',body:JSON.stringify(body)})},
 taskWorkflow:{checklist:(id:string)=>request<any[]>(lodgePath(`tasks/${id}/checklist`)),addChecklist:(id:string,body:any)=>request<any>(lodgePath(`tasks/${id}/checklist`),{method:'POST',body:JSON.stringify(body)}),updateChecklist:(id:string,item:string,completed:boolean)=>request<any>(lodgePath(`tasks/${id}/checklist/${item}`),{method:'PATCH',body:JSON.stringify({completed})}),comments:(id:string)=>request<any[]>(lodgePath(`tasks/${id}/comments`)),addComment:(id:string,body:string)=>request<any>(lodgePath(`tasks/${id}/comments`),{method:'POST',body:JSON.stringify({body})})},
 maintenanceAssets:{list:()=>request<any[]>(lodgePath('maintenance-assets')),create:(body:any)=>request<any>(lodgePath('maintenance-assets'),{method:'POST',body:JSON.stringify(body)}),parts:(ticket:string)=>request<any[]>(lodgePath(`maintenance/${ticket}/parts`)),addPart:(ticket:string,body:any)=>request<any>(lodgePath(`maintenance/${ticket}/parts`),{method:'POST',body:JSON.stringify(body)})},
 feedback:{list:()=>request<any[]>(lodgePath('feedback')),create:(body:any)=>request<any>(lodgePath('feedback'),{method:'POST',body:JSON.stringify(body)}),update:(id:string,body:any)=>request<any>(lodgePath(`feedback/${id}`),{method:'PATCH',body:JSON.stringify(body)})},
 foodBeverage:{list:()=>request<any[]>(lodgePath('food-beverage/meals')),create:(body:any)=>request<any>(lodgePath('food-beverage/meals'),{method:'POST',body:JSON.stringify(body)}),update:(id:string,body:any)=>request<any>(lodgePath(`food-beverage/meals/${id}`),{method:'PATCH',body:JSON.stringify(body)})},
 taskAttachments:{list:(taskId:string)=>request<any[]>(lodgePath(`tasks/${taskId}/attachments`)),uploadUrl:(taskId:string,body:any)=>request<any>(lodgePath(`tasks/${taskId}/attachments/upload-url`),{method:'POST',body:JSON.stringify(body)}),register:(taskId:string,body:any)=>request<any>(lodgePath(`tasks/${taskId}/attachments`),{method:'POST',body:JSON.stringify(body)}),download:(taskId:string,id:string)=>request<any>(lodgePath(`tasks/${taskId}/attachments/${id}/download-url`))},
};

export const intelligenceApi={
 notifications:()=>request<any[]>(lodgePath('notifications')),
 markNotificationRead:(id:string)=>request(lodgePath(`notifications/${id}/read`),{method:'POST'}),
 notificationPreferences:()=>request<any>(lodgePath('notification-preferences')),
 updateNotificationPreferences:(body:any)=>request<any>(lodgePath('notification-preferences'),{method:'PATCH',body:JSON.stringify(body)}),
 notificationDeliveries:()=>request<any[]>(lodgePath('notification-deliveries')),
 operationalMemory:(params:Record<string,string|undefined>={})=>{const q=new URLSearchParams();Object.entries(params).forEach(([k,v])=>{if(v)q.set(k,v)});return request<any[]>(lodgePath(`operational-memory${q.toString()?`?${q}`:''}`))},
 reportSummary:(start?:string,end?:string)=>{const q=new URLSearchParams();if(start)q.set('start',start);if(end)q.set('end',end);return request<any>(lodgePath(`reports/summary${q.toString()?`?${q}`:''}`))},
};

export const lodgeBrandingApi={get:(id:string)=>request<{display_name:string;logo_url:string|null;platform_name:string}>(`/api/v1/lodges/${id}/branding`)};

export const superApi={
 inviteUser:(body:{email:string;full_name:string})=>request<any>('/api/v1/platform/users/invite',{method:'POST',body:JSON.stringify(body)}),
 resendInvitation:(id:string)=>request<any>(`/api/v1/platform/users/${id}/invitation`,{method:'POST'}),
 emailStatus:()=>request<any>('/api/v1/platform/email'),
 testEmail:()=>request<any>('/api/v1/platform/email/test',{method:'POST'}),
 retryEmail:(id:string)=>request<any>(`/api/v1/platform/email/${id}/retry`,{method:'POST'}),
 updateBranding:(id:string,body:{display_name:string;logo_base64?:string;remove_logo?:boolean})=>request(`/api/v1/platform/lodges/${id}/branding`,{method:'PATCH',body:JSON.stringify(body)}),
 lodges:()=>request<any[]>('/api/v1/platform/lodges'),
 createLodge:(body:any)=>request<any>('/api/v1/platform/lodges',{method:'POST',body:JSON.stringify(body)}),
 updateSubscription:(id:string,body:any)=>request(`/api/v1/platform/lodges/${id}/subscription`,{method:'PATCH',body:JSON.stringify(body)}),
 platformNotifications:()=>request<any[]>('/api/v1/platform/notifications'),
 plans:()=>request<any[]>('/api/v1/platform/plans'),
 lodgeEntitlements:(id:string)=>request<any>(`/api/v1/platform/lodges/${id}/entitlements`),
 setEntitlement:(id:string,feature_key:string,enabled:boolean|null)=>request<any>(`/api/v1/platform/lodges/${id}/entitlements`,{method:'PATCH',body:JSON.stringify({feature_key,enabled})}),
 audit:()=>request<any[]>('/api/v1/platform/audit'),
 users:()=>request<any[]>('/api/v1/platform/users')
};

export {request};

export const accountNotificationsApi={
 list:(unread=false,severity='')=>request<any[]>(`/api/v1/auth/notifications?unread_only=${unread}${severity?'&severity='+encodeURIComponent(severity):''}`),
 summary:()=>request<{unread:number}>('/api/v1/auth/notifications/summary'),
 read:(id:string)=>request(`/api/v1/auth/notifications/${id}/read`,{method:'POST'}),
 readAll:()=>request('/api/v1/auth/notifications/read-all',{method:'POST'}),
 archive:(id:string)=>request(`/api/v1/auth/notifications/${id}/archive`,{method:'POST'}),
 preferences:()=>request<any>('/api/v1/auth/notification-preferences'),
 updatePreferences:(body:{email_enabled:boolean;email_min_severity:string})=>request<any>('/api/v1/auth/notification-preferences',{method:'PATCH',body:JSON.stringify(body)}),
};

export const groupsApi={
 resendAdmin:(lodge:string,id:string)=>request<any>(`/api/v1/lodges/${lodge}/administrators/${id}/invitation/resend`,{method:"POST"}),
 revokeAdmin:(lodge:string,id:string)=>request<any>(`/api/v1/lodges/${lodge}/administrators/${id}/revoke-access`,{method:"POST"}),
 restoreAdmin:(lodge:string,id:string)=>request<any>(`/api/v1/lodges/${lodge}/administrators/${id}/restore-access`,{method:"POST"}),
 list:()=>request<any[]>('/api/v1/platform/groups'),
 create:(body:any)=>request<any>('/api/v1/platform/groups',{method:'POST',body:JSON.stringify(body)}),
 update:(id:string,body:any)=>request<any>(`/api/v1/platform/groups/${id}`,{method:'PATCH',body:JSON.stringify(body)}),
 overview:(id:string)=>request<any>(`/api/v1/groups/${id}/overview`),
 inviteAdmin:(id:string,body:any)=>request<any>(`/api/v1/lodges/${id}/administrators/invite`,{method:'POST',body:JSON.stringify(body)})
};
