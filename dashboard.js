function show(id, el) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if (id === 'overview') buildCharts();
  if (id === 'windows') renderWindows();
  if (id === 'profiles') renderProfiles();
  if (id === 'qpr') renderQPR();
  if (id === 'history') renderHistory();
}

// ── DERIVED FIELDS ──────────────────────────────────────────────────────────
// Per-wine derived fields (drinkStatus, qprRaw, qprIndex, purchasePriceEff)
// are computed in the browser. This is the single source of truth for the
// derivation rules. The Python build step embeds raw data; recomputeDerivedFields()
// overwrites stale values before anything renders.
function _computeDrinkStatus(w) {
  var df = w.drinkFrom, dt = w.drinkTo;
  if (!df || !dt) return w.drinkStatus || 'wait';
  if (dt < CY) return 'past';
  if (df <= CY) return (dt === CY) ? 'urgent' : 'now';
  if (df <= CY + 2) return 'soon';
  return 'wait';
}
function recomputeDerivedFields() {
  WINES.forEach(function(w) { w.drinkStatus = _computeDrinkStatus(w); });
  if (typeof _recomputeQPR === 'function') _recomputeQPR();
}
recomputeDerivedFields();

// CHARTS
let _charts = {};
function buildCharts() {
  Object.values(_charts).forEach(function(c){if(c)c.destroy();});
  _charts = {};
  const def = { plugins:{ legend:{ labels:{ color:'#9b8a7a', font:{family:'Georgia'} } } }, scales:{ x:{ ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} }, y:{ ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} } } };

  // Country
  const cc = {}; WINES.forEach(w => cc[w.country] = (cc[w.country]||0)+w.qty);
  const cs = Object.entries(cc).sort((a,b)=>b[1]-a[1]);
  _charts.cc = new Chart(document.getElementById('countryChart'), { type:'bar', data:{ labels:cs.map(e=>e[0]), datasets:[{ data:cs.map(e=>e[1]), backgroundColor:['#7c2d3f','#c9a84c','#9b5a6a','#5a7c9b','#7c9b5a','#9b7c5a','#6a5a9b'], borderWidth:0 }] }, options:{ ...def, plugins:{ legend:{display:false} } } });

  // Style donut
  const sc = {}; WINES.forEach(w => sc[w.style]=(sc[w.style]||0)+w.qty);
  const scols = { red:'#7c2d3f', white:'#c9a84c', sparkling:'#5a8c9b', "rosé":'#c97a8a', dessert:'#9b7c3a', orange:'#c97a3a' };
  _charts.sc = new Chart(document.getElementById('styleChart'), { type:'doughnut', data:{ labels:Object.keys(sc).map(s=>s[0].toUpperCase()+s.slice(1)), datasets:[{ data:Object.values(sc), backgroundColor:Object.keys(sc).map(s=>scols[s]||'#777'), borderWidth:0, hoverOffset:6 }] }, options:{ plugins:{ legend:{ position:'right', labels:{ color:'#9b8a7a', font:{family:'Georgia'}, padding:12 } } }, cutout:'55%' } });

  // Varietal
  const vm = {};
  const vn = v => {
    if (v.includes('Pinot Noir')) return 'Pinot Noir';
    if (v.includes('Chardonnay')) return 'Chardonnay';
    if (v.includes('Cabernet Sauvignon')) return 'Cabernet Sauvignon';
    if (v.includes('Chenin Blanc')) return 'Chenin Blanc';
    if (v.includes('Gamay')) return 'Gamay';
    if (v.includes('Shiraz')||v.includes('Syrah')||v.includes('Mourvèdre')) return 'Shiraz / Mourvèdre';
    if (v.includes('Sangiovese')) return 'Sangiovese';
    if (v.includes('Nebbiolo')) return 'Nebbiolo';
    if (v.includes('Zinfandel')) return 'Zinfandel';
    if (v.includes('Merlot')||v.includes('Cab Franc')||v.includes('Cabernet Franc')) return 'Bordeaux Blend';
    if (v.includes('Sauvignon Blanc')||v.includes('Sémillon')) return 'Sauvignon Blanc';
    return 'Other / Rare';
  };
  WINES.forEach(w => { const k=vn(w.varietal); vm[k]=(vm[k]||0)+w.qty; });
  const vs = Object.entries(vm).sort((a,b)=>b[1]-a[1]);
  _charts.vc = new Chart(document.getElementById('varietalChart'), { type:'bar', data:{ labels:vs.map(e=>e[0]), datasets:[{ data:vs.map(e=>e[1]), backgroundColor:'#7c2d3f', borderWidth:0, hoverBackgroundColor:'#c9a84c' }] }, options:{ indexAxis:'y', plugins:{ legend:{display:false} }, scales:{ x:{ ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} }, y:{ ticks:{color:'#e8ddd0', font:{size:12}}, grid:{color:'rgba(58,37,53,.2)'} } } } });
}
buildCharts();

// WINDOWS
const GSTART=2000, GEND=2048;
const sColor = { past:'#e05050', urgent:'#e07830', now:'#4caf7a', soon:'#5090c8', wait:'#7a6a7a' };
const sLabel = { past:'Past window', urgent:'Open urgently', now:'Drink now', soon:'Open soon', wait:'Needs time' };

