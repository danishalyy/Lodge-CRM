// Same-origin requests keep session/CSRF cookies on the application domain.
export const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

function readCookie(name:string){
  if(typeof document==='undefined') return '';
  const row=document.cookie.split('; ').find(v=>v.startsWith(name+'='));
  return row?decodeURIComponent(row.split('=').slice(1).join('=')):'';
}
export function getActiveLodgeId(){return typeof window==='undefined'?'':localStorage.getItem('active_lodge_id')||''}
export function setActiveLodgeId(id:string){if(typeof window!=='undefined')localStorage.setItem('active_lodge_id',id)}

async function request<T>(path:string, init:RequestInit={}){
  const headers=new Headers(init.headers||{});
  if(init.body) headers.set('Content-Type','application/json');
  if(init.method && !['GET','HEAD'].includes(init.method.toUpperCase())){
    const csrf=readCookie('lodge_csrf');
    if(csrf)headers.set('X-CSRF-Token',csrf);
  }
  const res=await fetch(`${API_URL}${path}`,{...init,headers,credentials:'include',cache:'no-store'});
  if(res.status===401 && typeof window!=='undefined' && !location.pathname.startsWith('/login') && !location.pathname.startsWith('/activate')) location.href='/login';
  if(!res.ok){let message=`Request failed (${res.status})`;try{const body=await res.json();message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail||message)}catch{}throw new Error(message)}
  if(res.status===204)return undefined as T;
  return (await res.json()) as T;
}
const lodgePath=(suffix:string)=>{const id=getActiveLodgeId();if(!id)throw new Error('No lodge selected');return `/api/v1/lodges/${id}/${suffix}`};
const tenantCollection=(name:string)=>({
 list:<T=any[]>()=>request<T>(lodgePath(name)),
 create:<T=any>(body:any)=>request<T>(lodgePath(name),{method:'POST',body:JSON.stringify(body)}),
 update:<T=any>(recordId:string,body:any)=>request<T>(lodgePath(`${name}/${recordId}`),{method:'PATCH',body:JSON.stringify(body)})
});

export const authApi={
 login:(email:string,password:string,otp?:string)=>request('/api/v1/auth/login',{method:'POST',body:JSON.stringify({email,password,otp:otp||undefined})}),
 activate:(token:string,password:string)=>request('/api/v1/auth/activate',{method:'POST',body:JSON.stringify({token,password})}),
 logout:()=>request('/api/v1/auth/logout',{method:'POST'}),
 me:()=>request<any>('/api/v1/auth/me'),
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
 staff:{...tenantCollection('staff'),invite:(id:string,role_key:string)=>request<any>(lodgePath(`staff/${id}/invite`),{method:'POST',body:JSON.stringify({role_key})}),assignCustomRole:(id:string,custom_role_id:string|null)=>request<any>(lodgePath(`staff/${id}/custom-role`),{method:'PATCH',body:JSON.stringify({custom_role_id})})},
 departments:tenantCollection('departments'),
 stays:tenantCollection('stays'),
 requests:{...tenantCollection('requests'),createTask:(id:string)=>request(lodgePath(`requests/${id}/create-task`),{method:'POST'})},
 vehicles:tenantCollection('vehicles'),
 checklists:tenantCollection('vehicle-checklists'),
 fuel:tenantCollection('fuel'),
 activities:tenantCollection('activities'),
 transfers:tenantCollection('transfers'),
 wildlife:{...tenantCollection('wildlife'),uploadUrl:(body:any)=>request<any>(lodgePath('wildlife/media/upload-url'),{method:'POST',body:JSON.stringify(body)}),registerMedia:(body:any)=>request<any>(lodgePath('wildlife/media'),{method:'POST',body:JSON.stringify(body)}),downloadUrl:(id:string)=>request<any>(lodgePath(`wildlife/media/${id}/download-url`))},
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

export const superApi={
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
