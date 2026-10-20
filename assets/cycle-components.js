(async()=>{
const root=document.getElementById('cycleComponents');if(!root)return;
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
try{
const r=await fetch('data/cycle_components.json?t='+Date.now());if(!r.ok)throw Error('HTTP '+r.status);
const d=await r.json(),names={leading:'Leading · 10 componentes',coincident:'Coincident · 4 componentes',lagging:'Lagging · 7 componentes'};
root.innerHTML=Object.entries(names).map(([group,title])=>'<details style="margin:12px 0"><summary style="cursor:pointer;font-weight:650">'+title+'</summary><div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead><tr><th align="left">Componente</th><th align="right">Último valor</th><th align="right">Variación</th><th align="left">Período</th><th align="left">Fuente</th></tr></thead><tbody>'+
(d.groups?.[group]||[]).map(x=>{
const h=x.history||[],last=h.at(-1),prev=h.at(-2),delta=last&&prev&&prev[1]!==0?((last[1]/prev[1]-1)*100).toFixed(2)+'%':'—';
return '<tr style="border-top:1px solid #9995"><td>'+escape(x.name)+'</td><td align="right">'+(x.value===undefined?'—':escape(x.value))+'</td><td align="right">'+delta+'</td><td>'+escape(x.period||'Sin dato')+(x.status!=='ok'?' ⚠':'')+'</td><td>'+(x.url?'<a target="_blank" rel="noopener" href="'+escape(x.url)+'">FRED</a>':'No disponible')+'</td></tr>';
}).join('')+'</tbody></table></div></details>').join('');
document.getElementById('cycleComponentsStatus').textContent='Datos originales de fuentes públicas, no contribuciones calculadas por The Conference Board. Variación simple entre las dos últimas observaciones; frecuencia según serie. Las señales de mejora/deterioro requieren interpretar el sentido económico de cada variable. Consulta: '+(d.checked_at||'—');
}catch(e){root.textContent='Datos de componentes aún no disponibles.';document.getElementById('cycleComponentsStatus').textContent='La primera actualización está pendiente.';}
})();