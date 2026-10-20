const paths:Record<string,string>={
 arrow:'M7 17 17 7M7 7h10v10',
 overview:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
 lodge:'M3 21V9l9-6 9 6v12M9 21v-7h6v7M6 10h.01M18 10h.01',
 people:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3a4 4 0 0 1 0 8',
 tasks:'m8 11 3 3 6-7M5 3h14v18H5z',
 settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2',
 reports:'M4 21V3h16v18zM8 16v-3M12 16V8M16 16v-5',
 fleet:'M3 17V9l3-5h12l3 5v8M3 9h18M7 17h10M6 17v3M18 17v3M6 13h1M17 13h1',
 calendar:'M4 5h16v16H4zM8 2v6M16 2v6M4 10h16',
 leaf:'M20 3C8 2 2 8 5 15c6 6 16 0 15-12ZM4 21 15 10',
 search:'M21 21l-5-5M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14',
 bell:'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
 menu:'M4 6h16M4 12h16M4 18h16',
 close:'m6 6 12 12M6 18 18 6',
};
export default function UiIcon({name}:{name:string}){return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.tasks}/></svg>}
export function moduleIcon(key:string){return ['guests','staff','hr','roles'].includes(key)?'people':['rooms','housekeeping','lodges'].includes(key)?'lodge':['activities','stays','transfers'].includes(key)?'calendar':['fleet','fuel','maintenance'].includes(key)?'fleet':['wildlife','ranger'].includes(key)?'leaf':['reports','memory','audit','packages','subscriptions'].includes(key)?'reports':key==='settings'?'settings':key==='dashboard'||key===''?'overview':'tasks'}
