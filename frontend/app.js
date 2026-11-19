let datasetId=null, currentProfile=null, selectedActions=new Set(), charts=[];
const $=id=>document.getElementById(id);
$('upload-new').onclick=()=>{$('file').value='';$('file').click()};
async function api(path,body){const r=await fetch('/api'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Request failed');return d}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function table(el,rows){if(!rows?.length){el.innerHTML='<tr><td>No data</td></tr>';return}let cols=Object.keys(rows[0]);el.innerHTML='<thead><tr>'+cols.map(c=>`<th>${esc(c)}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>`<td>${esc(r[c])}</td>`).join('')+'</tr>').join('')+'</tbody>'}
function renderProfile(p){currentProfile=p;$('kpis').innerHTML=[['Rows',p.rows.toLocaleString()],['Columns',p.columns_count],['Missing cells',p.missing_cells.toLocaleString()],['Duplicate rows',p.duplicate_rows.toLocaleString()]].map(x=>`<div class="kpi"><small>${x[0]}</small><strong>${x[1]}</strong></div>`).join('');
$('profile-table').innerHTML='<thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Missing %</th><th>Unique</th><th>Sample values</th></tr></thead><tbody>'+p.columns.map(c=>`<tr><td>${esc(c.name)}</td><td>${esc(c.dtype)}</td><td>${c.missing}</td><td>${c.missing_pct}%</td><td>${c.unique}</td><td>${esc((c.sample||[]).join(', '))}</td></tr>`).join('')+'</tbody>'}
function showTab(tab){document.querySelectorAll('.tab-panel').forEach(x=>x.hidden=x.id!==tab);document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.tab===tab))}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
$('upload-new').onclick=()=>{$('file').click()};
$('file').onchange=async e=>{
 const f=e.target.files[0]; if(!f)return;
 $('upload-status').textContent='Uploading and profiling…'; $('upload-new').disabled=true;
 try{
  const fd=new FormData();fd.append('file',f);
  const r=await fetch('/api/upload',{method:'POST',body:fd});const d=await r.json();
  if(!r.ok)throw new Error(d.detail||'Upload failed');
  datasetId=d.dataset_id;$('filename').textContent=d.filename;renderProfile(d.profile);table($('preview-table'),d.preview);
  $('workspace').hidden=false;$('upload-panel').hidden=true;$('upload-new').hidden=false;$('export').disabled=false;
  $('upload-status').textContent='Upload complete';selectedActions.clear();showTab('overview');await scan();
 }catch(err){$('upload-status').textContent=err.message;alert(err.message)}
 finally{$('file').value='';$('upload-new').disabled=false}
};
async function scan(){if(!datasetId)return;const d=await api('/clean/preview',{dataset_id:datasetId});selectedActions.clear();$('suggestions').innerHTML=d.suggestions.length?d.suggestions.map(s=>`<label class="suggestion"><input type="checkbox" data-action="${esc(s.id)}"><span><b>${esc(s.issue)} <span class="pill">${s.count}</span></b><small>${esc(s.column)} — ${esc(s.recommendation)}</small></span></label>`).join(''):'<p>No common data quality issues detected by this scan.</p>';document.querySelectorAll('[data-action]').forEach(x=>x.onchange=()=>{x.checked?selectedActions.add(x.dataset.action):selectedActions.delete(x.dataset.action);$('apply').disabled=!selectedActions.size});$('apply').disabled=true}
$('scan').onclick=()=>scan().catch(e=>$('clean-status').textContent=e.message);
$('apply').onclick=async()=>{try{const d=await api('/clean/apply',{dataset_id:datasetId,actions:[...selectedActions]});renderProfile(d.profile);table($('preview-table'),d.preview);$('clean-status').textContent=`Applied ${d.applied.length} selected operation(s). Original columns were retained.`;await scan()}catch(e){$('clean-status').textContent=e.message}};
$('analyze').onclick=async()=>{try{const d=await api('/analyze',{dataset_id:datasetId});charts.forEach(c=>c.destroy());charts=[];let html='';d.distributions.forEach((x,i)=>html+=`<div class="panel chart-box"><h3>${esc(x.column)} · Distribution</h3><canvas id="dist${i}"></canvas></div>`);d.categories.forEach((x,i)=>html+=`<div class="panel chart-box"><h3>${esc(x.column)} · Top categories</h3><canvas id="cat${i}"></canvas></div>`);if(d.correlations.matrix.length)html+=`<div class="panel chart-box"><h3>Correlation matrix</h3><div class="table-wrap"><table><thead><tr><th>Column</th>${d.correlations.labels.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${d.correlations.matrix.map((row,i)=>`<tr><th>${esc(d.correlations.labels[i])}</th>${row.map(v=>`<td>${v??'—'}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`;$('charts').innerHTML=html||'<div class="panel">Not enough numeric or categorical data to chart.</div>';d.distributions.forEach((x,i)=>charts.push(new Chart($(`dist${i}`),{type:'bar',data:{labels:x.labels,datasets:[{label:x.column,data:x.values}]},options:{responsive:true,plugins:{legend:{display:false}}}})));d.categories.forEach((x,i)=>charts.push(new Chart($(`cat${i}`),{type:'bar',data:{labels:x.labels,datasets:[{label:x.column,data:x.values}]},options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}}}})))}catch(e){$('charts').textContent=e.message}};
$('get-insights').onclick=async()=>{try{const d=await api('/insights',{dataset_id:datasetId});$('insight-list').innerHTML=d.insights.map((x,i)=>`<div class="suggestion"><span class="pill">${i+1}</span><span>${esc(x)}</span></div>`).join('')}catch(e){$('insight-list').textContent=e.message}};
$('export').onclick=()=>{if(datasetId)fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:datasetId})}).then(r=>r.blob()).then(b=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='analysis_dataset.csv';a.click();URL.revokeObjectURL(a.href)})};
