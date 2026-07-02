const $ = (s, e=document) => e.querySelector(s);
const $$ = (s, e=document) => [...e.querySelectorAll(s)];
const state = { project:null, scope:["I.1","I.2","I.3","I.4","I.5"], rooms:[], activeRoom:null };
let roomSeq = 0;

function toast(msg, kind=""){
  const t = document.createElement("div"); t.className="t "+kind; t.textContent=msg;
  $("#toast").appendChild(t); setTimeout(()=>t.remove(), 4200);
}
function gotoStep(n){
  $$(".step").forEach(s=>s.classList.toggle("active", s.dataset.step==n));
  $$(".panel").forEach(p=>p.classList.toggle("active", p.id=="panel-"+n));
  window.scrollTo({top:0,behavior:"smooth"});
}
$$(".step").forEach(s=>s.onclick=()=>gotoStep(s.dataset.step));

// ---- scope chips ----
fetch("/api/catalog").then(r=>r.json()).then(d=>{
  const box=$("#scope");
  d.groups.forEach(g=>{
    const c=document.createElement("div");
    c.className="chip"+(state.scope.includes(g.ma)?" on":"");
    c.textContent=g.ma+" "+g.ten; c.dataset.ma=g.ma;
    c.onclick=()=>{ c.classList.toggle("on");
      state.scope = $$("#scope .chip.on").map(x=>x.dataset.ma); };
    box.appendChild(c);
  });
});

// ---- rooms editor (step 1) ----
function addRoom(ma="GR1", ten="KING 1", sl=5){
  const id="r"+(roomSeq++);
  state.rooms.push({id, file:null});
  const tr=document.createElement("tr"); tr.dataset.id=id;
  tr.innerHTML=`<td><input class="ma" value="${ma}" style="width:80px"></td>
    <td><input class="ten" value="${ten}"></td>
    <td><input class="sl" type="number" value="${sl}" style="width:70px"></td>
    <td><input class="pdf" type="file" accept="application/pdf"></td>
    <td><button class="danger" title="Xóa">×</button></td>`;
  tr.querySelector(".danger").onclick=()=>{ tr.remove();
    state.rooms=state.rooms.filter(r=>r.id!=id); };
  tr.querySelector(".pdf").onchange=e=>{
    const r=state.rooms.find(x=>x.id==id); r.file=e.target.files[0]||null; };
  $("#rooms").appendChild(tr);
}
$("#addRoom").onclick=()=>addRoom("", "", 1);
addRoom();

// ---- save project + uploads ----
$("#saveProject").onclick=async()=>{
  const btn=$("#saveProject"); btn.disabled=true;
  try{
    const phong=$$("#rooms tr").map(tr=>({
      ma: tr.querySelector(".ma").value.trim(),
      ten: tr.querySelector(".ten").value.trim(),
      so_luong: parseInt(tr.querySelector(".sl").value)||1,
      _id: tr.dataset.id,
    })).filter(p=>p.ma);
    if(!phong.length){ toast("Thêm ít nhất 1 loại phòng","err"); btn.disabled=false; return; }

    const cfg={
      du_an:$("#du_an").value, dia_diem:$("#dia_diem").value, hang_muc:$("#hang_muc").value,
      profit_percent:parseFloat($("#profit").value)||10,
      vat_percent:parseFloat($("#vat").value)||8,
      preliminaries_lumpsum:parseFloat($("#prelim").value)||0,
      scope:state.scope, phong:phong.map(({_id,...p})=>p),
    };
    const res=await (await fetch("/api/project",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(cfg)})).json();
    state.project=res.project;

    // upload PDFs
    for(const p of phong){
      const r=state.rooms.find(x=>x.id==p._id);
      if(r&&r.file){
        const fd=new FormData(); fd.append("project",state.project);
        fd.append("ma",p.ma); fd.append("pdf",r.file);
        await fetch("/api/upload",{method:"POST",body:fd});
        p._uploaded=true;
      }
    }
    state.phong=phong;
    toast("Đã lưu dự án ✓","ok");
    buildRoomTabs();
    $$(".step")[0].classList.add("done");
    gotoStep(2);
  }catch(e){ toast("Lỗi: "+e,"err"); }
  btn.disabled=false;
};

// ---- step 2: room tabs + takeoff ----
function buildRoomTabs(){
  const tabs=$("#roomTabs"); tabs.innerHTML="";
  state.phong.forEach((p,i)=>{
    const b=document.createElement("button");
    b.className="tab"+(i==0?" active":"");
    b.innerHTML=`${p.ma} · ${p.ten}<span class="dot" data-ma="${p.ma}"></span>`;
    b.onclick=()=>{ $$(".tab").forEach(t=>t.classList.remove("active"));
      b.classList.add("active"); openRoom(p); };
    tabs.appendChild(b);
  });
  if(state.phong[0]) openRoom(state.phong[0]);
}

function openRoom(p){
  state.activeRoom=p;
  const area=$("#boqArea");
  const hasPdf=p._uploaded;
  area.innerHTML=`
    <div class="grid2">
      <div>
        <button class="primary" id="runTakeoff" ${hasPdf?"":"disabled"}>
          🤖 Bóc khối lượng phòng ${p.ma} bằng AI</button>
        ${hasPdf?"":'<p class="hint">Chưa có PDF cho phòng này (quay lại bước 1 để tải).</p>'}
        <div class="usage" id="usage"></div>
      </div>
      <div>${hasPdf?`<embed src="/api/pdf/${state.project}/${enc(p.ma)}" type="application/pdf" width="100%" height="240">`:""}</div>
    </div>
    <div id="boqTable"></div>`;
  const rt=$("#runTakeoff"); if(rt) rt.onclick=()=>runTakeoff(p);
  loadBoq(p);
}
const enc = s => encodeURIComponent(s);

