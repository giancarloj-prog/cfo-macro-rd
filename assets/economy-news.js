(()=>{
 'use strict';
 const el=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fold=v=>String(v).normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase();
 const safe=url=>{try{const u=new URL(url);return u.protocol==='https:'?u.href:'#'}catch{return '#'}};
 const day=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santo_Domingo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).filter(x=>['year','month','day'].includes(x.type)).reduce((a,x)=>({...a,[x.type]:x.value}),{});
 const today=()=>{const d=day();return `${d.year}-${d.month}-${d.day}`};
 const time=v=>new Date(v).toLocaleTimeString('es-DO',{timeZone:'America/Santo_Domingo',hour:'2-digit',minute:'2-digit'});
 let data=null;
 function render(){
  if(!data)return;
  const list=el('economyList'),status=el('economyStatus');
  if(data.date!==today()){
   list.innerHTML='<div class="empty">Pendiente la actualización de hoy. Las publicaciones de días anteriores se han ocultado.</div>';
   status.textContent='Solo noticias del día · hora dominicana';return;
  }
  const topic=el('economyTopic').value,who=el('economyEconomist').value,q=fold(el('economySearch').value);
  const items=(data.items||[]).filter(x=>(topic==='all'||x.topics?.includes(topic))&&(who==='all'||x.economists?.includes(who))&&fold(x.title+' '+x.publisher+' '+(x.economists||[]).map(k=>data.economists[k]).join(' ')).includes(q));
  const failures=Object.values(data.source_health||{}).filter(x=>!x.ok).length;
  status.textContent=`${data.date} · ${items.length} publicaciones · Última búsqueda: ${time(data.checked_at)} (RD)${failures?' · Cobertura incompleta: '+failures+' búsquedas pendientes':''}`;
  list.innerHTML=items.map(x=>`<article class="card news-card"><div class="k">${esc(x.publisher)} · ${time(x.published_at)} RD</div><h3><a href="${esc(safe(x.url))}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a></h3><div class="news-tags">${(x.topics||[]).map(k=>`<span>${esc(data.topics[k]||k)}</span>`).join('')}${(x.economists||[]).map(k=>`<span>${esc(data.economists[k]||k)}</span>`).join('')}</div>${x.economist_match==='search'?'<p class="source-note">Coincidencia por búsqueda de nombre; no confirma autoría.</p>':''}</article>`).join('')||`<div class="empty">${failures?'La búsqueda está incompleta. No hay publicaciones disponibles con estos filtros.':'No se encontraron publicaciones de hoy con estos filtros.'}</div>`;
 }
 async function load(){
  try{
   const r=await fetch('data/economy_news.json?ts='+Date.now());if(!r.ok)throw Error(r.status);const next=await r.json();
   if(!Array.isArray(next.items)||!next.topics||!next.economists)throw Error('Formato inválido');data=next;
   for(const [id,options,label] of [['economyTopic',data.topics,'Todos los temas'],['economyEconomist',data.economists,'Todos']]){
    const select=el(id),value=select.value;select.innerHTML=`<option value="all">${label}</option>`+Object.entries(options).map(([k,v])=>`<option value="${esc(k)}">${esc(v)}</option>`).join('');select.value=Object.hasOwn(options,value)?value:'all';
   }
   render();
  }catch{render();el('economyStatus').textContent='No se pudo renovar la consulta de noticias económicas. Intenta recargar.';}
 }
 for(const id of ['economyTopic','economyEconomist'])el(id).addEventListener('change',render);
 el('economySearch').addEventListener('input',render);
 load();setInterval(load,300000);setInterval(render,30000);
})();
