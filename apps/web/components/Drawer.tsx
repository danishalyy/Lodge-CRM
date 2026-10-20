'use client';
import {useEffect,useRef} from 'react';
export default function Drawer({children,onClose}:{children:React.ReactNode;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),close=useRef(onClose);close.current=onClose;
 useEffect(()=>{const el=dialog.current;const previous=document.activeElement as HTMLElement|null;el?.showModal();const overflow=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{el?.close();document.body.style.overflow=overflow;previous?.focus()}},[]);
 return <dialog ref={dialog} className="safariDialog" aria-label="Details and actions" onCancel={e=>{e.preventDefault();close.current()}} onClick={e=>{if(e.target===e.currentTarget)close.current()}}><div className="drawer">{children}</div></dialog>;
}