async function loadBoq(p){
  const d=await (await fetch(`/api/boq?project=${enc(state.project)}&ma=${enc(p.ma)}`)).json();
  if(d.rows&&d.rows.length) renderBoq(p, d.rows);
}

async function runTakeoff(p){
  const btn=$("#runTakeoff"); btn.disabled=true;
  btn.innerHTML='<span class="spin"></span>AI đang đọc bản vẽ… (có thể mất 1-3 phút)';
  try{
    const body={project:state.project, room:p, scope:state.scope,
      model:$("#model").value, api_key:$("#api_key").value};
    const d=await (await fetch("/api/takeoff",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})).json();
    if(!d.ok){ toast(d.error,"err"); }
    else{
      renderBoq(p, d.rows);
      $("#usage").textContent=`Token: ${d.usage.input.toLocaleString()} vào / ${d.usage.output.toLocaleString()} ra`;
      $(`.dot[data-ma="${p.ma}"]`)?.classList.add("ready");
      toast(`Đã bóc ${d.rows.length} hạng mục cho ${p.ma} ✓`,"ok");
    }
  }catch(e){ toast("Lỗi: "+e,"err"); }
  btn.disabled=false; btn.textContent=`🤖 Bóc lại phòng ${p.ma} bằng AI`;
}

function renderBoq(p, rows){
  const cols=[["hang_muc","Hạng mục"],["quy_cach","Quy cách"],["don_vi","ĐVT"],
    ["kl_1phong","KL 1 phòng"],["don_gia_ncc","Đơn giá NCC"],["do_tin_cay","Tin cậy"],["ghi_chu","Ghi chú"]];
  let h=`<table class="boq"><thead><tr><th>STT</th>${cols.map(c=>`<th>${c[1]}</th>`).join("")}</tr></thead><tbody>`;
  let lastGrp=null, stt=0;
  rows.forEach(r=>{
    if(r.nhom_ma!==lastGrp){ lastGrp=r.nhom_ma;
      h+=`<tr class="grp"><td></td><td colspan="${cols.length}">${r.nhom_ma} · ${r.nhom_ten||""}</td></tr>`; }
    stt++;
    h+=`<tr data-nhom="${attr(r.nhom_ma)}" data-nten="${attr(r.nhom_ten)}"><td>${stt}</td>`+
      cols.map(c=>{
        const v=attr(r[c[0]]??"");
        if(c[0]=="do_tin_cay") return `<td><select data-k="do_tin_cay" class="tc-${r[c[0]]||'cao'}">
          ${["cao","trung_binh","thap"].map(o=>`<option ${o==r[c[0]]?"selected":""}>${o}</option>`).join("")}</select></td>`;
        const num=(c[0]=="kl_1phong"||c[0]=="don_gia_ncc")?" num":"";
        return `<td class="${num.trim()}"><input data-k="${c[0]}" value="${v}"></td>`;
      }).join("")+`</tr>`;
  });
  h+=`</tbody></table>
    <div class="actions"><button class="mini" id="saveBoq">💾 Lưu bảng khối lượng</button></div>`;
  $("#boqTable").innerHTML=h;
  $("#boqTable select").forEach(s=>s.onchange=()=>s.className="tc-"+s.value);
  $("#saveBoq").onclick=()=>saveBoq(p);
}
const attr = s => String(s).replace(/"/g,"&quot;");

async function saveBoq(p){
  const rows=$$("#boqTable tbody tr").filter(tr=>!tr.classList.contains("grp")).map(tr=>{
    const o={nhom_ma:tr.dataset.nhom, nhom_ten:tr.dataset.nten};
    tr.querySelectorAll("[data-k]").forEach(el=>o[el.dataset.k]=el.value);
    return o;
  });
  await fetch("/api/boq",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({project:state.project,ma:p.ma,rows})});
  toast("Đã lưu khối lượng ✓","ok");
}

// ---- step 3: mời thầu ----
$("#buildMoiThau").onclick=async()=>{
  if(!state.project){ toast("Tạo dự án ở bước 1 trước","err"); return; }
  const b=$("#buildMoiThau"); b.disabled=true;
  const d=await (await fetch("/api/moi-thau",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({project:state.project})})).json();
  $("#moiThauOut").innerHTML = d.ok
    ? `<a class="dl" href="${d.download}">⬇ Tải moi-thau.xlsx</a><pre class="log">${esc(d.log)}</pre>`
    : `<pre class="log">${esc(d.error)}</pre>`;
  b.disabled=false;
};

// ---- step 4: báo giá ----
$("#buildBaoGia").onclick=async()=>{
  if(!state.project){ toast("Tạo dự án ở bước 1 trước","err"); return; }
  const b=$("#buildBaoGia"); b.disabled=true;
  const d=await (await fetch("/api/bao-gia",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({project:state.project, profit_percent:$("#profit").value,
      vat_percent:$("#vat").value, preliminaries_lumpsum:$("#prelim").value})})).json();
  $("#baoGiaOut").innerHTML = d.ok
    ? `<a class="dl" href="${d.download}">⬇ Tải bao-gia-noi-bo.xlsx</a><pre class="log">${esc(d.log)}</pre>`
    : `<pre class="log">${esc(d.error)}</pre>`;
  b.disabled=false;
};
const esc = s => String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
