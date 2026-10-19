import ModulePage from './ModulePage';
export default function OperationsModule({kind}:{kind:string}){return <ModulePage title={kind.charAt(0).toUpperCase()+kind.slice(1)}/>}
