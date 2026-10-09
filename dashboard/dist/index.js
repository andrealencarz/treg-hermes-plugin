(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  const React = SDK.React;
  const h = React.createElement;
  const {useState, useEffect, useCallback} = SDK.hooks;
  const API = "/api/plugins/hermes-prospector";
  const ABOUT = {
    developer: "André Alencar",
    website: "https://www.aalencar.com.br",
    instagram: "https://www.instagram.com/empreendedorserialbr/",
    instagramLabel: "@empreendedorserialbr",
    youtube: "https://www.youtube.com/@empreendedorserial",
    youtubeLabel: "@empreendedorserial",
    email: "suporte@aalencar.com.br",
    whatsapp: "+55 86 9999-7003",
    whatsappUrl: "https://wa.me/558699997003",
  };
  const moneyFormat = new Intl.NumberFormat("pt-BR", {minimumFractionDigits:2, maximumFractionDigits:6});
  const money = n => "US$ " + moneyFormat.format((Number(n) || 0) / 1000000);
  const whatsappUrl = phone => {
    const raw = String(phone || "").trim();
    const digits = raw.replace(/\D/g, "");
    const number = digits.length === 10 || digits.length === 11 ? "55" + digits : digits;
    return (number.startsWith("55") && (number.length === 12 || number.length === 13)) ||
      (raw.startsWith("+") && number.length >= 8 && number.length <= 15)
      ? "https://wa.me/" + number : null;
  };
  const emailUrl = email => {
    const address = String(email || "").trim();
    return /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(address)
      ? "mailto:" + encodeURIComponent(address) : null;
  };
  const siteTypeLabels = {website:"Site",links:"Página de links",possible_links:"Possível agregador de links",
    delivery:"Delivery",marketplace:"Marketplace",social:"Rede social",messaging:"Mensagens",unknown:"Tipo desconhecido"};
  const auditLabel = audit => {
    if (!audit) return "Ainda não analisado";
    const access = {online:"No ar",offline:"Fora do ar",blocked:"Acesso bloqueado",error:"Erro de acesso",unsafe:"Endereço não público"}[audit.availability] || "Não avaliado";
    const kind = siteTypeLabels[audit.page_type] || audit.page_type;
    const seo = audit.seo_score == null ? "" : ` · SEO ${audit.seo_score}/100${audit.seo_score < 60 ? " (atenção)" : ""}`;
    return `${access} · ${audit.provider || kind}${seo}`;
  };
  const sourceOptions = [["google_maps","Google Maps"],["instagram","Instagram"],["linkedin","LinkedIn"]];
  const when = s => s ? new Date(s).toLocaleString("pt-BR") : "—";
  const item = (tag, props, ...children) => h(tag, props, ...children);
  const button = (label, onClick, props) => h("button", Object.assign({type:"button", onClick}, props || {}), label);
  const field = (label, name, options) => {
    const props = Object.assign({}, options || {});
    const tag = props.tag || "input";
    delete props.tag;
    return h("label", {className:"hp-field", key:name}, h("span", null, label),
      h(tag, Object.assign({name, ...(tag === "input" ? {type:"text"} : {})}, props)));
  };

  function request(path, method, body) {
    const options = method ? {method, headers:{"Content-Type":"application/json"}, body:body === undefined ? undefined : JSON.stringify(body)} : undefined;
    return SDK.fetchJSON(API + path, options);
  }

  function ProspectorPage() {
    const [page, setPage] = useState("dashboard");
    const [status, setStatus] = useState(null);
    const [campaigns, setCampaigns] = useState([]);
    const [runs, setRuns] = useState([]);
    const [schedules, setSchedules] = useState([]);
    const [leads, setLeads] = useState({items:[], total:0, page:1, size:20});
    const [filter, setFilter] = useState({q:"", campaign_id:"", status:"", source:""});
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");
    const [ready, setReady] = useState(false);
    const [busy, setBusy] = useState(false);
    const [editingId, setEditingId] = useState(null);

    const load = useCallback(async function (query) {
      const f = query || filter;
      const params = new URLSearchParams({q:f.q || "", campaign_id:f.campaign_id || "",
        status:f.status || "", source:f.source || "", page:String(f.page || 1), size:"20"});
      const [state, cs, rs, ss, ls] = await Promise.all([
        request("/status"), request("/campaigns"), request("/runs"),
        request("/schedules"), request("/leads?" + params.toString())]);
      setStatus(state); setCampaigns(cs); setRuns(rs); setSchedules(ss); setLeads(ls);
      setReady(true); setError("");
    }, [filter]);

    useEffect(function () {
      load().catch(e => {setError(String(e.message || e)); setReady(false);});
    }, []);

    async function change(action, success) {
      setBusy(true); setError(""); setMessage("");
      try { await action(); await load(); setMessage(success || "Salvo."); return true; }
      catch (e) { setError(String(e.message || e)); return false; }
      finally { setBusy(false); }
    }

    function campaignData(form) {
      const data = new FormData(form);
      const cities = String(data.get("cities") || "").split("\n").filter(line => line.trim()).map(line => {
        const parts = line.split(","); return {city:(parts[0] || "").trim(), uf:(parts[1] || "").trim()};
      });
      return {
        name:String(data.get("name") || ""), niche:String(data.get("niche") || ""), service:String(data.get("service") || ""),
        cities, sources:data.getAll("sources"), target_leads:Number(data.get("target")),
        run_cap_micro:Math.round(Number(data.get("cap"))*1000000),
        monthly_cap_micro:Math.round(Number(data.get("monthly"))*1000000),
      };
    }

    function createCampaign(event) {
      event.preventDefault();
      const form = event.currentTarget;
      change(() => request("/campaigns", "POST", campaignData(form)),
             "Campanha criada em rascunho.").then(ok => {if (ok) form.reset();});
    }

    function saveCampaign(event, campaignId) {
      event.preventDefault();
      const payload = campaignData(event.currentTarget);
      change(() => request("/campaigns/"+campaignId, "PATCH", payload),
             "Campanha atualizada. Rodadas já enfileiradas mantêm os dados anteriores.")
        .then(ok => {if (ok) setEditingId(null);});
    }

    function sourceChecks(active) {
      return h("div", {className:"hp-source-list"}, ...sourceOptions.map(([id,label]) =>
        h("label", {key:id,className:"hp-source"},
          h("input", {type:"checkbox",name:"sources",value:id,defaultChecked:active.includes(id)}),label)));
    }

    function saveToken(event) {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      change(() => request("/settings/treg", "PUT", {
        token:String(data.get("token") || ""), org:String(data.get("org") || "") || null,
      }), "Chave validada e salva no perfil Hermes.").then(ok => {if (ok) form.reset();});
    }

    function saveBudget(event) {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      change(() => request("/settings/budget", "PUT", {
        global_monthly_cap_micro:Math.round(Number(data.get("cap"))*1000000),
        timezone:String(data.get("timezone") || "America/Fortaleza"),
      }), "Teto global atualizado.");
    }

    function schedulePayload(form) {
      const data = new FormData(form);
      return {campaign_id:String(data.get("campaign_id") || ""),
        frequency:String(data.get("frequency") || "daily"),
        days:[...form.querySelectorAll("[name=days]:checked")].map(x => Number(x.value)),
        times:String(data.get("times") || "").split(",").map(x => x.trim()).filter(Boolean),
        timezone:String(data.get("timezone") || "America/Fortaleza"),
        once_at:String(data.get("once_at") || "") || null};
    }

    function saveSchedule(event) {
      event.preventDefault();
      const p = schedulePayload(event.currentTarget);
      change(() => request("/schedules/" + encodeURIComponent(p.campaign_id), "PUT", p),
             "Programação salva em pausa. Ative quando estiver pronto.");
    }

    async function exportCSV() {
      try {
        const params = new URLSearchParams({q:filter.q, campaign_id:filter.campaign_id, status:filter.status, source:filter.source});
        const response = await SDK.authedFetch(API + "/leads/export.csv?" + params.toString());
        if (!response.ok) throw new Error("Exportação falhou (HTTP " + response.status + ")");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href=url; a.download="leads.csv"; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (e) { setError(String(e.message || e)); }
    }

    async function analyzePage() {
      const targets = leads.items.filter(l => l.website && !l.site_audit);
      if (!targets.length) { setMessage("Não há sites pendentes nesta página."); return; }
      setBusy(true); setError("");
      let next = 0, completed = 0, failures = 0;
      async function worker() {
        while (next < targets.length) {
          const lead = targets[next++];
          try { await request("/leads/" + encodeURIComponent(lead.id) + "/analyze-site", "POST"); }
          catch (_) { failures++; }
          completed++;
          setMessage(`Analisando sites: ${completed} de ${targets.length}…`);
        }
      }
      try {
        await Promise.all(Array.from({length:Math.min(3,targets.length)},worker));
        await load();
        setMessage(`${completed-failures} site(s) analisado(s) nesta página.`);
        if (failures) setError(`${failures} análise(s) falharam. Tente novamente nos leads pendentes.`);
      } catch (e) { setError(String(e.message || e)); }
      finally { setBusy(false); }
    }

    const tabs = [["dashboard","Leads"],["campaigns","Campanhas"],["schedule","Programação"],
      ["runs","Execuções"],["settings","Configurações"],["about","Sobre"]];
    const nav = h("nav", {className:"hp-nav"}, ...tabs.map(([id,label]) =>
      button(label, () => setPage(id), {key:id, className:page === id ? "active" : ""})));

    if (!ready) return h("div", {id:"hp-root"},
      h("h1", null, "Hermes Prospector"),
      h("p", null, error ? "A API do painel ainda não está ativa no Hermes." : "Carregando painel…"),
      error && h("p", {className:"hp-error"}, error),
      error && h("p", null, "Após instalar pela tela de Plugins, reinicie o serviço Dashboard/serve do Hermes no painel da hospedagem e recarregue esta aba. O Hermes 0.21.5 monta a API dos plugins na inicialização."),
      button("Tentar novamente", () => load().catch(e => setError(String(e.message || e)))));

    return h("div", {id:"hp-root"},
      h("header", {className:"hp-header"}, h("div", null,
        h("small", null,"HERMES PROSPECTOR"), h("h1", null,"Prospecção de empresas")),
        h("span", {className:"hp-pill"}, status.treg_configured ? "Treg conectado" : "Treg não configurado")),
      nav,
      message && h("p", {className:"hp-message", role:"status"}, message),
      error && h("p", {className:"hp-error", role:"alert"}, error),
      page === "dashboard" && h("section", null,
        h("div", {className:"hp-stats"},
          h("article", null,h("span",null,"Leads"),h("strong",null,status.leads)),
          h("article", null,h("span",null,"Campanhas"),h("strong",null,status.campaigns)),
          h("article", null,h("span",null,"Na fila"),h("strong",null,status.queued)),
          h("article", null,h("span",null,"Custo do mês"),h("strong",null,money(status.global_used_micro)))),
        h("div", {className:"hp-toolbar"},
          h("input", {placeholder:"Buscar nome, nicho ou contato", value:filter.q,
            onChange:e=>setFilter({...filter,q:e.target.value,page:1})}),
          h("select", {value:filter.campaign_id,onChange:e=>setFilter({...filter,campaign_id:e.target.value,page:1})},
            h("option",{value:""},"Todas as campanhas"),
            ...campaigns.map(c=>h("option",{key:c.id,value:c.id},c.name))),
          h("select",{value:filter.status,onChange:e=>setFilter({...filter,status:e.target.value,page:1})},
            ...["","Novo","Em análise","Contatado","Proposta enviada","Fechado"].map(s=>
              h("option",{key:s,value:s},s || "Todos os status"))),
          h("select",{value:filter.source,onChange:e=>setFilter({...filter,source:e.target.value,page:1})},
            h("option",{value:""},"Todas as fontes"),...sourceOptions.map(([id,label])=>h("option",{key:id,value:id},label))),
          button("Filtrar",()=>load({...filter,page:1}).catch(e=>setError(String(e.message||e)))),
          button("Analisar sites da página",analyzePage,{disabled:busy || !leads.items.some(l=>l.website && !l.site_audit)}),
          button("CSV",exportCSV)),
        h("div", {className:"hp-table-wrap"}, h("table",null,
          h("thead",null,h("tr",null,...["Empresa","Cidade/UF","Contato","Status","Coletado"].map(x=>h("th",{key:x},x)))),
          h("tbody",null,...(leads.items.length ? leads.items.map(l=>h("tr",{key:l.id},
            h("td",null,h("strong",null,l.name),h("small",null,l.niche || ""),
              h("small",null,(l.sources || []).map(s=>sourceOptions.find(x=>x[0]===s)?.[1] || s).join(" · "))),
            h("td",null,(l.city || "—") + "/" + (l.uf || "—")),
            h("td",null,
              h("div",{className:"hp-contact-actions"},
                l.website && h("a",{href:l.website,target:"_blank",rel:"noopener noreferrer"},"Site"),
                whatsappUrl(l.phone) && h("a",{href:whatsappUrl(l.phone),target:"_blank",rel:"noopener noreferrer", "aria-label":"Abrir WhatsApp de " + l.name},"WhatsApp"),
                emailUrl(l.email) && h("a",{href:emailUrl(l.email),"aria-label":"Enviar e-mail para " + l.name},"E-mail")),
              !l.website && !whatsappUrl(l.phone) && !emailUrl(l.email) && "—",
              l.phone && h("small",null,l.phone),l.email && h("small",null,l.email),
              l.website && h("div",{className:"hp-site-audit"},
                h("span",null,auditLabel(l.site_audit)),
                l.site_audit && h("small",null,"Verificado: " + when(l.site_audit.checked_at)),
                l.site_audit && (l.site_audit.issues || []).length > 0 && h("details",null,
                  h("summary",null,"Detalhes da análise"),
                  h("ul",null,...l.site_audit.issues.map((issue,i)=>h("li",{key:i},issue)))),
                button(l.site_audit ? "Atualizar análise" : "Analisar site",
                  () => change(() => request("/leads/"+encodeURIComponent(l.id)+"/analyze-site","POST"),"Análise do site atualizada."),
                  {disabled:busy,className:"hp-audit-button"}))),
            h("td",null,h("select",{value:l.status,onChange:e=>change(() => request("/leads/"+l.id+"/status","PATCH",{status:e.target.value}),"Status atualizado.")},
              ...["Novo","Em análise","Contatado","Proposta enviada","Fechado"].map(s=>h("option",{key:s},s)))),
            h("td",null,when(l.last_seen_at)))) : [h("tr",{key:"empty"},h("td",{colSpan:5},"Nenhum lead encontrado."))]))),
        h("div", {className:"hp-pagination"},
          h("span",null,leads.total+" lead(s) · página "+leads.page),
          button("Anterior",()=>load({...filter,page:Math.max(1,leads.page-1)}).catch(e=>setError(String(e.message||e))),{disabled:leads.page<=1}),
          button("Próxima",()=>load({...filter,page:leads.page+1}).catch(e=>setError(String(e.message||e))),{disabled:leads.page*20>=leads.total})))),
      page === "campaigns" && h("section",{className:"hp-grid"},
        h("div",null,h("h2",null,"Campanhas"),...(campaigns.length ? campaigns.map(c=>h("article",{className:"hp-card",key:c.id},
          h("h3",null,c.name),h("p",null,c.niche+" · "+c.cities.map(x=>x.city+"/"+x.uf).join(", ")),
          h("p",null,c.state+" · meta "+c.target_leads+" · rodada "+money(c.run_cap_micro)),
          editingId === c.id ? h("form",{className:"hp-edit-form",onSubmit:e=>saveCampaign(e,c.id)},
            h("h4",null,"Editar campanha"),
            field("Nome","name",{required:true,maxLength:120,defaultValue:c.name}),
            field("Nicho para busca","niche",{required:true,maxLength:120,defaultValue:c.niche}),
            field("Serviço oferecido","service",{defaultValue:c.service || ""}),
            field("Cidades (Cidade, UF por linha)","cities",{tag:"textarea",required:true,rows:4,
              defaultValue:c.cities.map(x=>x.city+", "+x.uf).join("\n")}),
            h("div",{className:"hp-sources-form"},h("strong",null,"Fontes para buscar"),sourceChecks(c.sources || ["google_maps"])),
            field("Meta de leads","target",{type:"number",min:1,max:1000,required:true,defaultValue:c.target_leads}),
            field("Teto por rodada (USD)","cap",{type:"number",min:"0.01",step:"0.01",required:true,
              defaultValue:(c.run_cap_micro/1000000).toFixed(2)}),
            field("Teto mensal (USD)","monthly",{type:"number",min:"0.01",step:"0.01",required:true,
              defaultValue:(c.monthly_cap_micro/1000000).toFixed(2)}),
            h("div",{className:"hp-actions"},h("button",{type:"submit",disabled:busy},"Salvar alterações"),
              button("Cancelar",()=>setEditingId(null))))
            : h("form",{className:"hp-sources-form",onSubmit:e=>{e.preventDefault();
            const sources=new FormData(e.currentTarget).getAll("sources");
            change(()=>request("/campaigns/"+c.id,"PATCH",{sources}),"Fontes atualizadas. A rodada já enfileirada mantém as fontes anteriores.");}},
            h("strong",null,"Fontes da campanha"),sourceChecks(c.sources || ["google_maps"]),
            h("button",{type:"submit",disabled:busy||c.state==="archived"},"Salvar fontes")),
          h("div",{className:"hp-actions"},
            button(editingId === c.id ? "Fechar edição" : "Editar",()=>setEditingId(editingId === c.id ? null : c.id),
              {disabled:busy||c.state==="archived"}),
            button("Buscar agora",()=>{if(window.confirm("Executar busca paga até "+money(c.run_cap_micro)+"?"))
              change(()=>request("/campaigns/"+c.id+"/runs","POST"),"Busca enfileirada.");},{disabled:busy||!status.treg_configured||c.state==="archived"}),
            button("Duplicar",()=>change(()=>request("/campaigns/"+c.id+"/duplicate","POST"),"Campanha duplicada.")),
            button(c.state==="paused"?"Retomar":"Pausar",()=>change(()=>request("/campaigns/"+c.id+"/state","PATCH",{state:c.state==="paused"?"draft":"paused"}),"Estado alterado."),{disabled:c.state==="archived"}),
            button("Arquivar",()=>{if(window.confirm("Arquivar campanha? Os dados serão preservados."))
              change(()=>request("/campaigns/"+c.id+"/state","PATCH",{state:"archived"}),"Arquivada.");},{disabled:c.state==="archived"})))) : [h("p",{key:"empty"},"Nenhuma campanha.")])),
        h("form",{className:"hp-card",onSubmit:createCampaign},h("h2",null,"Nova campanha"),
          field("Nome","name",{required:true}),field("Nicho para busca","niche",{required:true,placeholder:"dentista"}),
          field("Serviço oferecido","service"),field("Cidades (Cidade, UF por linha)","cities",{tag:"textarea",required:true,rows:4,placeholder:"Fortaleza, CE"}),
          h("div",{className:"hp-sources-form"},h("strong",null,"Fontes para buscar"),sourceChecks(["google_maps"])),
          field("Meta de leads","target",{type:"number",min:1,max:1000,defaultValue:30}),
          field("Teto por rodada (USD)","cap",{type:"number",min:"0.01",step:"0.01",defaultValue:"1.00"}),
          field("Teto mensal (USD)","monthly",{type:"number",min:"0.01",step:"0.01",defaultValue:"30.00"}),
          h("button",{type:"submit",disabled:busy},"Criar em rascunho"))),
      page === "runs" && h("section",null,h("h2",null,"Execuções"),
        h("div",{className:"hp-actions"},button("Atualizar",()=>load().catch(e=>setError(String(e.message||e)))),
          button("Reconciliar custos",()=>change(()=>request("/runs/reconcile","POST"),"Ledger consultado; chamadas pendentes atualizadas."))),
        ...(runs.length ? runs.map(r=>h("article",{className:"hp-card",key:r.id},
          h("h3",null,campaigns.find(c=>c.id===r.campaign_id)?.name || "Campanha"),
          h("p",null,r.state+" · "+when(r.created_at)+" · "+r.new_campaign+" novos · "+money(r.cost_micro)),
          r.financial_state==="pending"&&h("p",{className:"hp-error"},"Custo pendente de reconciliação"),
          r.error&&h("p",{className:"hp-error"},r.error))) : [h("p",{key:"empty"},"Nenhuma execução.")])),
      page === "settings" && h("section",{className:"hp-grid"},
        h("form",{className:"hp-card",onSubmit:saveToken},h("h2",null,"Treg"),
          h("p",null,"A chave é validada gratuitamente e guardada no perfil do Hermes. Use HTTPS para enviá-la."),
          status.treg_token_hint && h("p",{className:"hp-key-hint"},"Chave salva: ",h("strong",null,status.treg_token_hint)),
          field("Chave Treg","token",{type:"password",required:true,autoComplete:"off",
            placeholder:status.treg_token_hint || ""}),
          field("Organização (token de identidade)","org"),
          h("button",{type:"submit",disabled:busy},status.treg_configured?"Substituir chave":"Validar e salvar")),
        h("form",{className:"hp-card",onSubmit:saveBudget},h("h2",null,"Orçamento global"),
          h("p",null,money(status.global_used_micro)+" de "+money(status.global_monthly_cap_micro)+" em "+status.global_period),
          field("Teto mensal (USD)","cap",{type:"number",min:"0.01",step:"0.01",defaultValue:(status.global_monthly_cap_micro/1000000).toFixed(2)}),
          field("Fuso","timezone",{defaultValue:"America/Fortaleza"}),
          h("button",{type:"submit",disabled:busy},"Salvar teto"))),
      page === "schedule" && h("section",{className:"hp-grid"},
        h("div",null,h("h2",null,"Programações"),...(schedules.length ? schedules.map(s=>h("article",{className:"hp-card",key:s.campaign_id},
          h("h3",null,campaigns.find(c=>c.id===s.campaign_id)?.name || "Campanha"),
          h("p",null,s.state+" · "+s.frequency+" · "+s.timezone),
          h("p",null,"Próximas: "+(s.next_occurrences || []).map(when).join(" · ")),
          h("div",{className:"hp-actions"},button("Ativar",()=>change(()=>request("/schedules/"+s.campaign_id+"/activate","POST"),"Programação ativa."),{disabled:s.state==="active"}),
            button("Pausar",()=>change(()=>request("/schedules/"+s.campaign_id+"/pause","POST"),"Programação pausada."),{disabled:s.state!=="active"})))) : [h("p",{key:"empty"},"Nenhuma programação.")])),
        h("form",{className:"hp-card",onSubmit:saveSchedule},h("h2",null,"Programar campanha"),
          h("label",{className:"hp-field"},h("span",null,"Campanha"),h("select",{name:"campaign_id",required:true},
            h("option",{value:""},"Selecione"),...campaigns.filter(c=>c.state!=="archived").map(c=>h("option",{key:c.id,value:c.id},c.name)))),
          h("label",{className:"hp-field"},h("span",null,"Frequência"),h("select",{name:"frequency"},
            h("option",{value:"daily"},"Todos os dias"),h("option",{value:"weekdays"},"Dias da semana"),h("option",{value:"once"},"Uma vez"))),
          field("Horários HH:MM separados por vírgula","times",{defaultValue:"09:00"}),
          h("div",null,h("span",null,"Dias para frequência semanal"),
            ...["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"].map((d,i)=>
              h("label",{className:"hp-day",key:d},h("input",{type:"checkbox",name:"days",value:i}),d))),
          field("Data e hora para execução única","once_at",{type:"datetime-local"}),
          field("Fuso IANA","timezone",{defaultValue:"America/Fortaleza",required:true}),
          h("button",{type:"submit",disabled:busy},"Salvar em pausa"))),
      page === "about" && h("section",{className:"hp-about"},
        h("article",{className:"hp-card"},
          h("small",null,"HERMES PROSPECTOR"),
          h("h2",null,"Sobre o plugin"),
          h("p",null,"Campanhas, leads, custos e programação de buscas Treg no Hermes."),
          h("p",null,"Desenvolvedor: ",h("strong",null,ABOUT.developer)),
          h("p",null,"Versão 0.1.0.dev3")),
        h("article",{className:"hp-card"},
          h("h2",null,"Contato e suporte"),
          h("dl",{className:"hp-contact-list"},
            h("div",null,h("dt",null,"Site"),h("dd",null,h("a",{href:ABOUT.website,target:"_blank",rel:"noopener noreferrer"},ABOUT.website))),
            h("div",null,h("dt",null,"Instagram"),h("dd",null,h("a",{href:ABOUT.instagram,target:"_blank",rel:"noopener noreferrer"},ABOUT.instagramLabel))),
            h("div",null,h("dt",null,"YouTube"),h("dd",null,h("a",{href:ABOUT.youtube,target:"_blank",rel:"noopener noreferrer"},ABOUT.youtubeLabel))),
            h("div",null,h("dt",null,"E-mail"),h("dd",null,h("a",{href:"mailto:"+ABOUT.email},ABOUT.email))),
            h("div",null,h("dt",null,"WhatsApp"),h("dd",null,h("a",{href:ABOUT.whatsappUrl,target:"_blank",rel:"noopener noreferrer"},ABOUT.whatsapp)))))));
  }

  window.__HERMES_PLUGINS__.register("hermes-prospector", ProspectorPage);
})();
