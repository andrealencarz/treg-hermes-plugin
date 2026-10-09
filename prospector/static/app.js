let csrf = "";
let leadPage = 1;
let leadTotal = 0;
let currentLeads = [];
let campaigns = [];
const $ = id => document.getElementById(id);
const moneyFormat = new Intl.NumberFormat("pt-BR", {minimumFractionDigits:2, maximumFractionDigits:6});
const money = micro => `US$ ${moneyFormat.format((Number(micro) || 0) / 1000000)}`;
const whatsappUrl = phone => {
  const raw = String(phone || "").trim();
  const digits = raw.replace(/\D/g, "");
  const number = digits.length === 10 || digits.length === 11 ? "55" + digits : digits;
  return (number.startsWith("55") && (number.length === 12 || number.length === 13)) ||
    (raw.startsWith("+") && number.length >= 8 && number.length <= 15)
    ? `https://wa.me/${number}` : null;
};
const emailUrl = email => {
  const address = String(email || "").trim();
  return /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(address)
    ? `mailto:${encodeURIComponent(address)}` : null;
};
const siteTypeLabels = {website:"Site",links:"Página de links",possible_links:"Possível agregador de links",
  delivery:"Delivery",marketplace:"Marketplace",social:"Rede social",messaging:"Mensagens",unknown:"Tipo desconhecido"};
const auditLabel = audit => {
  if (!audit) return "Ainda não analisado";
  const access={online:"No ar",offline:"Fora do ar",blocked:"Acesso bloqueado",error:"Erro de acesso",unsafe:"Endereço não público"}[audit.availability]||"Não avaliado";
  const seo=audit.seo_score==null?"":` · SEO ${audit.seo_score}/100${audit.seo_score<60?" (atenção)":""}`;
  return `${access} · ${audit.provider||siteTypeLabels[audit.page_type]||audit.page_type}${seo}`;
};
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const sourceNames = {google_maps:"Google Maps",instagram:"Instagram",linkedin:"LinkedIn"};
const sourceChecks = c => Object.entries(sourceNames).map(([id,label])=>`<label><input type="checkbox" name="sources" value="${id}" ${(c.sources||["google_maps"]).includes(id)?"checked":""}> ${label}</label>`).join("");
const date = value => value ? new Date(value).toLocaleString("pt-BR") : "—";

