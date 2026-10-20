'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { authApi } from '@/lib/api';
import ThemeToggle from './ThemeToggle';
import SignOutButton from './SignOutButton';
import AccountChangeGuard from './AccountChangeGuard';
const items=[['','Overview','◫'],['lodges','Lodges','⌂'],['subscriptions','Subscriptions','◷'],['packages','Packages','▦'],['users','Platform Users','◎'],['audit','Audit','≡'],['settings','Settings','⚙']];
export default function SuperAdminShell({children}:{children:React.ReactNode}){const p=usePathname();
 const router=useRouter();
 const [status,setStatus]=useState<'loading'|'allowed'|'denied'|'error'>('loading');
 useEffect(()=>{
  let active=true;
  authApi.me().then(user=>{
   if(!active)return;
   if(!user.is_super_admin){setStatus('denied');return;}
   if(!user.mfa_enabled){router.replace('/settings');return;}
   setStatus('allowed');
  }).catch(()=>{if(active)setStatus('error')});
  return ()=>{active=false};
 },[router]);
 if(status==='loading')return <main className="content" role="status">Checking platform access…</main>;
 if(status==='denied')return <main className="content"><section className="panel"><h1>Access denied</h1><p>Your lodge account does not have platform administration access.</p><Link className="button" href="/dashboard">Return to lodge dashboard</Link></section></main>;
 if(status==='error')return <main className="content"><section className="panel"><h1>Unable to verify access</h1><p>Please sign in again or retry when your connection is available.</p><Link className="button" href="/login">Sign in</Link></section></main>;
 return <div className="appShell"><AccountChangeGuard/><aside className="sidebar"><div className="brand"><div className="brandMark">L</div><div>Lodge <span>CRM</span></div></div><div className="roleBox"><label>Authenticated role</label><div className="roleSelect">Super Admin</div></div><div className="lodgeMini"><strong>Platform Console</strong><small>All lodges · owner access</small></div><nav><div className="navSection">Platform</div>{items.map(([k,l,i])=><Link key={k} href={`/super-admin${k?'/'+k:''}`} className={p===`/super-admin${k?'/'+k:''}`?'navItem active':'navItem'}><span className="navIcon">{i}</span>{l}</Link>)}</nav><div className="sidebarFooter"><div className="avatar">SA</div><div><strong>Super Admin</strong><small>Platform owner</small></div></div></aside><main className="mainArea"><header className="topbar"><div className="topContext"><span className="statusDot"/><span>Platform administration</span></div><div className="topActions"><ThemeToggle/><SignOutButton/></div></header><div className="content">{children}</div></main></div>}
