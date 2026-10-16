(()=>{
 const el=id=>document.getElementById(id);
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const fmt=v=>Number.isFinite(v)?`${v>0?'+':''}${v.toFixed(1)}%`:'—';
 const qlabel=p=>`T${p.slice(-1)} ${p.slice(0,4)}`;
 const names={'Producto Interno Bruto':'PIB total','Manufactura Zonas Francas':'Manufactura de zonas francas','Intermediación Financiera, Seguros y Actividades Conexas':'Servicios financieros','Administración Pública y Defensa; Seguridad Social de Afiliación Obligatoria y Otros Servicios':'Administración pública y defensa','Fabricación de Productos de la Refinación de Petróleo y Quimicos':'Refinación de petróleo y químicos'};
 const label=s=>names[s.name]||s.name;
 const dateSpan=periods=>{const a=periods[0],b=periods[periods.length-1],m=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];return `${m[(Number(a.slice(-1))-1)*3]} ${a.slice(0,4)} – ${m[Number(b.slice(-1))*3-1]} ${b.slice(0,4)}`};
 let data=null,selected='construccion';
 function draw(){
  if(!data?.series?.length)return;
  const s=data.series.find(x=>x.id===selected)||data.series[0];selected=s.id;
  el('gdpActivity').value=selected;
  const periods=data.periods,rates=periods.map(p=>s.yoy[p]);
  el('gdpTitle').textContent=label(s);
  el('gdpAnnual').textContent=fmt(s.rolling_12m_yoy);
  el('gdpAnnualPeriod').textContent=dateSpan(data.rolling_periods);
  el('gdpYtd').textContent=fmt(s.ytd_yoy);
  const through=data.ytd_period.through_quarter,year=data.ytd_period.year;
  el('gdpYtdPeriod').textContent=`Ene–${['mar','jun','sep','dic'][through-1]} ${year} vs. igual período de ${year-1}`;
  const rows=data.series.filter(x=>x.principal||x.id===selected);
  el('gdpTableHead').innerHTML='<tr><th>Actividad</th>'+periods.map(p=>`<th>${qlabel(p)}<br><span>YoY</span></th>`).join('')+'<th>12 meses<br><span>YoY</span></th></tr>';
  el('gdpTableBody').innerHTML=rows.map(x=>`<tr${x.id===selected?' class="gdp-selected"':''}><td><button type="button" data-gdp-sector="${esc(x.id)}" aria-label="Ver ${esc(x.name)}" title="${esc(x.name)}">${esc(label(x))}</button></td>${[...periods.map(p=>x.yoy[p]),x.rolling_12m_yoy].map((v,i)=>`<td class="${v<0?'gdp-negative':''}${i===periods.length-1?' gdp-latest':''}">${fmt(v)}</td>`).join('')}</tr>`).join('');
  el('gdpTableBody').querySelectorAll('[data-gdp-sector]').forEach(b=>b.addEventListener('click',()=>{selected=b.dataset.gdpSector;draw()}));
  const host=el('gdpChart'),W=host.clientWidth;
  if(W<200)return;
  const H=255,L=48,R=12,T=30,B=40,low=Math.floor(Math.min(0,...rates)-1),high=Math.ceil(Math.max(0,...rates)+1.5);
  const y=v=>T+(H-T-B)*(high-v)/(high-low),step=(W-L-R)/periods.length,bw=Math.min(68,step*.52),zero=y(0);
  const ticks=[low,...(low<0&&high>0?[0]:[]),high];
  let chart=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(s.name)}. Crecimiento real interanual: ${esc(rates.map((v,i)=>qlabel(periods[i])+': '+fmt(v)).join('; '))}"><text x="0" y="15" class="gdp-axis">YoY (%)</text>`;
  ticks.forEach(v=>{chart+=`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" class="gdp-gridline"/><text x="${L-9}" y="${y(v)+4}" text-anchor="end" class="gdp-axis">${v}</text>`});
  rates.forEach((v,i)=>{const x=L+step*(i+.5);chart+=`<rect x="${x-bw/2}" y="${Math.min(y(v),zero)}" width="${bw}" height="${Math.max(0,Math.abs(y(v)-zero))}" class="${v<0?'gdp-bar-negative':'gdp-bar'}"><title>${esc(qlabel(periods[i]))}: ${fmt(v)}</title></rect><text x="${x}" y="${v>=0?y(v)-9:y(v)+19}" text-anchor="middle" class="gdp-value">${fmt(v)}</text><text x="${x}" y="${H-12}" text-anchor="middle" class="gdp-axis">${qlabel(periods[i])}</text>`});
  host.innerHTML=chart+'</svg>';
 }
 el('gdpActivity').addEventListener('change',e=>{selected=e.target.value;draw()});
 new ResizeObserver(draw).observe(el('gdpChart'));
 fetch('data/gdp.json?ts='+Date.now()).then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(d=>{
  data=d;
  if(!d.series?.length||d.periods?.length!==4){el('gdpStatus').textContent='Todavía no hay una publicación trimestral validada disponible.';return;}
  const principal=d.series.filter(x=>x.principal),details=d.series.filter(x=>!x.principal);
  const options=xs=>xs.map(x=>`<option value="${esc(x.id)}">${esc(label(x))}</option>`).join('');
  el('gdpActivity').innerHTML=`<optgroup label="Actividades principales">${options(principal)}</optgroup><optgroup label="Desgloses">${options(details)}</optgroup>`;
  el('gdpPeriods').textContent=`${qlabel(d.periods[0])} – ${qlabel(d.latest_period)} · Crecimiento real interanual${d.preliminary?' · Cifras preliminares':''}`;
  const time=d.verified_at?new Date(d.verified_at).toLocaleString('es-DO',{timeZone:'America/Santo_Domingo'}):'pendiente';
  el('gdpStatus').textContent=`Último trimestre publicado: ${qlabel(d.latest_period)} · Última verificación: ${time} (RD)${d.source_health?.ok===false?' · No se pudo verificar la fuente. Se conserva la última publicación validada.':''}`;
  el('gdpSource').href=d.source_url;
  draw();
 }).catch(()=>{el('gdpStatus').textContent='No se pudieron cargar los datos trimestrales. Intenta recargar.'});
})();