function renderWindows() {
  const sort = document.getElementById('wSort').value;
  const order = { past:0, urgent:1, now:2, soon:3, wait:4 };
  const data = [...WINES].sort((a,b) => {
    if (sort==='status') return order[a.drinkStatus]-order[b.drinkStatus];
    if (sort==='vintage') { const av=typeof a.vintage==='number'?a.vintage:9999, bv=typeof b.vintage==='number'?b.vintage:9999; return av-bv; }
    if (sort==='country') return a.country.localeCompare(b.country);
    if (sort==='style') return a.style.localeCompare(b.style);
    return 0;
  });
  const range = GEND-GSTART;
  const nowPct = (CY-GSTART)/range*100;
  document.getElementById('wBody').innerHTML = data.map(w => {
    const fp = Math.max(0,Math.min(100,(w.drinkFrom-GSTART)/range*100));
    const tp = Math.max(0,Math.min(100,(w.drinkTo-GSTART)/range*100));
    const wp = Math.max(1,tp-fp);
    const vd = typeof w.vintage==='string'?'NV':w.vintage;
    return '<tr>'
      + '<td style="max-width:220px"><div class="wine-name">'+w.wine+'</div><div class="wine-producer">'+w.producer+'</div></td>'
      + '<td style="color:var(--muted);white-space:nowrap">'+vd+'</td>'
      + '<td style="color:var(--muted)">'+w.country+'</td>'
      + '<td><span class="status-badge s-'+w.drinkStatus+'">'+sLabel[w.drinkStatus]+'</span></td>'
      + '<td style="width:100%;padding-right:12px"><div class="bar-track">'
      + '<div class="bar-fill" style="left:'+fp+'%;width:'+wp+'%;background:'+sColor[w.drinkStatus]+'"></div>'
      + '<div class="bar-now" style="left:'+nowPct+'%"></div>'
      + '<span class="bar-lbl">'+w.drinkFrom+'–'+w.drinkTo+'</span>'
      + '</div></td></tr>';
  }).join('');
}

// PROFILES
const eStyle = { red:'🍷', white:'🥂', sparkling:'✨', 'rosé':'🌸', dessert:'🍯', orange:'🍊' };

function renderProfiles() {
  const q = document.getElementById('sSearch').value.toLowerCase();
  const st = document.getElementById('sStyle').value;
  const co = document.getElementById('sCountry').value;
  const ss = document.getElementById('sStatus').value;
  const f = WINES.filter(w => {
    if (st && w.style!==st) return false;
    if (co && w.country!==co) return false;
    if (ss && w.drinkStatus!==ss) return false;
    if (q) { const h=[w.producer,w.wine,w.appellation,w.varietal,w.country].join(' ').toLowerCase(); if (!h.includes(q)) return false; }
    return true;
  });
  document.getElementById('resCount').textContent = f.length + ' wine' + (f.length!==1?'s':'');
  document.getElementById('cardGrid').innerHTML = f.map(w => {
    const vd = typeof w.vintage==='string'?'NV':w.vintage;
    const pp = w.purchasePrice ? '$'+w.purchasePrice+' paid · $'+w.marketPrice+' market' : '$'+w.marketPrice+' market';
    const disc = w.purchasePrice ? Math.round((1-w.purchasePrice/w.marketPrice)*100) : 0;
    const pb = w.pending ? '<span class="pending-badge" style="margin-left:4px">pending enrichment</span>' : '';
    const hasQpr = w.qprIndex != null;
    const qp = hasQpr ? (w.qprIndex-1)/9*100 : 0;
    const qprDisplay = hasQpr
      ? '<div class="qpr-bar"><span>QPR</span><div class="qpr-track"><div class="qpr-fill" style="width:'+qp+'%"></div></div><span style="color:var(--gold)">'+w.qprIndex+'/10</span></div>'
      : '<div style="font-size:11px;color:var(--muted)">QPR &mdash; no purchase price recorded</div>';
    return '<div class="wine-card">'
      + '<div class="card-hdr"><div>'
      + '<div class="card-producer">'+w.producer+' · '+vd+'</div>'
      + '<div class="card-wine">'+w.wine+'</div>'
      + '<div class="card-app">'+w.appellation+'</div>'
      + '</div><div><div class="card-score">'+w.score+'<span>pts</span></div></div></div>'
      + '<div class="card-meta">'
      + '<span class="meta-tag">'+(eStyle[w.style]||'')+' '+w.style+'</span>'
      + '<span class="meta-tag">'+w.country+'</span>'
      + '<span class="meta-tag">'+w.varietal.split(',')[0]+'</span>'
      + '<span class="status-badge s-'+w.drinkStatus+'">'+sLabel[w.drinkStatus]+'</span>'+pb
      + '</div>'
      + '<div style="font-size:12px;color:var(--muted)"><strong style="color:var(--cream)">Drink:</strong> '+w.drinkFrom+'–'+w.drinkTo+'</div>'
      + '<div class="card-sum">'+w.summary+'</div>'
      + '<div class="card-pair"><strong>Pairings:</strong> '+w.pairings.join(' · ')+'</div>'
      + '<div class="card-foot">'
      + qprDisplay
      + '<div style="font-size:11px;color:var(--muted)">'+pp+(disc>0?' · '+disc+'% off':'')+'</div>'
      + '</div></div>';
  }).join('');
}

