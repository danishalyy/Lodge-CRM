'use client';
import { useEffect, useState } from 'react';
export default function ThemeToggle(){
 const [dark,setDark]=useState(true);
 useEffect(()=>{const saved=localStorage.getItem('theme');const d=saved!=='light';setDark(d);document.documentElement.dataset.theme=d?'dark':'light'},[]);
 function toggle(){const d=!dark;setDark(d);document.documentElement.dataset.theme=d?'dark':'light';localStorage.setItem('theme',d?'dark':'light')}
 return <button className="iconButton" onClick={toggle} aria-label="Toggle light and dark theme">{dark?'☼':'◐'}</button>
}
