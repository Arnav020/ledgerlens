const C = { red:"#B23A2E", slate:"#38576E", green:"#4F7A52", terra:"#BC6A34", mute:"#8A8678", ink:"#1A1D23" };
const sevColor = s => ({critical:C.red, high:C.red, medium:C.terra, low:C.mute}[s] || C.mute);
const tierColor = t => ({high:C.red, medium:C.terra, low:C.mute}[t] || C.mute);
const classMeta = c => ({
  cross_document:["Cross-document", C.slate], structural:["Within-document", C.slate],
  pdf_forensic:["Born-digital PDF", C.red], visual_forensic:["Visual forensic", C.mute]
}[c] || [c, C.mute]);
const statusMeta = s => ({
  observed_inconsistency:["Observed", C.red], potential_manipulation:["Potential", C.terra],
  needs_human_review:["Needs review", C.mute]
}[s] || [s, C.mute]);

let state = { packet:"manipulated", data:null, sel:null, tab:"evidence" };

function pill(text, color){ return `<span class="pill" style="color:${color}">${text}</span>`; }

async function load(packet){
  state.packet = packet;
  const res = await fetch(`data/${packet}.json?v=5`, {cache:"no-store"});
  state.data = await res.json();
  state.sel = state.data.findings.length ? state.data.findings[0].id : null;
  document.getElementById("dossierLink").style.display = packet === "manipulated" ? "" : "none";
  renderVerdict(); renderFindings(); renderTabs();
}

function renderVerdict(){
  const d = state.data, sm = d.summary;
  const vcol = sm.verdict === "HIGH RISK" ? C.red : (sm.verdict.includes("REVIEW") ? C.terra : C.green);
  const metrics = [
    ["Documents", Object.keys(d.documents).length],
    ["Findings", d.findings.length],
    ["Observed inconsistencies", sm.observed],
    ["Needs review", sm.potential + sm.needs_review],
  ];
  document.getElementById("verdict").innerHTML = `
    <div class="vbanner" style="border-color:${vcol}">
      <div class="vstamp" style="background:${vcol}">${sm.verdict}</div>
      <div><h1>${d.findings.length ? "Investigation complete" : "No anomalies detected"}</h1>
      <p>${sm.recommendation}</p></div>
    </div>
    <div class="metrics">${metrics.map(([l,n])=>`
      <div class="metric"><div class="n" style="color:${l==='Findings'&&d.findings.length?C.red:C.ink}">${n}</div>
      <div class="l">${l}</div></div>`).join("")}</div>`;
}

function renderFindings(){
  const d = state.data;
  document.getElementById("findCount").textContent = d.findings.length ? `${d.findings.length} ranked` : "clean";
  const list = document.getElementById("findingsList");
  if(!d.findings.length){
    list.innerHTML = `<div class="empty"><div class="big">0 findings</div>
      <div>The genuine packet is internally consistent.</div></div>`;
    return;
  }
  list.innerHTML = d.findings.map(f=>{
    const [cls,ccol]=classMeta(f.anomaly_class); const [st,scol]=statusMeta(f.status);
    const active = f.id===state.sel ? "active":"";
    return `<button class="fcard ${active}" data-id="${f.id}" style="border-left-color:${sevColor(f.severity)}">
      <div class="ftitle">${f.title}</div>
      <div class="frow"><span class="fcls" style="color:${ccol}">${cls}</span>
        ${pill(f.confidence_tier.toUpperCase(), tierColor(f.confidence_tier))}
        ${pill(st, scol)}</div></button>`;
  }).join("");
  list.querySelectorAll(".fcard").forEach(b=>b.onclick=()=>{ state.sel=b.dataset.id; state.tab="evidence"; renderFindings(); renderTabs(); });
}

function viewer(docId, bbox){
  const doc = state.data.documents[docId];
  const src = `data/${state.packet}/${doc.img}`;
  if(bbox){
    const [x,y,w,h]=bbox;
    return `<div class="viewer zoomed" data-x="${x}" data-y="${y}" data-w="${w}" data-h="${h}" data-nw="${doc.w}" data-nh="${doc.h}">
      <img src="${src}" alt="${doc.display_name}"><div class="hl"></div></div>`;
  }
  return `<div class="viewer full"><img src="${src}" alt="${doc.display_name}"></div>`;
}