// QPR
let qprChart = null;
function renderQPR() {
  if (qprChart) { qprChart.destroy(); qprChart = null; }
  const scols2 = { red:'rgba(124,45,63,.8)', white:'rgba(201,168,76,.8)', sparkling:'rgba(90,140,155,.8)', 'rosé':'rgba(201,122,138,.8)', dessert:'rgba(155,124,58,.8)', orange:'rgba(201,122,58,.8)' };
  const pricedWines = WINES.filter(w => w.qprIndex != null);
  const styleKeys = [...new Set(pricedWines.map(w=>w.style))];
  qprChart = new Chart(document.getElementById('qprScatter'), {
    type:'bubble',
    data:{ datasets: styleKeys.map(st => ({
      label: st[0].toUpperCase()+st.slice(1),
      data: pricedWines.filter(w=>w.style===st).map(w=>({
        x: w.purchasePriceEff, y: w.score,
        r: Math.max(4, Math.min(18, (1-w.purchasePrice/w.marketPrice)*16+5)),
        label: w.producer+' — '+w.wine.substring(0,30),
        paid: w.purchasePriceEff, market: w.marketPrice, score: w.score
      })),
      backgroundColor: scols2[st]||'rgba(128,128,128,.7)', borderWidth:1
    })).filter(d=>d.data.length) },
    options:{
      plugins:{
        legend:{ labels:{ color:'#9b8a7a', font:{family:'Georgia'} } },
        tooltip:{ callbacks:{ label: ctx => ctx.raw.label+' | Paid: $'+ctx.raw.paid+' | Market: $'+ctx.raw.market+' | Score: '+ctx.raw.score } }
      },
      scales:{
        x:{ title:{display:true,text:'Purchase Price ($)',color:'#9b8a7a'}, ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} },
        y:{ title:{display:true,text:'Score',color:'#9b8a7a'}, min:85, ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} }
      }
    }
  });
  const sorted = [...pricedWines].sort((a,b)=>b.qprIndex-a.qprIndex);
  document.getElementById('qprBody').innerHTML = sorted.map(w => {
    const paid = w.purchasePriceEff;
    const disc = (w.marketPrice && paid < w.marketPrice) ? Math.round((1-paid/w.marketPrice)*100) : 0;
    const qc = w.qprIndex>=7?'q-hi':w.qprIndex>=4?'q-mid':'q-lo';
    const vd = typeof w.vintage==='string'?'NV':w.vintage;
    return '<tr>'
      + '<td><div style="font-size:13px;color:var(--cream)">'+w.wine+'</div><div style="font-size:11px;color:var(--muted)">'+w.producer+' · '+w.appellation+'</div></td>'
      + '<td style="color:var(--muted)">'+vd+'</td>'
      + '<td style="color:var(--gold);text-align:center">'+w.score+'</td>'
      + '<td style="color:var(--cream)">$'+paid+'</td>'
      + '<td style="color:var(--muted)">$'+w.marketPrice+'</td>'
      + '<td style="color:'+(disc>0?'#4caf7a':'var(--muted)')+'">'+(disc>0?disc+'% off':'—')+'</td>'
      + '<td><span class="qval '+qc+'">'+w.qprIndex+'</span></td>'
      + '</tr>';
  }).join('');
}

renderWindows();
renderProfiles();

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  document.getElementById('themeLabel').textContent = isDark ? 'Dark' : 'Light';
  document.getElementById('toggleKnob').textContent = isDark ? '🌙' : '☀';
  setTimeout(() => {
    const activeId = document.querySelector('.section.active')?.id;
    if (activeId === 'qpr') renderQPR();
    else buildCharts();
  }, 50);
}

