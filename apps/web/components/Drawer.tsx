'use client';
export default function Drawer({children,onClose}:{children:React.ReactNode,onClose:()=>void}){return <><div className="drawerOverlay" onClick={onClose}/><aside className="drawer">{children}</aside></>}