async function api(url, options={}) {
  const response = await fetch(url, {credentials:"same-origin", ...options,
    headers:{"Content-Type":"application/json", ...(options.method && options.method !== "GET" ? {"X-CSRF-Token":csrf}:{}), ...(options.headers||{})}});
  let body = {};
  try { body = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(body.detail || `Falha HTTP ${response.status}`);
  return body;
}

function notice(message, error=false) {
  const box = $("notice"); box.textContent=message; box.className=error?"notice error":"notice"; box.hidden=false;
  setTimeout(()=>box.hidden=true,6000);
}

async function init() {
  try { csrf=(await api("/api/session")).csrf; $("shell").hidden=false; $("login").hidden=true; await refresh(); }
  catch (_) { $("shell").hidden=true; $("login").hidden=false; }
}

function page() {
  const selected=["dashboard","campaigns","schedule","runs","settings"].includes(location.hash.slice(1))?location.hash.slice(1):"dashboard";
  document.querySelectorAll(".page").forEach(el=>el.hidden=el.id!==`page-${selected}`);
  document.querySelectorAll(".sidebar a").forEach(el=>el.classList.toggle("active",el.dataset.page===selected));
  $("page-title").textContent={dashboard:"Dashboard",campaigns:"Campanhas",schedule:"Programação",runs:"Execuções",settings:"Configurações"}[selected];
  if(selected==="runs") loadRuns();
  if(selected==="schedule") loadSchedules();
}

async function refresh() {
  const [status, list] = await Promise.all([api("/api/status"),api("/api/campaigns")]);
  campaigns=list;
  $("stat-leads").textContent=status.leads;
  $("stat-campaigns").textContent=status.campaigns;
  $("stat-queued").textContent=status.queued;
  $("stat-cost").textContent=money(status.global_used_micro);
  $("global-budget").textContent=`${money(status.global_used_micro)} de ${money(status.global_monthly_cap_micro)} em ${status.global_period}`;
  $("connection-pill").textContent=status.treg_configured?"Treg configurado":"Treg não configurado";
  $("treg-state").textContent=status.treg_configured?`Chave salva: ${status.treg_token_hint || "••••••••"}. Digite outra chave para substituí-la.`:"Nenhuma chave configurada.";
  $("treg-form").elements.token.placeholder=status.treg_token_hint || "";
  $("lead-campaign").innerHTML='<option value="">Todas as campanhas</option>'+list.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("");
  $("schedule-campaign").innerHTML='<option value="">Selecione</option>'+list.filter(c=>c.state!=="archived").map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("");
  renderCampaigns(); await loadLeads(); page();
}

function renderCampaigns() {
  $("campaign-list").innerHTML=campaigns.length?campaigns.map(c=>`<div class="campaign"><h3>${esc(c.name)}</h3><p>${esc(c.niche)} · ${c.cities.map(x=>esc(x.city)+"/"+esc(x.uf)).join(", ")}</p><p><span class="tag">${esc(c.state)}</span> &nbsp; Meta ${c.target_leads} · Teto ${money(c.run_cap_micro)} · Mensal ${money(c.monthly_cap_micro)}</p><form class="campaign-sources" data-sources="${esc(c.id)}"><strong>Fontes</strong>${sourceChecks(c)}<button type="submit" ${c.state==="archived"?"disabled":""}>Salvar fontes</button></form><div class="campaign-actions"><button class="primary" data-run="${esc(c.id)}">Buscar agora</button><button data-edit="${esc(c.id)}">Editar</button><button data-duplicate="${esc(c.id)}">Duplicar</button><button data-state="${esc(c.id)}" ${c.state==="archived"?"disabled":""}>${c.state==="paused"?"Retomar":"Pausar"}</button><button data-archive="${esc(c.id)}" ${c.state==="archived"?"disabled":""}>Arquivar</button></div></div>`).join(""):'<div class="empty">Nenhuma campanha. Crie a primeira ao lado.</div>';
  document.querySelectorAll("[data-sources]").forEach(form=>form.onsubmit=async event=>{event.preventDefault();try{await api(`/api/campaigns/${form.dataset.sources}`,{method:"PATCH",body:JSON.stringify({sources:new FormData(form).getAll("sources")})});notice("Fontes atualizadas. A rodada já enfileirada mantém as fontes anteriores.");await refresh()}catch(e){notice(e.message,true)}});
  document.querySelectorAll("[data-run]").forEach(button=>button.onclick=async()=>{
    const c=campaigns.find(x=>x.id===button.dataset.run);
    if(!confirm(`Buscar agora em ${c.name}? Limite de ${money(c.run_cap_micro)} por rodada.`)) return;
    try { const run=await api(`/api/campaigns/${encodeURIComponent(c.id)}/runs`,{method:"POST"}); notice(`Rodada ${run.id.slice(0,8)} enfileirada.`); location.hash="runs"; await loadRuns(); }
    catch(e){notice(e.message,true)}
  });
  document.querySelectorAll("[data-duplicate]").forEach(button=>button.onclick=async()=>{try{await api(`/api/campaigns/${button.dataset.duplicate}/duplicate`,{method:"POST"});notice("Campanha duplicada em rascunho.");await refresh()}catch(e){notice(e.message,true)}});
  document.querySelectorAll("[data-state]").forEach(button=>button.onclick=async()=>{const c=campaigns.find(x=>x.id===button.dataset.state);const state=c.state==="paused"?"draft":"paused";try{await api(`/api/campaigns/${c.id}/state`,{method:"PATCH",body:JSON.stringify({state})});await refresh()}catch(e){notice(e.message,true)}});
  document.querySelectorAll("[data-archive]").forEach(button=>button.onclick=async()=>{const c=campaigns.find(x=>x.id===button.dataset.archive);if(!confirm(`Arquivar ${c.name}? Os leads e o histórico serão preservados.`))return;try{await api(`/api/campaigns/${c.id}/state`,{method:"PATCH",body:JSON.stringify({state:"archived"})});await refresh()}catch(e){notice(e.message,true)}});
  document.querySelectorAll("[data-edit]").forEach(button=>button.onclick=async()=>{const c=campaigns.find(x=>x.id===button.dataset.edit);const name=prompt("Nome da campanha",c.name);if(name===null)return;const niche=prompt("Nicho",c.niche);if(niche===null)return;const cap=prompt("Teto por rodada (USD)",(c.run_cap_micro/1000000).toFixed(2));if(cap===null)return;try{await api(`/api/campaigns/${c.id}`,{method:"PATCH",body:JSON.stringify({name,niche,run_cap_micro:Math.round(Number(cap)*1000000)})});notice("Campanha atualizada. A rodada atual mantém a configuração anterior.");await refresh()}catch(e){notice(e.message,true)}});
}

function leadParams() {
  return new URLSearchParams({q:$("lead-search").value,campaign_id:$("lead-campaign").value,
    status:$("lead-status").value,sort:$("lead-sort").value,page:leadPage,size:$("lead-size").value});
}

async function loadLeads() {
  const params=leadParams();
  const result=await api(`/api/leads?${params}`); leadTotal=result.total; currentLeads=result.items;
  $("lead-analyze").disabled=!currentLeads.some(l=>l.website&&!l.site_audit);
  $("lead-rows").innerHTML=result.items.length?result.items.map(l=>{
    const wa=whatsappUrl(l.phone), mail=emailUrl(l.email);
    const links=[l.website?`<a href="${esc(l.website)}" rel="noopener noreferrer" target="_blank">Site</a>`:"",
      wa?`<a href="${esc(wa)}" rel="noopener noreferrer" target="_blank" aria-label="Abrir WhatsApp de ${esc(l.name)}">WhatsApp</a>`:"",
      mail?`<a href="${esc(mail)}" aria-label="Enviar e-mail para ${esc(l.name)}">E-mail</a>`:""].filter(Boolean).join(" ");
    const audit=l.website?`<div class="site-audit"><span>${esc(auditLabel(l.site_audit))}</span>${l.site_audit?`<small>Verificado: ${date(l.site_audit.checked_at)}</small>`:""}${l.site_audit?.issues?.length?`<details><summary>Detalhes da análise</summary><ul>${l.site_audit.issues.map(issue=>`<li>${esc(issue)}</li>`).join("")}</ul></details>`:""}<button data-site-audit="${esc(l.id)}">${l.site_audit?"Atualizar análise":"Analisar site"}</button></div>`:"";
    return `<tr><td><button class="link-button" data-lead="${esc(l.id)}">${esc(l.name)}</button><small>${esc(l.niche||"Nicho não informado")}</small></td><td>${esc(l.city||"—")}/${esc(l.uf||"—")}</td><td><div class="contact-actions">${links||"—"}</div>${l.phone?`<small>${esc(l.phone)}</small>`:""}${l.email?`<small>${esc(l.email)}</small>`:""}${audit}</td><td><select data-lead-status="${esc(l.id)}">${["Novo","Em análise","Contatado","Proposta enviada","Fechado"].map(s=>`<option ${s===l.status?"selected":""}>${s}</option>`).join("")}</select></td><td>${date(l.last_seen_at)}</td></tr>`;
  }).join(""):'<tr><td colspan="5" class="empty">Nenhum lead encontrado. Ajuste os filtros ou faça a primeira busca.</td></tr>';
  document.querySelectorAll("[data-lead]").forEach(button=>button.onclick=async()=>{try{const l=await api(`/api/leads/${button.dataset.lead}`);alert(`${l.name}\n${l.city}/${l.uf}\nTelefone: ${l.phone||"não informado"}\nE-mail: ${l.email||"não informado"}\nFontes: ${l.sources.map(s=>`${s.source}: ${s.evidence_url||s.external_id}`).join("; ")}`)}catch(e){notice(e.message,true)}});
  document.querySelectorAll("[data-lead-status]").forEach(select=>select.onchange=async()=>{try{await api(`/api/leads/${select.dataset.leadStatus}/status`,{method:"PATCH",body:JSON.stringify({status:select.value})});notice("Status atualizado.")}catch(e){notice(e.message,true)}});
  document.querySelectorAll("[data-site-audit]").forEach(button=>button.onclick=async()=>{button.disabled=true;try{await api(`/api/leads/${encodeURIComponent(button.dataset.siteAudit)}/analyze-site`,{method:"POST"});notice("Análise do site atualizada.");await loadLeads()}catch(e){notice(e.message,true);button.disabled=false}});
  const first=leadTotal?(leadPage-1)*result.size+1:0, last=Math.min(leadPage*result.size,leadTotal);
  $("lead-range").textContent=`${first}–${last} de ${leadTotal}`;
  $("lead-prev").disabled=leadPage<=1; $("lead-next").disabled=last>=leadTotal;
  history.replaceState(null,"",location.pathname+"?"+params.toString()+location.hash);
}

async function loadRuns() {
  try { const runs=await api("/api/runs"); $("run-list").innerHTML=runs.length?runs.map(r=>`<div class="run"><h3>${esc(campaigns.find(c=>c.id===r.campaign_id)?.name||"Campanha")}</h3><p><span class="tag">${esc(r.state)}</span> &nbsp; ${date(r.created_at)} · ${r.new_campaign} novos na campanha · ${money(r.cost_micro)} ${r.financial_state==="pending"?"(custo pendente)":""}</p>${r.error?`<p class="error">${esc(r.error)}</p>`:""}</div>`).join(""):'<div class="empty">Nenhuma execução ainda.</div>'; }
  catch(e){notice(e.message,true)}
}

async function loadSchedules() {
  try { const list=await api("/api/schedules"); $("schedule-list").innerHTML=list.length?list.map(s=>`<div class="run"><h3>${esc(campaigns.find(c=>c.id===s.campaign_id)?.name||"Campanha")}</h3><p><span class="tag">${esc(s.state)}</span> · ${esc(s.timezone)} · ${s.frequency==="once"?"Uma vez":s.frequency==="daily"?"Todos os dias":"Dias da semana"}</p><p>Próximas: ${s.next_occurrences.length?s.next_occurrences.map(date).join(" · "):"Nenhuma"}</p><div class="button-row"><button data-schedule-action="activate" data-schedule-id="${esc(s.campaign_id)}" ${s.state==="active"?"disabled":""}>Ativar/Retomar</button><button data-schedule-action="pause" data-schedule-id="${esc(s.campaign_id)}" ${s.state!=="active"?"disabled":""}>Pausar</button></div></div>`).join(""):'<div class="empty">Nenhuma rotina programada. Salve uma programação ao lado.</div>';
    document.querySelectorAll("[data-schedule-action]").forEach(button=>button.onclick=async()=>{try{await api(`/api/schedules/${button.dataset.scheduleId}/${button.dataset.scheduleAction}`,{method:"POST"});notice("Rotina atualizada no Hermes.");await loadSchedules();await refresh()}catch(e){notice(e.message,true)}});
  }catch(e){$("schedule-list").innerHTML=`<p class="error">${esc(e.message)}</p>`}
}

function schedulePayload() {
  const form=new FormData($("schedule-form"));
  return {campaign_id:form.get("campaign_id"), frequency:form.get("frequency"),
    times:String(form.get("times")||"").split(",").map(x=>x.trim()).filter(Boolean),
    days:[...$("schedule-form").elements.days.selectedOptions].map(x=>Number(x.value)),
    once_at:form.get("once_at")||null,timezone:form.get("timezone")};
}

function scheduleFields() {
  const frequency=$("schedule-frequency").value;
  $("schedule-times-wrap").hidden=frequency==="once";
  $("schedule-days-wrap").hidden=frequency!=="weekdays";
  $("schedule-once-wrap").hidden=frequency!=="once";
}

$("login-form").addEventListener("submit",async event=>{event.preventDefault(); try {csrf=(await api("/api/login",{method:"POST",body:JSON.stringify({password:$("password").value})})).csrf;$("password").value="";$("login-error").textContent="";await init();} catch(e){$("login-error").textContent=e.message}});
$("logout").onclick=async()=>{try{await api("/api/logout",{method:"POST"})}finally{csrf="";await init()}};
$("campaign-form").addEventListener("submit",async event=>{event.preventDefault();const form=new FormData(event.target);try{const cities=String(form.get("cities")).split("\n").filter(x=>x.trim()).map(line=>{const [city,uf]=line.split(",");return {city:city?.trim(),uf:uf?.trim()}});await api("/api/campaigns",{method:"POST",body:JSON.stringify({name:form.get("name"),niche:form.get("niche"),service:form.get("service"),cities,sources:form.getAll("sources"),target_leads:Number(form.get("target")),run_cap_micro:Math.round(Number(form.get("cap"))*1000000),monthly_cap_micro:Math.round(Number(form.get("monthly"))*1000000)})});event.target.reset();$("campaign-error").textContent="";notice("Campanha criada em rascunho.");await refresh()}catch(e){$("campaign-error").textContent=e.message}});
$("treg-form").addEventListener("submit",async event=>{event.preventDefault();try{const form=new FormData(event.target);await api("/api/settings/treg",{method:"PUT",body:JSON.stringify({token:form.get("token"),org:form.get("org")||null})});event.target.reset();$("treg-error").textContent="";notice("Chave validada e salva.");await refresh()}catch(e){$("treg-error").textContent=e.message}});
$("test-token").onclick=async()=>{try{const form=new FormData($("treg-form"));await api("/api/settings/treg/test",{method:"POST",body:JSON.stringify({token:form.get("token"),org:form.get("org")||null})});notice("Conexão Treg validada.")}catch(e){$("treg-error").textContent=e.message}};
$("budget-form").addEventListener("submit",async event=>{event.preventDefault();try{const form=new FormData(event.target);await api("/api/settings/budget",{method:"PUT",body:JSON.stringify({global_monthly_cap_micro:Math.round(Number(form.get("cap"))*1000000),timezone:form.get("timezone")})});notice("Orçamento global atualizado.");await refresh()}catch(e){notice(e.message,true)}});
$("refresh-runs").onclick=loadRuns;
$("reconcile-runs").onclick=async()=>{try{const result=await api("/api/runs/reconcile",{method:"POST"});notice(result.length?`${result.length} chamada(s) verificadas no ledger Treg.`:"Não há cobranças pendentes.");await loadRuns();await refresh()}catch(e){notice(e.message,true)}};
$("schedule-frequency").onchange=scheduleFields;
$("preview-schedule").onclick=async()=>{const payload=schedulePayload();if(!payload.campaign_id){$("schedule-error").textContent="Selecione uma campanha";return}try{const value=await api(`/api/schedules/${payload.campaign_id}/preview`,{method:"POST",body:JSON.stringify(payload)});$("schedule-preview").textContent=value.next_occurrences.length?"Próximas: "+value.next_occurrences.map(date).join(" · "):"Nenhuma ocorrência futura";$("schedule-error").textContent=""}catch(e){$("schedule-error").textContent=e.message}};
$("schedule-form").addEventListener("submit",async event=>{event.preventDefault();const payload=schedulePayload();try{await api(`/api/schedules/${payload.campaign_id}`,{method:"PUT",body:JSON.stringify(payload)});$("schedule-error").textContent="";notice("Programação salva em pausa. Ative quando quiser iniciar a rotina.");await loadSchedules()}catch(e){$("schedule-error").textContent=e.message}});
$("lead-prev").onclick=()=>{leadPage--;loadLeads()};$("lead-next").onclick=()=>{leadPage++;loadLeads()};
for(const id of ["lead-search","lead-campaign","lead-status","lead-sort","lead-size"])$(id).addEventListener("input",()=>{leadPage=1;loadLeads()});
$("lead-export").onclick=()=>{const params=leadParams();params.delete("page");params.delete("size");location.href=`/api/leads/export.csv?${params}`};
$("lead-analyze").onclick=async()=>{
  const targets=currentLeads.filter(l=>l.website&&!l.site_audit).slice(0,20);
  if(!targets.length)return;
  $("lead-analyze").disabled=true;
  let next=0, failures=0;
  async function worker(){while(next<targets.length){const lead=targets[next++];try{await api(`/api/leads/${encodeURIComponent(lead.id)}/analyze-site`,{method:"POST"})}catch(_){failures++}}}
  await Promise.all(Array.from({length:Math.min(3,targets.length)},worker));
  notice(`${targets.length-failures} site(s) analisado(s).${failures?` ${failures} falharam.`:""}`,Boolean(failures));
  await loadLeads();
};
window.addEventListener("hashchange",page);
$("today").textContent=new Date().toLocaleDateString("pt-BR",{day:"numeric",month:"long",year:"numeric"});
init();
setInterval(()=>{if(!$("shell").hidden && location.hash==="#runs")loadRuns()},5000);
