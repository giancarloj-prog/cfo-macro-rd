(()=>{
 'use strict';
 const el=id=>document.getElementById(id);
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const link=(url,label)=>/^https:\/\//.test(url||'')?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`:esc(label);
 const pct=v=>Number.isFinite(v)?`${v>0?'+':''}${v.toFixed(1)}%`:'—';
 const num=v=>Number.isFinite(v)?v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'—';
 const month=p=>/^\d{4}-\d{2}$/.test(p||'')?new Date(p+'-15T12:00:00Z').toLocaleDateString('es-DO',{month:'short',year:'numeric',timeZone:'UTC'}):p||'Sin dato';
 const checked=s=>s?new Date(s).toLocaleString('es-DO',{timeZone:'America/Santo_Domingo'}):'Pendiente';
 const old=x=>!x?.period||(Date.now()-Date.parse(x.period+'-01T00:00:00Z'))/86400000>120;
 const expected={aluminum:'Aluminio primario',resins:'Resinas termoplásticas',corrugated:'Cartón corrugado',paperboard:'Cajas plegadizas',ethanol:'Etanol',sugar:'Azúcar mundial',gscpi:'Presión logística global'};
 let data=null;
 function spark(s){
  const history=(s.history||[]).slice(-24);if(history.length<2)return '<p class="source-note">Histórico insuficiente para graficar.</p>';
  const values=history.map(x=>x.value),min=Math.min(...values),max=Math.max(...values),range=max-min||1,W=330,H=90;
  const x=i=>8+i*(W-16)/(history.length-1),y=v=>12+48*(max-v)/range;
  const points=history.map((o,i)=>`${x(i)},${y(o.value)}`).join(' ');
  return `<svg class="inputs-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(s.name)}: ${month(history[0].period)} a ${month(history.at(-1).period)}, ${num(values[0])} a ${num(values.at(-1))} ${esc(s.unit)}"><polyline points="${points}" fill="none" stroke="var(--blue)" stroke-width="2.5"/>${history.map((o,i)=>`<circle cx="${x(i)}" cy="${y(o.value)}" r="2" fill="var(--blue)"><title>${month(o.period)}: ${num(o.value)} ${esc(s.unit)}</title></circle>`).join('')}<text x="8" y="85">${month(history[0].period)}</text><text x="322" y="85" text-anchor="end">${month(history.at(-1).period)}</text></svg>`;
 }
 function card(key){
  const s=data.series?.[key],health=data.source_health?.[key];
  if(!s)return `<article class="card inputs-card"><h3>${expected[key]}</h3><div class="v">—</div><div class="meta">Sin dato público validado en esta consulta.</div></article>`;
  const logistical=key==='gscpi',prior=s.history?.find(x=>x.period===previousMonth(s.period)),diff=prior?s.value-prior.value:null;
  const changes=logistical?`<span><small>Mes anterior · puntos</small>${Number.isFinite(diff)?(diff>0?'+':'')+diff.toFixed(2):'—'}</span>`:[['mom','1 mes'],['qoq','3 meses'],['yoy','12 meses']].map(([k,label])=>`<span class="${s.changes?.[k]>0?'inputs-up':s.changes?.[k]<0?'inputs-down':''}"><small>${label}</small>${pct(s.changes?.[k])}</span>`).join('');
  return `<article class="card inputs-card"><div class="k">${logistical?'Contexto logístico':'Referencia indirecta de costo'}</div><h3>${esc(s.name)}</h3><div class="v">${num(s.value)}</div><div class="inputs-unit">${esc(s.unit)} · ${month(s.period)}</div><div class="inputs-changes">${changes}</div>${spark(s)}<div class="inputs-scope">${esc(s.scope)}</div><div class="source-note">${link(s.url,s.source)}${s.series_id?' · '+esc(s.series_id):''}<br>Verificado: ${checked(s.verified_at)} (RD)${health?.ok===false?'<br><span class="inputs-stale">Consulta incompleta; se conserva el dato anterior.</span>':''}${old(s)?'<br><span class="inputs-stale">Dato con más de 120 días; revisar vigencia.</span>':''}</div></article>`;
 }
 function previousMonth(p){const [y,m]=p.split('-').map(Number);return `${m===1?y-1:y}-${String(m===1?12:m-1).padStart(2,'0')}`;}
 function renderWatch(){
  const watches=[];
  for(const key of Object.keys(expected)){
   const s=data.series?.[key];if(!s||old(s)||data.source_health?.[key]?.ok===false)continue;
   if(key==='gscpi'){
    if(s.value>=1)watches.push(`<article class="watch ${s.value>=2?'red':'yellow'}"><h3>Mayor presión logística</h3><p>GSCPI ${num(s.value)} · ${month(s.period)}. Revisar noticias de rutas y plazos internacionales; no confirma faltantes de materiales.</p></article>`);
    continue;
   }
   const c=s.changes||{},red=c.mom>=10||c.qoq>=20||c.yoy>=30,yellow=c.mom>=5||c.qoq>=10||c.yoy>=20;
   if(yellow)watches.push(`<article class="watch ${red?'red':'yellow'}"><h3>${esc(s.name)} · presión de costos</h3><p>1 mes: ${pct(c.mom)} · 3 meses: ${pct(c.qoq)} · 12 meses: ${pct(c.yoy)}. ${month(s.period)}. Señal para revisar referencias de mercado; no predice el ajuste del material farmacéutico.</p></article>`);
  }
  const affected=data.fda?.items?.filter(x=>x.count>0)||[];
  if(affected.length&&data.source_health?.fda?.ok===true)watches.push(`<article class="watch yellow"><h3>FDA · medicamentos terminados</h3><p>${affected.length} familias del catálogo tienen presentaciones en faltante vigente en EE. UU. Base FDA: ${esc(data.fda.last_updated)}. Ver detalle por molécula; no confirma escasez del API.</p></article>`);
  const failed=Object.entries(data.source_health||{}).filter(([,v])=>!v.ok).map(([k])=>k==='fda'?'FDA':expected[k]||k);
  if(failed.length)watches.push(`<article class="watch inputs-neutral"><h3>Cobertura incompleta</h3><p>No se verificó: ${esc(failed.join(', '))}. Los registros anteriores mantienen su fecha.</p></article>`);
  if(!watches.length)watches.push('<article class="watch inputs-neutral"><h3>Sin alertas numéricas activadas</h3><p>Las referencias verificadas no activan los umbrales orientativos. Esto no confirma disponibilidad ni estabilidad de precios de cada sustancia.</p></article>');
  el('inputsWatch').innerHTML=watches.join('');
 }
 function renderCatalogue(){
  const type=el('inputsType').value,q=el('inputsSearch').value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase();
  let entries=[...(data.catalogue?.actives||[]).map(x=>({...x,type:'api'})),...(data.catalogue?.excipients||[]).map(x=>({...x,type:'excipiente'}))];
  entries=entries.filter(x=>(type==='all'||x.type===type)&&x.name.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name,'es'));
  const verifiedFDA=data.source_health?.fda?.ok===true;
  el('inputsCatalogueBody').innerHTML=entries.map(x=>{
   const fda=x.type==='api'?data.fda?.items?.find(y=>y.name===x.name):null;
   const signal=x.signal?data.series?.[x.signal]:null;
   const price=signal?`${esc(signal.name)}: ${num(signal.value)}<br><span class="source-note">${esc(signal.unit)} · ${month(signal.period)}<br>Referencia indirecta${old(signal)||data.source_health?.[x.signal]?.ok===false?' · revisar vigencia':''}</span>`:'Sin serie pública comparable integrada';
   let availability=x.type==='excipiente'?'Sin medición pública específica integrada':!fda?'Consulta FDA pendiente':fda.count?`<span class="inputs-count">${fda.count} presentaciones con estado Current en FDA</span>`:'Sin coincidencias en faltantes vigentes FDA';
   if(x.type==='api')availability+=`<div class="source-note">Medicamento terminado · EE. UU.${!verifiedFDA?' · consulta incompleta; último registro':''}</div>`;
   const detail=fda?.count?`<details><summary>Ver registros públicos FDA</summary><ul>${fda.presentations.map(p=>`<li><strong>${esc(p.presentation||p.generic_name)}</strong><br>${esc(p.company_name)}<br>Disponibilidad reportada: ${esc(p.availability||'No especificada')}<br>Motivo: ${esc(p.shortage_reason||'No especificado')}<br>Actualización del registro: ${esc(p.update_date||'No indicada')}</li>`).join('')}</ul></details>`:'';
   return `<tr><td>${esc(x.name)}<br><span class="inputs-label">${x.type==='api'?'Principio activo':'Excipiente'}</span></td><td>${price}</td><td>${availability}${detail}</td><td>${esc(x.note||'Comparar sustancia, sal, pureza, mercado, fecha y condiciones antes de interpretar referencias de precios.')}</td></tr>`;
  }).join('')||'<tr><td colspan="4">No hay materiales que coincidan con la búsqueda.</td></tr>';
  el('inputsCatalogueCount').textContent=`${entries.length} sustancias · Catálogo genérico en orden alfabético. Los faltantes FDA no cubren todos los mercados ni todos los APIs; una ausencia de coincidencias no demuestra disponibilidad.`;
 }
 el('inputsType').addEventListener('change',()=>{if(data)renderCatalogue()});
 el('inputsSearch').addEventListener('input',()=>{if(data)renderCatalogue()});
 fetch('data/inputs.json?ts='+Date.now()).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(d=>{
  data=d;el('inputsCards').innerHTML=Object.keys(expected).map(card).join('');renderWatch();renderCatalogue();
  el('inputsStatus').textContent=`Consulta automática: ${checked(d.checked_at)} (RD). Cada tarjeta conserva el período publicado y la última verificación exitosa.`;
  el('inputsFDAStatus').textContent=d.fda?`FDA · Base actualizada: ${d.fda.last_updated} · Verificada: ${checked(d.fda.verified_at)} (RD). ${d.source_health?.fda?.ok===false?'No se pudo renovar la consulta; se conserva el registro anterior.':''}`:'FDA: sin una consulta completa validada; no se infiere ausencia de faltantes.';
 }).catch(()=>{el('inputsStatus').textContent='No se pudieron cargar las señales externas. Intenta recargar. No se infiere disponibilidad a partir de este fallo.';el('inputsCatalogueBody').innerHTML='<tr><td colspan="4">Datos no disponibles.</td></tr>';});
})();
