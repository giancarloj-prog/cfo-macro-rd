(async function(){
 const box=document.getElementById('economicCycle');if(!box)return;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 try{
 const r=await fetch('data/economic_cycle.json?ts='+Date.now());if(!r.ok)throw Error('HTTP '+r.status);
 const data=await r.json();
 box.innerHTML=['leading','coincident','lagging'].map((key)=>{
 const names={leading:'Leading · LEI',coincident:'Coincident · CEI',lagging:'Lagging · LAG'};
 const x=data.series?.[key],health=data.source_health?.[key],entries=Object.entries(x?.history||{}).sort(([a],[b])=>a.localeCompare(b));
 const last=entries.at(-1),prev=entries.at(-2);
 const change=last&&prev&&prev[1]!==0?(100*(last[1]/prev[1]-1)).toFixed(2)+'%':'—';
 const points=entries.length>1?entries.map(([d,v],i)=>{const vals=entries.map(e=>e[1]);const lo=Math.min(...vals),hi=Math.max(...vals),range=hi-lo||1;return (10+i*300/(entries.length-1)).toFixed(1)+','+(85-(v-lo)/range*70).toFixed(1)}).join(' '):'';
 return '<div class="card"><div class="k">'+names[key]+'</div><div class="v">'+(x?Number(x.value).toFixed(1):'—')+'</div><div class="meta">Período: '+esc(x?.period||'sin datos')+' · Cambio mensual: '+change+'</div>'+(points?'<svg viewBox="0 0 320 100" style="width:100%;height:110px" role="img" aria-label="Histórico '+names[key]+'"><polyline fill="none" stroke="#79aaff" stroke-width="2.5" points="'+points+'"/></svg>':'')+'<div class="source-note">'+(health?.ok?'Fuente verificada':'Actualización no verificada; no asumir vigencia')+'</div>'+(x?.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener">Fuente</a>':'')+'</div>';
 }).join('');
 document.getElementById('economicCycleStatus').textContent='Última consulta: '+esc(data.checked_at||'—')+'. Los índices de The Conference Board no deben confundirse con PMI. Si la fuente pública no ofrece datos recientes, se muestra la falta de cobertura.';
 }catch(e){box.innerHTML='<div class="empty">No hay datos verificados disponibles.</div>';document.getElementById('economicCycleStatus').textContent='Consulta no disponible: '+esc(e.message);}
})();