function layoutZoom(root){
  root.querySelectorAll(".viewer.zoomed").forEach(v=>{
    const x=+v.dataset.x, y=+v.dataset.y, w=+v.dataset.w, h=+v.dataset.h, nw=+v.dataset.nw;
    const img=v.querySelector("img"), hl=v.querySelector(".hl");
    const apply=()=>{
      const vw=v.clientWidth, H=v.clientHeight;
      const padX=Math.max(140, w*0.6), padY=90;
      let scale=vw/(w+2*padX);
      const imgW=nw*scale;
      const left=-(x-padX)*scale;
      const top=H/2-(y+h/2)*scale;
      img.style.width=imgW+"px"; img.style.left=left+"px"; img.style.top=top+"px";
      hl.style.left=(x*scale+left)+"px"; hl.style.top=(y*scale+top)+"px";
      hl.style.width=(w*scale)+"px"; hl.style.height=(h*scale)+"px";
    };
    if(img.complete && img.naturalWidth) apply(); else img.onload=apply;
  });
}

function renderEvidence(){
  const pane = document.getElementById("pane-evidence");
  const d = state.data;
  if(!d.findings.length){
    pane.innerHTML = `<div class="empty" style="border-style:solid"><div class="big">Genuine packet verified</div>
      <div>Every field reconciles within and across the five documents. No evidence to show.</div></div>`;
    return;
  }
  const f = d.findings.find(x=>x.id===state.sel) || d.findings[0];
  const [cls,ccol]=classMeta(f.anomaly_class); const [st,scol]=statusMeta(f.status);
  pane.innerHTML = `
    <div class="detail-head"><h2>${f.title}</h2>
      <div class="detail-meta">
        <span class="fcls" style="color:${ccol};font-family:var(--mono);font-size:11px;font-weight:700;align-self:center">${cls}</span>
        ${pill(f.confidence_tier.toUpperCase()+" CONFIDENCE", tierColor(f.confidence_tier))}
        ${pill(st, scol)}
        <span class="pill" style="color:var(--mute)">${f.id}</span></div>
      <div class="detail-expl">${f.explanation}</div>
      ${f.recommended_action?`<div class="rec"><b>Recommended action:</b> ${f.recommended_action}</div>`:""}
    </div>
    <div class="ev-title">EVIDENCE · CLICK-TO-SOURCE</div>
    <div class="ev-grid">${f.evidence.map(e=>{
      const doc = d.documents[e.doc_id];
      return `<div class="ev-card">
        <div class="ev-head"><span class="ev-doc">${doc.display_name}</span><span class="ev-snip">${e.snippet||""}</span></div>
        ${viewer(e.doc_id, e.bbox)}
        <div class="ev-note">${e.bbox?"Highlighted region traced to the source document.":"Document-level signal (file structure / metadata)."}</div>
      </div>`;
    }).join("")}</div>`;
  layoutZoom(pane);
}

function renderDocuments(){
  const d = state.data;
  document.getElementById("pane-documents").innerHTML = `<div class="docs-grid">${
    Object.values(d.documents).map(doc=>{
      const fields = d.fields[doc.id]||{};
      const rows = Object.entries(fields).slice(0,6).map(([k,v])=>
        `<div><span>${k.replace(/_/g,' ')}</span><span class="fc">${v.value} · ${Math.round(v.confidence*100)}%</span></div>`).join("");
      return `<div class="doc-card"><div class="dthumb"><img src="data/${state.packet}/${doc.img}"></div>
        <div class="dmeta"><div class="dname">${doc.display_name}</div><div class="dtype">${doc.doc_type}</div>
        <div class="dfields">${rows||"<div class='fc'>no labelled fields</div>"}</div></div></div>`;
    }).join("")}</div>`;
}

