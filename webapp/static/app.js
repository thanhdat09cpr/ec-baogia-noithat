const $ = (s, e=document) => e.querySelector(s);
const $$ = (s, e=document) => [...e.querySelectorAll(s)];
const enc = s => encodeURIComponent(s);
const attr = s => String(s).replace(/"/g, "&quot;");
const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const state = { project_id:null, scope:["I.1","I.2","I.3","I.4","I.5"], rooms:[], phong:[], activeRoom:null };
let roomSeq = 0;

// nhãn trạng thái dự án
const STATUS = {
  draft:      {t:"Nháp",         c:"neut"},
  takeoff:    {t:"Đang bóc",     c:"acc"},
  awaiting_ncc:{t:"Chờ giá NCC", c:"warn"},
  quoted:     {t:"Đã có báo giá",c:"good"},
};

function toast(msg, kind=""){
  const t = document.createElement("div"); t.className = "t " + kind; t.textContent = msg;
  $("#toast").appendChild(t); setTimeout(() => t.remove(), 4200);
}
async function postJSON(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  return r.json();
}
// parse số kiểu VN "2.500.000" -> 2500000 ; "12,5" -> 12.5 (chỉ để hiển thị đơn giá bán)
function parseVN(s){
  s = String(s ?? "").trim().replace(/\s/g, "");
  if(!s) return NaN;
  if(/^\d{1,3}([.,]\d{3})+$/.test(s)) return parseFloat(s.replace(/[.,]/g, ""));
  return parseFloat(s.replace(/\./g, "").replace(",", "."));
}
const fmtVN = n => isNaN(n) ? "—" : Math.round(n).toLocaleString("vi-VN");

// ---------------- views ----------------
function showView(name){
  $$(".view").forEach(v => v.classList.toggle("on", v.id === name));
  $("#navProjects").classList.toggle("on", name === "dashboard");
  $("#navNew").classList.toggle("on", name === "wizard");
  if(name === "dashboard"){ $("#crumb").innerHTML = "<b>Dự án của tôi</b>"; loadProjects(); }
  window.scrollTo({top:0, behavior:"smooth"});
}
function gotoStep(n){
  $$("#stepper button").forEach(b => b.classList.toggle("on", b.dataset.w == n));
  $$(".wz").forEach(w => w.classList.toggle("on", w.dataset.wz == n));
  if(n == 4) buildRoomTabs("#priceTabs", "#priceArea", true);
  window.scrollTo({top:0, behavior:"smooth"});
}
$("#stepper").addEventListener("click", e => {
  const b = e.target.closest("button[data-w]"); if(b) gotoStep(b.dataset.w);
});
$("#navProjects").onclick = () => showView("dashboard");
$("#navNew").onclick = () => resetWizard();
$("#newProjectBtn").onclick = () => resetWizard();

// ---------------- dashboard ----------------
async function loadProjects(){
  const d = await (await fetch("/api/projects")).json();
  const ps = d.projects || [];
  $("#statTotal").textContent = ps.length;
  $("#statActive").textContent = ps.filter(p => p.status==="draft"||p.status==="takeoff").length;
  $("#statAwaiting").textContent = ps.filter(p => p.status==="awaiting_ncc").length;
  $("#statQuoted").textContent = ps.filter(p => p.status==="quoted").length;
  const tb = $("#projRows"); tb.innerHTML = "";
  if(!ps.length){
    tb.innerHTML = '<tr><td colspan="4" class="muted" style="padding:22px;text-align:center">Chưa có dự án. Bấm “Tạo báo giá mới”.</td></tr>';
    return;
  }
  ps.forEach(p => {
    const s = STATUS[p.status] || STATUS.draft;
    const when = p.updated_at ? new Date(p.updated_at).toLocaleString("vi-VN") : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><span class="rowlink">${esc(p.ten)}<small>${esc(p.dia_diem||"")}</small></span></td>
      <td><span class="chip ${s.c}"><span class="dot" style="background:currentColor;opacity:.6"></span> ${s.t}</span></td>
      <td class="muted">${esc(when)}</td>
      <td style="text-align:right"><button class="btn ghost sm">Mở →</button></td>`;
    tr.querySelector("button").onclick = () => openProject(p.id);
    tb.appendChild(tr);
  });
}

async function openProject(id){
  const d = await (await fetch(`/api/project/${enc(id)}`)).json();
  if(!d.ok){ toast("Không mở được dự án", "err"); return; }
  const c = d.config || {};
  state.project_id = id;
  state.scope = c.scope || state.scope;
  $("#du_an").value = c.du_an || d.ten || "";
  $("#dia_diem").value = c.dia_diem || "";
  $("#hang_muc").value = c.hang_muc || "";
  $("#profit").value = c.profit_percent ?? 10;
  $("#vat").value = c.vat_percent ?? 8;
  $("#prelim").value = c.preliminaries_lumpsum ?? 0;
  state.phong = (c.phong || []).map(p => ({...p, _uploaded:true}));
  renderScope();
  $("#crumb").innerHTML = `Dự án của tôi / <b>${esc(state.phong.length ? (c.du_an||d.ten) : (c.du_an||d.ten))}</b>`;
  showViewWizard();
  buildRoomTabs("#roomTabs", "#boqArea", false);
  gotoStep(2);
}

function showViewWizard(){
  $$(".view").forEach(v => v.classList.toggle("on", v.id === "wizard"));
  $("#navProjects").classList.remove("on"); $("#navNew").classList.add("on");
}

function resetWizard(){
  state.project_id = null; state.phong = []; state.rooms = []; roomSeq = 0;
  $("#rooms").innerHTML = "";
  $("#du_an").value = ""; $("#dia_diem").value = ""; $("#hang_muc").value = "";
  addRoom();
  renderScope();
  $("#crumb").innerHTML = "Dự án của tôi / <b>Dự án mới</b>";
  showViewWizard();
  gotoStep(1);
}

// ---------------- scope chips ----------------
let CATALOG_GROUPS = [];
fetch("/api/catalog").then(r => r.json()).then(d => { CATALOG_GROUPS = d.groups || []; renderScope(); });
function renderScope(){
  const box = $("#scope"); if(!box) return; box.innerHTML = "";
  CATALOG_GROUPS.forEach(g => {
    const c = document.createElement("span");
    c.className = "schip" + (state.scope.includes(g.ma) ? " on" : "");
    c.textContent = g.ma + " " + g.ten; c.dataset.ma = g.ma;
    c.onclick = () => { c.classList.toggle("on"); state.scope = $$("#scope .schip.on").map(x => x.dataset.ma); };
    box.appendChild(c);
  });
}

// ---------------- rooms editor (step 1) ----------------
function addRoom(ma="GR1", ten="Superior King", sl=5){
  const id = "r" + (roomSeq++);
  state.rooms.push({id, file:null});
  const tr = document.createElement("tr"); tr.dataset.id = id;
  tr.innerHTML = `<td><input class="ma mono" value="${attr(ma)}" style="width:80px"></td>
    <td><input class="ten" value="${attr(ten)}"></td>
    <td><input class="sl" type="number" value="${sl}" style="width:64px"></td>
    <td><input class="pdf" type="file" accept="application/pdf"></td>
    <td style="text-align:right"><button class="btn ghost sm danger">×</button></td>`;
  tr.querySelector(".danger").onclick = () => { tr.remove(); state.rooms = state.rooms.filter(r => r.id != id); };
  tr.querySelector(".pdf").onchange = e => { const r = state.rooms.find(x => x.id == id); r.file = e.target.files[0] || null; };
  $("#rooms").appendChild(tr);
}
$("#addRoom").onclick = () => addRoom("", "", 1);

// ---------------- save project + uploads (step 1) ----------------
$("#saveProject").onclick = async () => {
  const btn = $("#saveProject"); btn.disabled = true;
  try{
    const phong = $$("#rooms tr").map(tr => ({
      ma: tr.querySelector(".ma").value.trim(),
      ten: tr.querySelector(".ten").value.trim(),
      so_luong: parseInt(tr.querySelector(".sl").value) || 1,
      _id: tr.dataset.id,
    })).filter(p => p.ma);
    if(!phong.length){ toast("Thêm ít nhất 1 loại phòng", "err"); btn.disabled = false; return; }

    const cfg = {
      du_an:$("#du_an").value, dia_diem:$("#dia_diem").value, hang_muc:$("#hang_muc").value,
      profit_percent: parseFloat($("#profit").value) || 10,
      vat_percent: parseFloat($("#vat").value) || 8,
      preliminaries_lumpsum: parseFloat($("#prelim").value) || 0,
      scope: state.scope, phong: phong.map(({_id, ...p}) => p),
    };
    const res = await postJSON("/api/project", cfg);
    state.project_id = res.project_id;

    for(const p of phong){
      const r = state.rooms.find(x => x.id == p._id);
      if(r && r.file){
        const fd = new FormData();
        fd.append("project_id", state.project_id); fd.append("ma", p.ma); fd.append("pdf", r.file);
        await fetch("/api/upload", {method:"POST", body:fd});
        p._uploaded = true;
      }
    }
    state.phong = phong;
    $("#crumb").innerHTML = `Dự án của tôi / <b>${esc(cfg.du_an)}</b>`;
    toast("Đã lưu dự án ✓", "ok");
    buildRoomTabs("#roomTabs", "#boqArea", false);
    $("#stepper button[data-w='1']").classList.add("done");
    gotoStep(2);
  }catch(e){ toast("Lỗi: " + e, "err"); }
  btn.disabled = false;
};

// ---------------- room tabs (step 2 = full, step 4 = price) ----------------
function buildRoomTabs(tabsSel, areaSel, priceMode){
  const tabs = $(tabsSel); if(!tabs) return; tabs.innerHTML = "";
  if(!state.phong.length){ $(areaSel).innerHTML = '<p class="hint">Chưa có loại phòng (thêm ở bước 1).</p>'; return; }
  state.phong.forEach((p, i) => {
    const b = document.createElement("button");
    b.className = i == 0 ? "on" : "";
    b.innerHTML = `${esc(p.ma)} · ${esc(p.ten)}<span class="dot" data-ma="${attr(p.ma)}"></span>`;
    b.onclick = () => { $$("button", tabs).forEach(t => t.classList.remove("on")); b.classList.add("on"); openRoom(p, areaSel, priceMode); };
    tabs.appendChild(b);
  });
  openRoom(state.phong[0], areaSel, priceMode);
}

function openRoom(p, areaSel, priceMode){
  state.activeRoom = p;
  const area = $(areaSel);
  if(priceMode){
    area.innerHTML = `<div class="card tbl-wrap" id="priceMount"></div>`;
    loadBoq(p, $("#priceMount"), true);
    return;
  }
  const hasPdf = p._uploaded;
  area.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 300px;gap:16px;align-items:start">
      <div>
        <button class="btn" id="runTakeoff" ${hasPdf ? "" : "disabled"}>🤖 Bóc khối lượng phòng ${esc(p.ma)}</button>
        ${hasPdf ? "" : '<p class="hint" style="margin-top:8px">Chưa có PDF cho phòng này (quay lại bước 1 để tải).</p>'}
        <div class="usage" id="usage"></div>
      </div>
      <div>${hasPdf ? `<embed src="/api/pdf/${enc(state.project_id)}/${enc(p.ma)}" type="application/pdf" width="100%" height="260" style="border:1px solid var(--line);border-radius:8px">` : ""}</div>
    </div>
    <div class="card tbl-wrap" id="boqMount" style="margin-top:16px"></div>`;
  const rt = $("#runTakeoff"); if(rt) rt.onclick = () => runTakeoff(p);
  loadBoq(p, $("#boqMount"), false);
}

async function loadBoq(p, mount, priceMode){
  const d = await (await fetch(`/api/boq?project_id=${enc(state.project_id)}&ma=${enc(p.ma)}`)).json();
  if(d.rows && d.rows.length) renderBoq(p, d.rows, mount, priceMode);
  else mount.innerHTML = '<p class="hint" style="padding:16px">Chưa có khối lượng. Bóc ở bước 2 trước.</p>';
}

// ---------------- takeoff (async job + polling) ----------------
function runTakeoff(p){
  const btn = $("#runTakeoff"); btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>AI đang đọc bản vẽ… (1-3 phút)';
  const done = (label) => { btn.disabled = false; btn.textContent = label; };
  postJSON("/api/takeoff", {project_id:state.project_id, room:p, scope:state.scope}).then(d => {
    if(!d.ok){ toast(d.error, "err"); done(`🤖 Bóc khối lượng phòng ${p.ma}`); return; }
    if(!d.created) toast("Phòng này đang được bóc, tiếp tục theo dõi…");
    pollJob(d.job_id, p, done);
  }).catch(e => { toast("Lỗi: " + e, "err"); done(`🤖 Bóc khối lượng phòng ${p.ma}`); });
}
function pollJob(jobId, p, done){
  const iv = setInterval(async () => {
    let s; try{ s = await (await fetch(`/api/takeoff/status/${enc(jobId)}`)).json(); }catch(e){ return; }
    if(s.status === "done"){
      clearInterval(iv);
      renderBoq(p, s.rows || [], $("#boqMount"), false);
      if(s.usage) $("#usage").textContent = `Token: ${(s.usage.input||0).toLocaleString()} vào / ${(s.usage.output||0).toLocaleString()} ra`;
      $(`.dot[data-ma="${attr(p.ma)}"]`)?.classList.add("ready");
      toast(`Đã bóc ${(s.rows||[]).length} hạng mục cho ${p.ma} ✓`, "ok");
      done(`🤖 Bóc lại phòng ${p.ma}`);
    } else if(s.status === "error"){
      clearInterval(iv); toast(s.error || "Bóc khối lượng lỗi.", "err"); done(`🤖 Bóc lại phòng ${p.ma}`);
    }
  }, 2000);
}

// ---------------- BOQ table ----------------
function renderBoq(p, rows, mount, priceMode){
  const globalProfit = parseFloat($("#profit").value) || 0;
  let h, lastGrp = null;
  if(priceMode){
    h = `<table class="boq"><thead><tr><th>Hạng mục</th><th>ĐVT</th><th style="text-align:right">KL</th>
      <th style="text-align:right">Đơn giá NCC</th><th style="text-align:right">Lợi nhuận %</th><th style="text-align:right">Đơn giá bán</th></tr></thead><tbody>`;
  } else {
    h = `<table class="boq"><thead><tr><th>Hạng mục</th><th>Quy cách</th><th>ĐVT</th>
      <th style="text-align:right">Khối lượng</th><th>Độ tin</th><th>Minh họa</th></tr></thead><tbody>`;
  }
  rows.forEach(r => {
    if(r.nhom_ma !== lastGrp){ lastGrp = r.nhom_ma;
      h += `<tr class="grp"><td colspan="6">${esc(r.nhom_ma)} · ${esc((r.nhom_ten||"").toUpperCase())}</td></tr>`; }
    const base = `data-nhom="${attr(r.nhom_ma)}" data-nten="${attr(r.nhom_ten)}"`;
    if(priceMode){
      const noPrice = !String(r.don_gia_ncc||"").trim();
      const prof = String(r.profit_override||"").trim() !== "" ? parseFloat(r.profit_override) : globalProfit;
      const sell = noPrice ? NaN : parseVN(r.don_gia_ncc) * (1 + prof/100);
      h += `<tr ${base}>
        <td class="locked">${esc(r.hang_muc||"")}${r.quy_cach?`<small>${esc(r.quy_cach)}</small>`:""}</td>
        <td>${esc(r.don_vi||"")}</td>
        <td class="qty">${esc(r.kl_1phong||"")}</td>
        <td class="qty ${noPrice?"price-empty":"price-cell"}"><input data-k="don_gia_ncc" value="${attr(r.don_gia_ncc||"")}" placeholder="chưa có giá"></td>
        <td class="qty"><input data-k="profit_override" value="${attr(r.profit_override||"")}" placeholder="${globalProfit}" style="width:70px"></td>
        <td class="sell">${fmtVN(sell)}</td></tr>`;
    } else {
      const tc = r.do_tin_cay || "cao";
      h += `<tr ${base}>
        <td class="locked"><input data-k="hang_muc" value="${attr(r.hang_muc||"")}"></td>
        <td><input data-k="quy_cach" value="${attr(r.quy_cach||"")}"></td>
        <td><input data-k="don_vi" value="${attr(r.don_vi||"")}" style="width:70px"></td>
        <td class="qty qty-cell"><input data-k="kl_1phong" value="${attr(r.kl_1phong||"")}"></td>
        <td><select data-k="do_tin_cay" class="tc-${tc}">
          ${["cao","trung_binh","thap"].map(o=>`<option ${o==tc?"selected":""}>${o}</option>`).join("")}</select></td>
        <td><span class="chip neut">ảnh</span></td></tr>`;
    }
  });
  h += `</tbody></table>`;
  mount.innerHTML = h;
  // gỡ thanh nút cũ (nếu render lại) rồi chèn mới ngay sau bảng
  if(mount.nextElementSibling && mount.nextElementSibling.classList.contains("actions"))
    mount.nextElementSibling.remove();
  const wrap = document.createElement("div"); wrap.className = "actions";
  wrap.innerHTML = `<button class="btn ghost" data-save="1">💾 Lưu ${priceMode?"giá":"khối lượng"}</button>`;
  mount.after(wrap);
  $$("select", mount).forEach(s => s.onchange = () => s.className = "tc-" + s.value);
  $$("input[data-k='profit_override'],input[data-k='don_gia_ncc']", mount).forEach(inp =>
    inp.oninput = () => recalcSell(inp.closest("tr")));
  wrap.querySelector("[data-save]").onclick = () => saveBoq(p, mount, priceMode);
}

function recalcSell(tr){
  const globalProfit = parseFloat($("#profit").value) || 0;
  const ncc = tr.querySelector("[data-k='don_gia_ncc']");
  const povr = tr.querySelector("[data-k='profit_override']");
  const sellCell = tr.querySelector(".sell");
  if(!ncc || !sellCell) return;
  const empty = !ncc.value.trim();
  ncc.parentElement.className = "qty " + (empty ? "price-empty" : "price-cell");
  const prof = povr && povr.value.trim() !== "" ? parseFloat(povr.value) : globalProfit;
  sellCell.textContent = empty ? "—" : fmtVN(parseVN(ncc.value) * (1 + prof/100));
}

async function saveBoq(p, mount, priceMode){
  if(priceMode){
    const cur = await (await fetch(`/api/boq?project_id=${enc(state.project_id)}&ma=${enc(p.ma)}`)).json();
    const base = cur.rows || [];
    const trs = $$("tbody tr", mount).filter(tr => !tr.classList.contains("grp"));
    base.forEach((b, i) => { const tr = trs[i]; if(!tr) return;
      tr.querySelectorAll("[data-k]").forEach(el => b[el.dataset.k] = el.value); });
    await postJSON("/api/boq", {project_id:state.project_id, ma:p.ma, rows:base});
  } else {
    const rows = $$("tbody tr", mount).filter(tr => !tr.classList.contains("grp")).map(tr => {
      const o = {nhom_ma: tr.dataset.nhom, nhom_ten: tr.dataset.nten};
      tr.querySelectorAll("[data-k]").forEach(el => o[el.dataset.k] = el.value);
      return o;
    });
    await postJSON("/api/boq", {project_id:state.project_id, ma:p.ma, rows});
  }
  toast(`Đã lưu ${priceMode?"giá":"khối lượng"} ✓`, "ok");
}

// ---------------- step 3: mời thầu ----------------
$("#buildMoiThau").onclick = async () => {
  if(!state.project_id){ toast("Tạo dự án ở bước 1 trước", "err"); return; }
  const b = $("#buildMoiThau"); b.disabled = true;
  const d = await postJSON("/api/moi-thau", {project_id:state.project_id});
  $("#moiThauOut").innerHTML = d.ok
    ? `<div class="result"><div class="file-ic">XLS</div><div><b>moi-thau.xlsx</b><div class="hint">${(d.stats?.n_rows||"")} dòng · đơn giá trống</div></div>
        <a class="dl" style="margin-left:auto" href="${d.download}">Tải về</a></div>`
    : `<pre class="log">${esc(d.error)}</pre>`;
  b.disabled = false;
};

// ---------------- step 5: báo giá ----------------
$("#buildBaoGia").onclick = async () => {
  if(!state.project_id){ toast("Tạo dự án ở bước 1 trước", "err"); return; }
  const b = $("#buildBaoGia"); b.disabled = true;
  const d = await postJSON("/api/bao-gia", {project_id:state.project_id,
    profit_percent:$("#profit").value, vat_percent:$("#vat").value, preliminaries_lumpsum:$("#prelim").value});
  $("#baoGiaOut").innerHTML = d.ok
    ? `<div class="result"><div class="file-ic">XLS</div><div><b>bao-gia-noi-bo.xlsx</b><div class="hint">Mỗi phòng 1 sheet + Tổng hợp + VAT</div></div>
        <a class="dl" style="margin-left:auto" href="${d.download}">Tải về</a></div>`
    : `<pre class="log">${esc(d.error)}</pre>`;
  b.disabled = false;
};

// ---------------- init ----------------
addRoom();
showView("dashboard");
