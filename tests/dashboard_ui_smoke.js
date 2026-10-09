const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../dashboard/dist/index.js"), "utf8");
const expected = {
  dashboard: ["Nenhum lead encontrado."],
  campaigns: ["Nova campanha", "Criar em rascunho", "Google Maps", "Instagram", "LinkedIn"],
  schedule: ["Programar campanha", "Salvar em pausa"],
  runs: ["Nenhuma execução.", "Reconciliar custos"],
  settings: ["Chave Treg", "Validar e salvar", "Orçamento global", "Salvar teto"],
  about: ["Sobre o plugin", "André Alencar", "https://www.aalencar.com.br",
    "@empreendedorserialbr", "YouTube", "@empreendedorserial", "suporte@aalencar.com.br", "+55 86 9999-7003"],
};

function render(page, configured = false, campaignItems = [], editingId = null, leadItems = []) {
  let hook = 0;
  let component;
  const React = {createElement: (type, props, ...children) => ({type, props, children})};
  const hooks = {
    useState(initial) {
      hook += 1;
      const value = hook === 1 ? page : hook === 2 ? {
        treg_configured: configured, treg_token_hint: configured ? "••••••••WXYZ" : null,
        leads: 0, campaigns: 0, queued: 0,
        global_used_micro: 0, global_monthly_cap_micro: 200000,
        global_period: "2026-10",
      } : hook === 3 ? campaignItems : hook === 6 ? {items:leadItems,total:leadItems.length,page:1,size:20}
        : hook === 10 ? true : hook === 12 ? editingId : initial;
      return [value, () => {}];
    },
    useEffect() {},
    useCallback(callback) { return callback; },
  };
  const window = {
    __HERMES_PLUGIN_SDK__: {React, hooks},
    __HERMES_PLUGINS__: {register(id, value) {
      assert.equal(id, "hermes-prospector");
      component = value;
    }},
  };
  vm.runInNewContext(source, {window, URLSearchParams}, {filename: "dashboard/dist/index.js"});
  assert.equal(typeof component, "function");
  return component();
}

function flatten(node) {
  if (node == null || node === false) return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(flatten).join(" ");
  return (node.children || []).map(flatten).join(" ");
}

for (const [page, labels] of Object.entries(expected)) {
  const tree = render(page);
  const text = flatten(tree);
  for (const label of labels) {
    assert.ok(text.includes(label), `${page}: conteúdo ausente: ${label}`);
  }
  for (const [otherPage, otherLabels] of Object.entries(expected)) {
    if (otherPage !== page) {
      assert.ok(!text.includes(otherLabels[0]), `${page}: exibiu conteúdo da aba ${otherPage}`);
    }
  }
  console.log(`${page}: conteúdo exibido`);
}

const configured = render("settings", true);
const configuredText = flatten(configured);
assert.match(configuredText, /Chave salva:\s+••••••••WXYZ/);
assert.ok(configuredText.includes("Substituir chave"));
assert.ok(!configuredText.includes("test-token"));
console.log("settings: identificador mascarado exibido");

function anchors(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(anchors);
  return [...(node.type === "a" ? [node.props] : []), ...(node.children || []).flatMap(anchors)];
}

const aboutLinks = anchors(render("about")).map(link => link.href);
assert.deepEqual(aboutLinks, [
  "https://www.aalencar.com.br",
  "https://www.instagram.com/empreendedorserialbr/",
  "https://www.youtube.com/@empreendedorserial",
  "mailto:suporte@aalencar.com.br",
  "https://wa.me/558699997003",
]);
console.log("about: links de contato conferidos");

const lead = {id:"lead-1",name:"Clínica Exemplo",city:"Teresina",uf:"PI",status:"Novo",
  phone:"+55 (86) 99814-1883",email:"contato@exemplo.com.br",website:"https://exemplo.com.br",sources:["google_maps"]};
const leadLinks = anchors(render("dashboard",true,[],null,[lead]));
assert.ok(leadLinks.some(link => link.href === "https://wa.me/5586998141883" && link.target === "_blank"));
assert.ok(leadLinks.some(link => link.href === "mailto:contato%40exemplo.com.br"));
assert.ok(leadLinks.some(link => link.href === "https://exemplo.com.br"));
const missingLinks = anchors(render("dashboard",true,[],null,[{...lead,phone:"",email:""}]));
assert.ok(!missingLinks.some(link => link.href?.startsWith("https://wa.me/") || link.href?.startsWith("mailto:")));
const invalidLinks = anchors(render("dashboard",true,[],null,[{...lead,phone:"123",email:"invalid@example.com\nBcc:x"}]));
assert.ok(!invalidLinks.some(link => link.href?.startsWith("https://wa.me/") || link.href?.startsWith("mailto:")));
console.log("leads: links de WhatsApp e e-mail conforme contatos válidos");
const auditLead = {...lead,site_audit:{availability:"online",page_type:"delivery",provider:"iFood",
  seo_score:null,issues:["Página em plataforma de terceiros; SEO do site próprio não aplicável"]}};
const auditText = flatten(render("dashboard",true,[],null,[auditLead]));
assert.ok(auditText.includes("No ar · iFood"));
assert.ok(auditText.includes("Atualizar análise"));
assert.ok(auditText.includes("Página em plataforma de terceiros"));
assert.ok(flatten(render("dashboard",true,[],null,[{...lead,site_audit:{...auditLead.site_audit,
  availability:"offline",page_type:"unknown",provider:null}}])).includes("Fora do ar"));
console.log("leads: resultado da análise do site exibido");

const campaign = {id:"campaign-1",name:"Clínica Estética",niche:"estética",service:"Marketing",
  cities:[{city:"Teresina",uf:"PI"}],sources:["google_maps","instagram"],state:"draft",
  target_leads:30,run_cap_micro:1000000,monthly_cap_micro:2000000};
const campaignText = flatten(render("campaigns",true,[campaign]));
assert.ok(campaignText.includes("Editar"));
assert.ok(campaignText.includes("rodada US$ 1,00"));
assert.ok(!campaignText.includes("US$ 1.0000"));
assert.ok(flatten(render("campaigns",true,[{...campaign,run_cap_micro:1000000000}])).includes("US$ 1.000,00"));
const editTree = render("campaigns",true,[campaign],campaign.id);
assert.ok(flatten(editTree).includes("Salvar alterações"));
function namedFields(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(namedFields);
  return [...(node.props?.name ? [node.props] : []), ...(node.children || []).flatMap(namedFields)];
}
const editFields = namedFields(editTree);
assert.ok(editFields.some(x => x.name === "service" && x.defaultValue === "Marketing"));
assert.ok(editFields.some(x => x.name === "cities" && x.defaultValue === "Teresina, PI"));
assert.ok(editFields.some(x => x.name === "sources" && x.value === "instagram" && x.defaultChecked));
console.log("campaigns: edição completa com dados existentes exibida");
