'use client';
import {useEffect,useMemo,useState} from 'react';
import Link from 'next/link';
import StatusPill from './StatusPill';
import {superApi} from '@/lib/api';

type LodgeRow={
  id:string;
  name:string;
  location?:string|null;
  subscription?:{
    package?:string|null;
    start_date?:string|null;
    expiry_date?:string|null;
    suspended?:boolean;
    status?:string|null;
  }|null;
};

function subscriptionStatus(row:LodgeRow){
  if(row.subscription?.suspended)return 'Suspended';
  const raw=row.subscription?.expiry_date;
  if(!raw)return 'Not configured';
  const expiry=new Date(`${raw}T23:59:59`);
  const days=Math.ceil((expiry.getTime()-Date.now())/86400000);
  if(days<0)return 'Expired';
  if(days<=30)return 'Expiring Soon';
  return 'Active';
}

function daysLeft(row:LodgeRow){
  const raw=row.subscription?.expiry_date;
  if(!raw)return null;
  return Math.ceil((new Date(`${raw}T23:59:59`).getTime()-Date.now())/86400000);
}

export default function SuperAdminOverview(){
  const[rows,setRows]=useState<LodgeRow[]>([]);
  const[error,setError]=useState('');
  const[loading,setLoading]=useState(true);
  useEffect(()=>{superApi.lodges().then(v=>setRows(v as LodgeRow[])).catch((e:any)=>setError(e.message)).finally(()=>setLoading(false))},[]);
  const stats=useMemo(()=>{
    const active=rows.filter(r=>subscriptionStatus(r)==='Active').length;
    const expiring=rows.filter(r=>subscriptionStatus(r)==='Expiring Soon').length;
    const attention=rows.filter(r=>['Expiring Soon','Expired','Suspended','Not configured'].includes(subscriptionStatus(r))).length;
    return {total:rows.length,active,expiring,attention};
  },[rows]);
  return <>
    <div className="pageHeader"><div><span className="eyebrow">PLATFORM CONTROL</span><h1>Super Admin</h1><p>Register lodges, control packages, subscription dates and platform access.</p></div><Link href="/super-admin/lodges" className="button primary">+ Register lodge</Link></div>
    {error&&<p className="dangerText">{error}</p>}
    <div className="metricGrid superStats">
      <div className="metricCard"><span>Total lodges</span><strong>{loading?'—':stats.total}</strong><small>{loading?'Loading…':`${stats.active} active`}</small></div>
      <div className="metricCard"><span>Expiring in 30 days</span><strong>{loading?'—':stats.expiring}</strong><small className="warningText">Calculated from real subscription dates</small></div>
      <div className="metricCard"><span>Platform attention</span><strong>{loading?'—':stats.attention}</strong><small>Expiry, suspension or setup issues</small></div>
    </div>
    <section className="panel tableWrap"><div className="panelHeader"><div><h2>Lodge subscriptions</h2><p>External payment · manual access control</p></div><Link href="/super-admin/subscriptions" className="linkButton">View all →</Link></div>
      <table className="dataTable"><thead><tr><th>Lodge</th><th>Package</th><th>Expiry</th><th>Days</th><th>Status</th></tr></thead><tbody>{rows.slice(0,8).map(r=>{const days=daysLeft(r),status=subscriptionStatus(r);return <tr key={r.id}><td>{r.name}</td><td>{r.subscription?.package||'—'}</td><td>{r.subscription?.expiry_date||'—'}</td><td>{days===null?'—':days}</td><td><StatusPill value={status}/></td></tr>})}</tbody></table>
      {!loading&&!rows.length&&<p style={{color:'var(--tx3)'}}>No lodges registered yet.</p>}
    </section>
  </>;
}
