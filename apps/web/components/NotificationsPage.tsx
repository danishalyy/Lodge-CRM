'use client';
import {useEffect,useState} from 'react';
import {intelligenceApi} from '@/lib/api';

type Notification={id:string;type:string;severity:string;title:string;body:string;resource_type:string;resource_id:string;created_at:string;read_at:string|null};
export default function NotificationsPage(){
 const[rows,setRows]=useState<Notification[]>([]),[prefs,setPrefs]=useState({email_enabled:false,email_min_severity:'high'}),[error,setError]=useState(''),[saving,setSaving]=useState(false);
 const load=async()=>{try{const[r,p]=await Promise.all([intelligenceApi.notifications(),intelligenceApi.notificationPreferences()]);setRows(r);setPrefs(p)}catch(e:any){setError(e.message)}};
 useEffect(()=>{load()},[]);
 async function markRead(id:string){try{await intelligenceApi.markNotificationRead(id);setRows(v=>v.map(x=>x.id===id?{...x,read_at:new Date().toISOString()}:x))}catch(e:any){setError(e.message)}}
 async function savePrefs(){setSaving(true);try{const p=await intelligenceApi.updateNotificationPreferences(prefs);setPrefs(p)}catch(e:any){setError(e.message)}finally{setSaving(false)}}
 return <><div className="pageHeader"><div><span className="eyebrow">OPERATIONS INTELLIGENCE</span><h1>Notifications</h1><p>Stay informed about the work and updates that need your attention.</p></div></div>
 {error&&<div className="panel dangerText">{error}</div>}
 <div className="twoCol"><section className="panel"><div className="panelHeader"><div><h2>Inbox</h2><p>{rows.filter(x=>!x.read_at).length} unread</p></div></div>{rows.map(n=><div className="row" key={n.id}><div><strong>{n.title}</strong><div style={{color:'var(--tx3)',fontSize:12,marginTop:3}}>{n.body||n.type}</div><div style={{color:'var(--tx3)',fontSize:12,marginTop:4}}>{new Date(n.created_at).toLocaleString()} · {n.severity}</div></div>{!n.read_at&&<button className="button" onClick={()=>markRead(n.id)}>Mark read</button>}</div>)}{!rows.length&&<div className="empty">No system notifications have been generated for your account.</div>}</section>
 <section className="panel"><div className="panelHeader"><div><h2>Delivery preferences</h2><p>In-app notifications are always retained. Email delivery is optional.</p></div></div><div className="checkRow"><span>Email notifications</span><input type="checkbox" checked={prefs.email_enabled} onChange={e=>setPrefs({...prefs,email_enabled:e.target.checked})}/></div><label className="label">Minimum severity for email</label><select className="select" value={prefs.email_min_severity} onChange={e=>setPrefs({...prefs,email_min_severity:e.target.value})}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical only</option></select><div style={{marginTop:12}}><button className="button primary" disabled={saving} onClick={savePrefs}>{saving?'Saving…':'Save preferences'}</button></div></section></div></>
}