function renderGraph(){
  const d = state.data;
  const order = (d.node_order || Object.keys(d.documents)).filter(id=>d.documents[id]);
  const n = order.length, cx=460, cy=248, R=172, pos={};
  order.forEach((id,i)=>{ const a=(-90+i*360/n)*Math.PI/180; pos[id]={x:cx+R*Math.cos(a), y:cy+R*Math.sin(a)}; });
  const short={application:["Loan","Form"], id:["PAN","Identity"], bank_statement:["Bank","Statement"],
               salary_slip:["Salary","Slip"], address_proof:["Address","Proof"]};
  const es=e=>({date_of_birth:"DOB", full_name:"name", pan:"PAN", address:"address",
                employer:"employer", account_number:"account"}[e]||e);
  let edges="", labels="", nodes="";
  (d.correlations||[]).forEach(c=>{
    if(!pos[c.a]||!pos[c.b]) return;
    const p=pos[c.a], q=pos[c.b], con=c.conflicts&&c.conflicts.length;
    edges+=`<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="${con?'#B23A2E':'#4F7A52'}"
      stroke-width="${con?3.2:1.8}" ${con?'stroke-dasharray="9 6"':'opacity="0.32"'} stroke-linecap="round"/>`;
    if(con){ const mx=(p.x+q.x)/2, my=(p.y+q.y)/2, t=c.conflicts.map(es).join(" · "), wdt=t.length*7+16;
      labels+=`<g transform="translate(${mx},${my})"><rect x="${-wdt/2}" y="-11" width="${wdt}" height="22" rx="7" fill="#F6F2E9" stroke="#B23A2E" stroke-width="1.2"/>
        <text x="0" y="4.5" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="11.5" font-weight="700" fill="#B23A2E">${t}</text></g>`; }
  });
  order.forEach(id=>{ const p=pos[id], nm=short[id]||[d.documents[id].display_name,""];
    nodes+=`<circle cx="${p.x}" cy="${p.y}" r="41" fill="#223140" filter="url(#clay)"/>
      <text x="${p.x}" y="${p.y-3}" text-anchor="middle" font-family="Fraunces,serif" font-weight="600" font-size="13.5" fill="#F6F2E9">${nm[0]}</text>
      <text x="${p.x}" y="${p.y+14}" text-anchor="middle" font-family="Fraunces,serif" font-weight="600" font-size="13.5" fill="#F6F2E9">${nm[1]}</text>`; });
  const legend=`<g transform="translate(40,512)">
    <line x1="0" y1="0" x2="34" y2="0" stroke="#4F7A52" stroke-width="3" opacity="0.55"/>
    <text x="42" y="4.5" font-family="JetBrains Mono,monospace" font-size="11.5" fill="#6A665C">consistent across documents</text>
    <line x1="268" y1="0" x2="302" y2="0" stroke="#B23A2E" stroke-width="3.2" stroke-dasharray="9 6"/>
    <text x="310" y="4.5" font-family="JetBrains Mono,monospace" font-size="11.5" font-weight="700" fill="#B23A2E">cross-document conflict</text></g>`;
  const svg = `<svg viewBox="0 0 920 540" width="100%" style="display:block">
    <defs><filter id="clay" x="-40%" y="-40%" width="180%" height="180%">
      <feDropShadow dx="3" dy="5" stdDeviation="5" flood-color="rgba(60,45,20,0.45)"/></filter></defs>
    ${edges}${labels}${nodes}${legend}</svg>`;
  const body = d.correlations && d.correlations.length ? svg
    : `<p style="padding:30px;color:var(--mute)">No correlated entities to graph.</p>`;
  document.getElementById("pane-graph").innerHTML =
    `<div class="graph-cap">Each document is a node. Edges link documents that share an entity —
      green where the values agree, red dashed where they conflict.</div>
     <div class="graph-wrap">${body}</div>`;
}

function renderAudit(){
  const d = state.data;
  document.getElementById("pane-audit").innerHTML = `<table class="audit">${
    d.audit.map(a=>`<tr><td class="ts">${a.ts.replace('T',' ')}</td><td class="stage">${a.stage}</td><td>${a.message}</td></tr>`).join("")}</table>`;
}

function renderTabs(){
  renderEvidence(); renderDocuments(); renderGraph(); renderAudit();
  document.querySelectorAll(".tabs button").forEach(b=>b.classList.toggle("active", b.dataset.tab===state.tab));
  ["evidence","documents","graph","audit"].forEach(t=>
    document.getElementById("pane-"+t).classList.toggle("hidden", t!==state.tab));
}

document.getElementById("tabs").onclick = e=>{ if(e.target.dataset.tab){ state.tab=e.target.dataset.tab; renderTabs(); } };
document.getElementById("packetToggle").onclick = e=>{
  if(e.target.dataset.packet){
    document.querySelectorAll("#packetToggle button").forEach(b=>b.classList.toggle("active", b===e.target));
    load(e.target.dataset.packet);
  }
};
load("manipulated");