// ── EDIT DRAWER
let _editChanges = [];
function openDrawer() {
  document.getElementById("editDrawer").classList.add("open");
  document.getElementById("drawerOverlay").classList.add("open");
  renderInvList();
}
function closeDrawer() {
  document.getElementById("editDrawer").classList.remove("open");
  document.getElementById("drawerOverlay").classList.remove("open");
  refreshStats();
}
function switchEditTab(tab, el) {
  document.querySelectorAll(".drawer-tab").forEach(function(t){t.classList.remove("active");});
  document.querySelectorAll(".drawer-panel").forEach(function(p){p.classList.remove("active");});
  el.classList.add("active");
  document.getElementById("panel-" + tab).classList.add("active");
  if (tab === "inventory") renderInvList();
  if (tab === "export") renderChangeLog();
  if (tab === "add") _updateKeyStatus();
}
function renderInvList() {
  var q = (document.getElementById("invSearch").value || "").toLowerCase();
  var wines = WINES.filter(function(w) {
    if (!q) return true;
    return [w.producer, w.wine, w.appellation, w.varietal || ""].join(" ").toLowerCase().indexOf(q) !== -1;
  });
  document.getElementById("invList").innerHTML = wines.map(function(w) {
    var vd = typeof w.vintage === "string" ? "NV" : w.vintage;
    var zc = w.qty === 0 ? " qty-zero" : "";
    var pb = w.pending ? " <span class=\"pending-badge\">pending</span>" : "";
    return '<div class="inv-row" id="inv-' + w.id + '">'
      + '<div class="inv-info">'
      + '<div class="inv-name">' + w.producer + ' — ' + w.wine + '</div>'
      + '<div class="inv-sub">' + vd + ' · ' + w.appellation + pb + '</div>'
      + '</div>'
      + '<button class="tasting-link" onclick="logTastingFromWine(' + w.id + ')" title="Log a tasting">tasting</button>'
      + '<div class="qty-ctrl">'
      + '<button class="qty-btn" onclick="adjustQty(' + w.id + ',-1)">−</button>'
      + '<span class="qty-val' + zc + '">' + w.qty + '</span>'
      + '<button class="qty-btn" onclick="adjustQty(' + w.id + ',1)">+</button>'
      + '</div>'
      + '<button class="remove-btn" onclick="removeWine(' + w.id + ')" title="Remove">✕</button>'
      + '</div>';
  }).join("");
}
function adjustQty(id, delta) {
  var w = WINES.find(function(w){return w.id===id;});
  if (!w) return;
  if (delta < 0 && w.qty > 0) {
    var idx = WINES.findIndex(function(x){return x.id===id;});
    _openRateModal(w, idx, true);
    return;
  }
  if (delta > 0) {
    var prev = w.qty;
    w.qty = w.qty + 1;
    _logChange("▲ " + w.producer + " — " + w.wine
      + " (" + (typeof w.vintage === "string" ? "NV" : w.vintage) + "): qty " + prev + " → " + w.qty);
    renderInvList();
  }
}
function removeWine(id) {
  var idx = WINES.findIndex(function(w){return w.id===id;});
  if (idx === -1) return;
  var w = WINES[idx];
  _openRateModal(w, idx);
}
function logTastingFromWine(id) {
  var w = WINES.find(function(x){return x.id===id;});
  if (!w) return;
  var allIds = WINES.map(function(x){return x.id;}).concat(CONSUMED.map(function(x){return x.id;}));
  var newId = allIds.length ? Math.max.apply(null, allIds) + 1 : 1;
  var vintage = w.vintage;
  var vd = typeof vintage === "string" ? "NV" : vintage;
  var pendingEntry = Object.assign({}, w, {
    id: newId, qty: 1, adhoc: true,
    purchasePrice: null, purchasePriceEff: null, qprRaw: null, qprIndex: null
  });
  var overlay = document.getElementById("rateOverlay");
  var nameEl = document.getElementById("rateWineName");
  var noteEl = document.getElementById("rateNote");
  nameEl.textContent = w.producer + " — " + w.wine + " (" + vd + ")";
  noteEl.value = "";
  var btns = document.querySelectorAll("#rateBtns .rate-btn");
  btns.forEach(function(b){ b.classList.remove("selected"); b.onclick = function(){ btns.forEach(function(x){x.classList.remove("selected");}); b.classList.add("selected"); }; });
  var confirmBtn = document.getElementById("rateConfirmBtn");
  var cancelBtn = document.getElementById("rateCancelBtn");
  confirmBtn.textContent = "Log Tasting";
  overlay.classList.add("open");
  function cleanup() { overlay.classList.remove("open"); confirmBtn.onclick = null; cancelBtn.onclick = null; }
  cancelBtn.onclick = cleanup;
  confirmBtn.onclick = function() {
    var sel = document.querySelector("#rateBtns .rate-btn.selected");
    var rating = sel ? sel.getAttribute("data-val") : null;
    var note = noteEl.value.trim() || null;
    var today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/New_York'}).format(new Date());
    pendingEntry.removedDate = today;
    if (rating) pendingEntry.myRating = rating;
    if (note) pendingEntry.myNote = note;
    CONSUMED.push(pendingEntry);
    _logChange("✶ Tasting: " + w.producer + " — " + w.wine + " (" + vd + ")"
      + (rating ? " [" + rating + "]" : ""));
    cleanup();
  };
}
function _openRateModal(w, idx, fromDecrement) {
  var overlay = document.getElementById("rateOverlay");
  var nameEl = document.getElementById("rateWineName");
  var noteEl = document.getElementById("rateNote");
  nameEl.textContent = w.producer + " — " + w.wine + " (" + (typeof w.vintage === "string" ? "NV" : w.vintage) + ")";
  noteEl.value = "";
  var btns = document.querySelectorAll("#rateBtns .rate-btn");
  btns.forEach(function(b){ b.classList.remove("selected"); b.onclick = function(){ btns.forEach(function(x){x.classList.remove("selected");}); b.classList.add("selected"); }; });
  var confirmBtn = document.getElementById("rateConfirmBtn");
  var cancelBtn = document.getElementById("rateCancelBtn");
  confirmBtn.textContent = (fromDecrement && w.qty > 1) ? "Log Bottle" : "Confirm Removal";
  overlay.classList.add("open");
  function cleanup() { overlay.classList.remove("open"); confirmBtn.onclick = null; cancelBtn.onclick = null; }
  cancelBtn.onclick = cleanup;
  confirmBtn.onclick = function() {
    var sel = document.querySelector("#rateBtns .rate-btn.selected");
    var rating = sel ? sel.getAttribute("data-val") : null;
    var note = noteEl.value.trim() || null;
    var today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/New_York'}).format(new Date());
    var entry = Object.assign({}, w, {removedDate: today, qty: 1});
    if (rating) entry.myRating = rating;
    if (note) entry.myNote = note;
    CONSUMED.push(entry);
    var willRemove = !fromDecrement || w.qty <= 1;
    if (willRemove) {
      _logChange("✕ Consumed: " + w.producer + " — " + w.wine
        + " (" + (typeof w.vintage === "string" ? "NV" : w.vintage) + ")"
        + (rating ? " [" + rating + "]" : ""));
      WINES.splice(idx, 1);
    } else {
      var prev = w.qty;
      w.qty = prev - 1;
      _logChange("▼ " + w.producer + " — " + w.wine
        + " (" + (typeof w.vintage === "string" ? "NV" : w.vintage) + "): qty " + prev + " → " + w.qty
        + (rating ? " [" + rating + "]" : ""));
    }
    _recomputeQPR();
    renderInvList();
    refreshStats();
    cleanup();
  };
}
function addWine() {
  var producer = document.getElementById("f-producer").value.trim();
  var wine = document.getElementById("f-wine").value.trim();
  var country = document.getElementById("f-country").value;
  var style = document.getElementById("f-style").value;
  var qty = parseInt(document.getElementById("f-qty").value) || 1;
  var msg = document.getElementById("add-msg");
  if (!producer || !wine || !country || !style) {
    msg.style.color = "#e05050";
    msg.textContent = "Producer, Wine, Country and Style are required.";
    return;
  }
  var appellation = document.getElementById("f-appellation").value.trim() || "";
  var region = document.getElementById("f-region").value.trim() || country;
  var varietal = document.getElementById("f-varietal").value.trim() || "";
  var vintageRaw = document.getElementById("f-vintage").value;
  var vintage = vintageRaw ? parseInt(vintageRaw) : "NV";
  var purchasePrice = parseFloat(document.getElementById("f-purchase").value) || null;
  var marketPrice = parseFloat(document.getElementById("f-market").value) || null;
  var score = parseInt(document.getElementById("f-score").value) || 88;
  var drinkFrom = parseInt(document.getElementById("f-from").value) || CY;
  var drinkTo = parseInt(document.getElementById("f-to").value) || (CY + 5);
  var purchasePriceEff = purchasePrice || null;
  var allIds = WINES.map(function(w){return w.id;}).concat(CONSUMED.map(function(w){return w.id;}));
  var newId = allIds.length ? Math.max.apply(null, allIds) + 1 : 1;
  WINES.push({
    id: newId, producer: producer, wine: wine, appellation: appellation,
    country: country, region: region, vintage: vintage, qty: qty,
    varietal: varietal, style: style,
    purchasePrice: purchasePrice, marketPrice: marketPrice || purchasePrice || 0,
    score: score, drinkFrom: drinkFrom, drinkTo: drinkTo,
    pairings: (window._scanPending && window._scanPending.pairings && window._scanPending.pairings.length) ? window._scanPending.pairings : ["Pending enrichment"],
    summary: (window._scanPending && window._scanPending.summary) ? window._scanPending.summary : "Added manually — bring this file to Claude to complete tasting notes, pairings, and vintage context.",
    purchasePriceEff: purchasePriceEff, qprRaw: null, qprIndex: null,
    pending: !(window._scanPending && window._scanPending.pairings && window._scanPending.pairings.length)
  });
  window._scanPending = null;
  recomputeDerivedFields();  // fills in drinkStatus + QPR for the new wine
  _logChange("+ Added: " + producer + " — " + wine
    + " (" + (typeof vintage === "string" ? "NV" : vintage) + ") ×" + qty);
  clearAddForm();
  msg.style.color = "#4caf7a";
  msg.textContent = "✓ Added \"" + wine + "\" — switch to Inventory to verify.";
  setTimeout(function(){msg.textContent="";}, 4000);
}
function logTasting() {
  var producer = document.getElementById("f-producer").value.trim();
  var wine = document.getElementById("f-wine").value.trim();
  var country = document.getElementById("f-country").value;
  var style = document.getElementById("f-style").value;
  var msg = document.getElementById("add-msg");
  if (!producer || !wine || !country || !style) {
    msg.style.color = "#e05050";
    msg.textContent = "Producer, Wine, Country and Style are required.";
    return;
  }
  var appellation = document.getElementById("f-appellation").value.trim() || "";
  var region = document.getElementById("f-region").value.trim() || country;
  var varietal = document.getElementById("f-varietal").value.trim() || "";
  var vintageRaw = document.getElementById("f-vintage").value;
  var vintage = vintageRaw ? parseInt(vintageRaw) : "NV";
  var marketPrice = parseFloat(document.getElementById("f-market").value) || null;
  var score = parseInt(document.getElementById("f-score").value) || null;
  var drinkFrom = parseInt(document.getElementById("f-from").value) || null;
  var drinkTo = parseInt(document.getElementById("f-to").value) || null;
  var allIds = WINES.map(function(w){return w.id;}).concat(CONSUMED.map(function(w){return w.id;}));
  var newId = allIds.length ? Math.max.apply(null, allIds) + 1 : 1;
  var pendingEntry = {
    id: newId, producer: producer, wine: wine, appellation: appellation,
    country: country, region: region, vintage: vintage, varietal: varietal,
    style: style, score: score, marketPrice: marketPrice,
    purchasePrice: null, purchasePriceEff: null, qprRaw: null, qprIndex: null,
    drinkFrom: drinkFrom, drinkTo: drinkTo,
    pairings: (window._scanPending && window._scanPending.pairings && window._scanPending.pairings.length) ? window._scanPending.pairings : [],
    summary: (window._scanPending && window._scanPending.summary) ? window._scanPending.summary : "",
    qty: 1, adhoc: true
  };
  window._scanPending = null;
  var overlay = document.getElementById("rateOverlay");
  var nameEl = document.getElementById("rateWineName");
  var noteEl = document.getElementById("rateNote");
  nameEl.textContent = producer + " — " + wine + " (" + (typeof vintage === "string" ? "NV" : vintage) + ")";
  noteEl.value = "";
  var btns = document.querySelectorAll("#rateBtns .rate-btn");
  btns.forEach(function(b){ b.classList.remove("selected"); b.onclick = function(){ btns.forEach(function(x){x.classList.remove("selected");}); b.classList.add("selected"); }; });
  var confirmBtn = document.getElementById("rateConfirmBtn");
  var cancelBtn = document.getElementById("rateCancelBtn");
  confirmBtn.textContent = "Log Tasting";
  overlay.classList.add("open");
  function cleanup() { overlay.classList.remove("open"); confirmBtn.onclick = null; cancelBtn.onclick = null; }
  cancelBtn.onclick = cleanup;
  confirmBtn.onclick = function() {
    var sel = document.querySelector("#rateBtns .rate-btn.selected");
    var rating = sel ? sel.getAttribute("data-val") : null;
    var note = noteEl.value.trim() || null;
    var today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/New_York'}).format(new Date());
    pendingEntry.removedDate = today;
    if (rating) pendingEntry.myRating = rating;
    if (note) pendingEntry.myNote = note;
    CONSUMED.push(pendingEntry);
    _logChange("✶ Tasting: " + producer + " — " + wine
      + " (" + (typeof vintage === "string" ? "NV" : vintage) + ")"
      + (rating ? " [" + rating + "]" : ""));
    clearAddForm();
    msg.style.color = "#4caf7a";
    msg.textContent = "✓ Tasting logged — visible in Drinking History.";
    setTimeout(function(){msg.textContent="";}, 4000);
    cleanup();
  };
}
function clearAddForm() {
  ["f-producer","f-wine","f-appellation","f-varietal","f-region"].forEach(function(id){document.getElementById(id).value="";});
  ["f-country","f-style"].forEach(function(id){document.getElementById(id).value="";});
  ["f-vintage","f-purchase","f-market","f-score","f-from","f-to"].forEach(function(id){document.getElementById(id).value="";});
  document.getElementById("f-qty").value = "1";
  window._scanPending = null;
  var ss = document.getElementById("scanStatus");
  if (ss) { ss.className = "scan-status-line"; ss.textContent = ""; }
}
function _recomputeQPR() {
  var priced = WINES.filter(function(w){ return w.purchasePrice; });
  var raws = priced.map(function(w){ return w.score / w.purchasePrice; });
  var mn = Math.min.apply(null, raws), mx = Math.max.apply(null, raws);
  priced.forEach(function(w, i) {
    w.purchasePriceEff = w.purchasePrice;
    w.qprRaw = raws[i];
    w.qprIndex = mn === mx ? 5.0 : Math.round(((raws[i]-mn)/(mx-mn)*9+1)*10)/10;
  });
  WINES.forEach(function(w) {
    if (!w.purchasePrice) { w.purchasePriceEff = null; w.qprRaw = null; w.qprIndex = null; }
  });
}
function refreshStats() {
  var bottles = WINES.reduce(function(s,w){return s+w.qty;},0);
  var skus = WINES.length;
  var ctSet = {}; WINES.forEach(function(w){ctSet[w.country]=1;});
  var countries = Object.keys(ctSet).length;
  var mv = WINES.reduce(function(s,w){return s+(w.marketPrice*w.qty);},0);
  var vints = WINES.map(function(w){return typeof w.vintage==="number"?w.vintage:null;}).filter(Boolean);
  var spanStr = vints.length ? Math.min.apply(null,vints)+"–"+Math.max.apply(null,vints) : "—";
  var cards = document.querySelectorAll(".stat-card .stat-val");
  if (cards[0]) cards[0].textContent = bottles;
  if (cards[1]) cards[1].textContent = skus;
  if (cards[2]) cards[2].textContent = countries;
  if (cards[3]) cards[3].textContent = "$"+(mv>=1000?(mv/1000).toFixed(1)+"k":Math.round(mv));
  if (cards[4]) cards[4].textContent = spanStr;
  var activeId = (document.querySelector(".section.active")||{}).id;
  if (activeId === "overview") buildCharts();
  else if (activeId === "windows") renderWindows();
  else if (activeId === "profiles") renderProfiles();
  else if (activeId === "qpr") renderQPR();
}
function renderHistory() {
  var wrap = document.getElementById("historyWrap");
  var empty = document.getElementById("historyEmpty");
  var body = document.getElementById("historyBody");
  if (!body) return;
  if (!CONSUMED.length) {
    if (wrap) wrap.style.display = "none";
    if (empty) empty.style.display = "block";
    return;
  }
  if (wrap) wrap.style.display = "";
  if (empty) empty.style.display = "none";
  var sorted = CONSUMED.slice().sort(function(a,b){ return (b.removedDate||"").localeCompare(a.removedDate||""); });
  body.innerHTML = sorted.map(function(w) {
    var vd = typeof w.vintage === "string" ? "NV" : w.vintage;
    var score = (w.score != null && w.score !== 0) ? w.score : "—";
    var style = w.style ? (w.style[0].toUpperCase() + w.style.slice(1)) : "—";
    var rating = w.myRating ? (w.myRating[0].toUpperCase() + w.myRating.slice(1)) : "—";
    var noteHtml = w.myNote ? '<div style="font-size:10px;color:var(--muted);margin-top:2px;font-style:italic">' + w.myNote + '</div>' : '';
    var subLine = w.appellation || w.region || w.country || "";
    var tastingBadge = w.adhoc ? '<span style="font-size:9px;background:rgba(90,140,155,.18);color:#5a8c9b;border-radius:3px;padding:1px 5px;margin-left:5px;vertical-align:middle;letter-spacing:.3px">tasting</span>' : '';
    return '<tr>'
      + '<td style="color:var(--muted);white-space:nowrap">' + (w.removedDate || '—') + '</td>'
      + '<td><div style="font-size:13px;color:var(--cream)">' + w.wine + tastingBadge + '</div>'
      + '<div style="font-size:11px;color:var(--muted)">' + w.producer + (subLine ? ' · ' + subLine : '') + '</div></td>'
      + '<td style="color:var(--muted)">' + vd + '</td>'
      + '<td style="color:var(--muted)">' + style + '</td>'
      + '<td style="color:var(--gold);text-align:center">' + score + '</td>'
      + '<td style="color:var(--cream)">' + rating + noteHtml + '</td>'
      + '</tr>';
  }).join("");
}
function _logChange(msg) {
  var now = new Date();
  var ts = now.getHours().toString().padStart(2,"0")+":"+now.getMinutes().toString().padStart(2,"0");
  _editChanges.push("["+ts+"] "+msg);
  renderChangeLog();
}
function renderChangeLog() {
  var el = document.getElementById("changeLog");
  if (!el) return;
  if (!_editChanges.length) {
    el.innerHTML = '<span style="font-style:italic">No changes yet this session.</span>';
  } else {
    el.innerHTML = _editChanges.slice().reverse().map(function(e){
      return '<div class="change-entry">'+e+'</div>';
    }).join("");
  }
}
function exportHTML() {
  var src = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
  src = src.replace(/class="drawer-overlay open"/g, 'class="drawer-overlay"');
  src = src.replace(/class="drawer open"/g, 'class="drawer"');
  src = src.replace(/class="rate-overlay open"/g, 'class="rate-overlay"');
  var winesStr = 'const WINES = ' + JSON.stringify(WINES, null, '\n') + ';';
  src = src.replace(/const WINES = \[[\s\S]*?\];/, winesStr);
  var consumedStr = 'const CONSUMED = ' + JSON.stringify(CONSUMED, null, '\n') + ';';
  src = src.replace(/const CONSUMED = \[[\s\S]*?\];/, consumedStr);
  var d = new Date(), fn = d.getFullYear() + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0') + '_Wine Cellar Dashboard.html';
  _dlBlob(fn, src, 'text/html');
  _logChange('\u2193 Exported ' + fn);
}
function exportJSON() {
  var out = {wines: WINES, consumed: CONSUMED};
  _dlBlob('wines.json', JSON.stringify(out, null, 2), 'application/json');
  _logChange('\u2193 Exported wines.json');
}
function _dlBlob(filename, content, type) {
  var blob = new Blob([content], {type: type});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

// ── SCAN LABEL (client-side Gemini Vision)
window._scanPending = null;

function _scanKey() {
  try { return localStorage.getItem('gemini_api_key') || ''; } catch(e) { return ''; }
}
function _updateKeyStatus() {
  var k = _scanKey();
  var el = document.getElementById('keyStatusLine');
  var btn = document.getElementById('scanBtn');
  if (el) { el.textContent = k ? '✓ API key set' : 'No API key'; el.style.color = k ? '#4caf7a' : 'var(--muted)'; }
  if (btn) btn.disabled = !k;
}
function toggleKeyArea() {
  var el = document.getElementById('keyArea');
  if (!el) return;
  var showing = el.style.display !== 'none';
  el.style.display = showing ? 'none' : 'block';
  if (!showing) { var ki = document.getElementById('keyInput'); if (ki) ki.focus(); }
}
function saveKey() {
  var val = (document.getElementById('keyInput') || {}).value || '';
  val = val.trim();
  if (!val) return;
  try { localStorage.setItem('gemini_api_key', val); } catch(e) {}
  document.getElementById('keyInput').value = '';
  document.getElementById('keyArea').style.display = 'none';
  _updateKeyStatus();
}
function clearKey() {
  try { localStorage.removeItem('gemini_api_key'); } catch(e) {}
  var ki = document.getElementById('keyInput');
  if (ki) ki.value = '';
  _updateKeyStatus();
}
function scanLabel() {
  var k = _scanKey();
  if (!k) {
    toggleKeyArea();
    var ss = document.getElementById('scanStatus');
    if (ss) { ss.className = 'scan-status-line err'; ss.textContent = 'Set your Gemini API key first.'; }
    return;
  }
  var inp = document.getElementById('scanInput');
  if (inp) inp.click();
}
function handleScanFile(input) {
  var file = input.files[0];
  if (!file) return;
  var status = document.getElementById('scanStatus');
  var btn = document.getElementById('scanBtn');
  status.className = 'scan-status-line';
  status.innerHTML = '<span class="spin"></span> Identifying wine…';
  btn.disabled = true;
  var reader = new FileReader();
  reader.onload = function(e) {
    var b64 = e.target.result.split(',')[1];
    var mime = file.type || 'image/jpeg';
    _callGeminiVision(b64, mime, status, btn);
  };
  reader.readAsDataURL(file);
  input.value = '';
}
function _callGeminiVision(b64, mime, status, btn) {
  var key = _scanKey();
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=' + key;
  var prompt = 'You are a wine expert examining a wine bottle label photo.\n\nExtract every detail you can identify from the label. Then, using your wine knowledge, fill in the remaining fields needed for a wine cellar database.\n\nReturn ONLY a JSON object with these exact fields (no markdown, no explanation):\n{"producer":"...","wine":"...","appellation":"...","country":"...","region":"...","vintage":2023,"varietal":"...","style":"red","purchasePrice":null,"marketPrice":25,"score":88,"drinkFrom":2024,"drinkTo":2030,"pairings":["food1","food2","food3"],"summary":"2-3 sentence tasting note and context."}\n\nRules:\n- vintage must be an integer year, or the string NV for non-vintage\n- style must be one of: red, white, sparkling, ros\u00e9, dessert, orange\n- marketPrice is your best estimate of current US retail price in USD\n- score is your best estimate of critic consensus (Wine Advocate, Wine Spectator)\n- drinkFrom and drinkTo are drinking window years\n- pairings should be 3 specific food pairings\n- summary should mention the producer, vintage character, and what to expect\n- purchasePrice should always be null\n- If you cannot identify the wine at all, set producer to null';
  var body = JSON.stringify({ contents: [{ parts: [
    { inline_data: { mime_type: mime, data: b64 } },
    { text: prompt }
  ]}]});
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) throw new Error(data.error.message || 'API error');
      var candidates = data.candidates || [];
      var content = (candidates[0] || {}).content || {};
      var parts = content.parts || [];
      var text = ((parts[0] || {}).text || '').trim();
      if (text.indexOf('```') === 0) {
        text = text.split('\n').slice(1).join('\n');
        text = text.replace(/```\s*$/, '').trim();
      }
      var wine = JSON.parse(text);
      if (!wine.producer) throw new Error('Could not identify wine from this image');
      _fillFormFromScan(wine);
      status.className = 'scan-status-line ok';
      status.textContent = '✓ Wine identified — review fields below, then add to collection or log as a tasting';
      btn.disabled = false;
    })
    .catch(function(err) {
      status.className = 'scan-status-line err';
      status.textContent = 'Scan failed: ' + err.message;
      btn.disabled = false;
    });
}
function _fillFormFromScan(w) {
  function setVal(id, val) { var el = document.getElementById(id); if (el && val != null) el.value = val; }
  setVal('f-producer', w.producer || '');
  setVal('f-wine', w.wine || '');
  setVal('f-appellation', w.appellation || '');
  setVal('f-varietal', w.varietal || '');
  setVal('f-region', w.region || '');
  setVal('f-vintage', typeof w.vintage === 'number' ? w.vintage : '');
  setVal('f-market', w.marketPrice || '');
  setVal('f-score', w.score || '');
  setVal('f-from', w.drinkFrom || '');
  setVal('f-to', w.drinkTo || '');
  var cEl = document.getElementById('f-country');
  if (cEl && w.country) {
    for (var i = 0; i < cEl.options.length; i++) {
      if (cEl.options[i].value === w.country || cEl.options[i].text === w.country) { cEl.selectedIndex = i; break; }
    }
  }
  var sEl = document.getElementById('f-style');
  if (sEl && w.style) sEl.value = w.style;
  window._scanPending = { pairings: w.pairings || [], summary: w.summary || '' };
}
function openScanDrawer() {
  openDrawer();
  var tabs = document.querySelectorAll('.drawer-tab');
  if (tabs[1]) switchEditTab('add', tabs[1]);
}
_updateKeyStatus();
