"""Build a standalone, sanitized HTML walkthrough from generated lab reports.

Run from src/: python scripts/build_demo.py [--benchmark ... --crash ... --out ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
DEFAULT_OUT = ROOT / "report" / "team" / "demo.html"

SCENARIOS = {
    "T01": "Đơn giao trễ 4 ngày; đủ điều kiện hoàn phí ship.",
    "T02": "Ticket nói trễ 5 ngày, đơn ghi 2 ngày.",
    "T03": "Hàng hỏng đã xác minh; tính mức bồi thường theo policy.",
    "T04": "Thiếu order_id; cần hỏi thêm thông tin.",
    "T05": "Principal không sở hữu đơn; chuyển xử lý.",
    "T06": "Ticket dẫn policy cũ; policy hiện hành không cho hoàn.",
    "T07": "Quote dương nhưng approval hết hạn; host từ chối.",
    "T08": "Approval thấp hơn quote; host giới hạn số tiền ghi.",
    "T09": "Ticket chứa lệnh bỏ qua policy; đơn không đủ điều kiện.",
    "T10": "Đơn đủ điều kiện; trace phải giữ kín dữ liệu riêng.",
    "T11": "Claim dùng cho test gọi lại; benchmark hiển thị một lượt chạy.",
    "T12": "Claim dùng cho test crash/resume; benchmark hiển thị một lượt chạy.",
    "T13": "Đơn đã được hoàn đủ từ claim trước.",
    "T14": "Hỏng hàng sau khi hoàn ship; chỉ trả phần chênh.",
}

HTML = r'''<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>LogiX-VN · Demo luồng claim</title>
  <style>
    :root { --bg:#0b1420; --panel:#122233; --panel-2:#172b3d; --line:#2a4053; --text:#ecf4f5; --muted:#a8bfca; --accent:#62dcc2; --accent-dark:#123e3d; --good:#74d9ae; --bad:#ff887f; --warn:#f5c878; }
    * { box-sizing:border-box; }
    body { margin:0; background:radial-gradient(circle at 88% 0%,#1b3e4c 0,transparent 36%),var(--bg); color:var(--text); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
    button,select { font:inherit; }
    button { cursor:pointer; }
    main { width:min(1180px,calc(100% - 32px)); margin:0 auto; padding:30px 0 52px; }
    h1,h2,h3,p { margin:0; }
    h1 { font-size:clamp(28px,4vw,44px); line-height:1.1; letter-spacing:-.04em; }
    h2 { font-size:21px; letter-spacing:-.02em; }
    h3 { font-size:16px; }
    .eyebrow { color:var(--accent); font-size:12px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
    .sub { color:var(--muted); max-width:72ch; margin-top:10px; }
    .hero { display:flex; align-items:end; justify-content:space-between; gap:20px; flex-wrap:wrap; padding:12px 0 28px; }
    .pill { border:1px solid #3a796e; color:var(--good); background:#12302f; border-radius:999px; padding:8px 14px; white-space:nowrap; font-weight:650; }
    .stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:0 0 28px; }
    .stat,.panel { background:var(--panel); border:1px solid var(--line); border-radius:16px; }
    .stat { padding:18px; }
    .stat strong { display:block; font-size:27px; line-height:1.1; margin:5px 0; font-variant-numeric:tabular-nums; }
    .stat small,.hint,.source { color:var(--muted); }
    .section-head { display:flex; justify-content:space-between; align-items:baseline; gap:10px; flex-wrap:wrap; margin:28px 0 12px; }
    .section-head p { color:var(--muted); font-size:13px; }
    .panel { padding:20px; }
    .control-row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
    label { display:block; color:var(--muted); font-size:13px; margin-bottom:5px; }
    select { width:100%; min-height:42px; color:var(--text); background:var(--panel-2); border:1px solid #3c596b; border-radius:9px; padding:8px 10px; }
    select:focus-visible,button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .case-line { margin:18px 0 14px; color:var(--muted); }
    .result-line { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .tag { display:inline-flex; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:700; letter-spacing:.02em; }
    .tag.good { color:var(--good); background:#153b37; }
    .tag.bad { color:var(--bad); background:#482d34; }
    .tag.neutral { color:#c4dce5; background:#294253; }
    .run-id { font:12px ui-monospace,SFMono-Regular,Consolas,monospace; color:var(--muted); overflow-wrap:anywhere; }
    .outcome-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:18px; }
    .mini { background:var(--panel-2); border-radius:10px; padding:11px 13px; min-width:0; }
    .mini span { display:block; color:var(--muted); font-size:12px; }
    .mini strong { display:block; font-size:17px; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
    .flow { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; list-style:none; padding:0; margin:18px 0 0; }
    .flow li { position:relative; min-height:118px; padding:14px; background:var(--panel-2); border:1px solid var(--line); border-radius:11px; }
    .flow li:not(:last-child)::after { content:"→"; position:absolute; right:-14px; top:45%; z-index:1; color:var(--accent); background:var(--panel); border-radius:50%; width:18px; text-align:center; }
    .flow .num { display:block; color:var(--accent); font-size:12px; font-weight:800; margin-bottom:9px; }
    .flow b { display:block; font-size:13px; line-height:1.25; }
    .flow small { display:block; color:var(--muted); margin-top:5px; font-size:12px; line-height:1.35; }
    .note { margin-top:14px; padding:12px 14px; background:#263943; border-left:3px solid var(--warn); border-radius:5px; color:#e6e8db; }
    .matrix { display:grid; grid-template-columns:110px repeat(5,minmax(0,1fr)); gap:7px; align-items:stretch; }
    .matrix .head { color:var(--muted); font-size:12px; text-align:center; padding:4px; }
    .matrix .row-name { display:flex; align-items:center; font-weight:650; font-size:13px; }
    .cell { border:1px solid transparent; border-radius:9px; min-height:48px; color:var(--text); font-size:12px; font-weight:700; }
    .cell.good { background:#194d44; }
    .cell.bad { background:#69413c; }
    .cell.selected { outline:2px solid var(--accent); outline-offset:1px; }
    .cell:hover { filter:brightness(1.18); }
    .table-wrap { overflow-x:auto; }
    table { width:100%; border-collapse:collapse; min-width:690px; }
    th,td { text-align:left; padding:12px 10px; border-bottom:1px solid var(--line); }
    th { color:var(--muted); font-size:12px; font-weight:650; white-space:nowrap; }
    td { font-variant-numeric:tabular-nums; }
    tbody tr:last-child td { border-bottom:0; }
    tbody tr.chosen { background:#193c40; }
    .bar { height:8px; width:86px; background:#294350; border-radius:99px; overflow:hidden; display:inline-block; margin-right:8px; vertical-align:middle; }
    .bar i { height:100%; display:block; background:var(--accent); }
    .bar i.imperfect { background:var(--warn); }
    .legend { margin-top:12px; color:var(--muted); font-size:12px; }
    .delta-good { color:var(--good); }
    .delta-warn { color:var(--warn); }
    footer { border-top:1px solid var(--line); margin-top:30px; padding-top:18px; color:var(--muted); font-size:12px; }
    code { color:#b8f0df; }
    @media(max-width:790px) { .stats { grid-template-columns:repeat(2,1fr); } .flow { grid-template-columns:1fr; } .flow li { min-height:auto; } .flow li:not(:last-child)::after { content:"↓"; top:auto; bottom:-16px; right:50%; } .outcome-grid { grid-template-columns:repeat(2,1fr); } }
    @media(max-width:540px) { main { width:min(100% - 20px,1180px); } .control-row { grid-template-columns:1fr; } .matrix { grid-template-columns:83px repeat(5,minmax(0,1fr)); gap:4px; } .cell { min-height:43px; font-size:11px; } .row-name { overflow-wrap:anywhere; } .stat { padding:13px; } .stat strong { font-size:23px; } }
  </style>
</head>
<body>
<main>
  <header class="hero">
    <div><div class="eyebrow">LogiX-VN · Lab 8</div><h1>Từ workflow đến agent</h1><p class="sub">Xem một claim đi qua bốn shape, so kết quả theo seed, và đối chiếu với benchmark cùng crash suite đã chạy.</p></div>
    <div class="pill" id="crash-pill">Crash safety</div>
  </header>

  <section class="stats" aria-label="Tổng quan benchmark">
    <div class="stat"><small>Corpus</small><strong id="claim-count">—</strong><small>claim public</small></div>
    <div class="stat"><small>Benchmark</small><strong id="trial-count">—</strong><small>lượt chạy · 4 shape × 5 seed</small></div>
    <div class="stat"><small>Shape nhóm chọn</small><strong id="chosen-name">—</strong><small id="chosen-score">—</small></div>
    <div class="stat"><small id="chosen-pass5-label">Pass⁵</small><strong id="chosen-pass5">—</strong><small>tỉ lệ claim pass cả 5 seed</small></div>
  </section>

  <section aria-labelledby="inspect-title">
    <div class="section-head"><h2 id="inspect-title">Một lần chạy</h2><p>Chọn claim, shape và seed để xem kết quả đã ghi trong benchmark.</p></div>
    <div class="panel">
      <div class="control-row">
        <div><label for="claim-select">Claim / tình huống</label><select id="claim-select"></select></div>
        <div><label for="shape-select">Shape</label><select id="shape-select"></select></div>
        <div><label for="seed-select">Seed</label><select id="seed-select"></select></div>
      </div>
      <p class="case-line" id="case-line"></p>
      <div class="result-line" id="result-line" aria-live="polite"></div>
      <div class="outcome-grid" id="outcome-grid"></div>
      <h3 style="margin-top:24px">Luồng xử lý khái quát</h3>
      <p class="hint" style="font-size:12px;margin-top:3px">Các bước dưới đây mô tả kiến trúc từ code và tài liệu; số event là số đo thực tế trong benchmark.</p>
      <ol class="flow" id="flow"></ol>
      <p class="note" id="case-note"></p>
    </div>
  </section>

  <section aria-labelledby="matrix-title">
    <div class="section-head"><h2 id="matrix-title">Cùng claim, 20 lượt chạy</h2><p>Nhấn một ô để mở lượt chạy tương ứng ở trên.</p></div>
    <div class="panel"><div class="matrix" id="matrix"></div><p class="legend">Xanh: pass · Cam: không pass · Viền sáng: lượt đang xem. Ma trận luôn dùng cùng claim và 5 seed.</p></div>
  </section>

  <section aria-labelledby="compare-title">
    <div class="section-head"><h2 id="compare-title">Tổng kết bốn shape</h2><p>Giá là VND mô phỏng từ MockLLM và tool, không phải hóa đơn API.</p></div>
    <div class="panel table-wrap"><table><thead><tr><th>Shape</th><th>Pass rate</th><th>Pass⁵</th><th>Seed variance</th><th>Cost/success</th><th>Event TB/P95</th><th>Model call TB</th></tr></thead><tbody id="summary-body"></tbody></table></div>
  </section>

  <section id="baseline-section" aria-labelledby="baseline-title" hidden>
    <div class="section-head"><h2 id="baseline-title">So với bản demo trước</h2><p>Cùng corpus và 5 seed; số liệu lấy từ hai báo cáo benchmark.</p></div>
    <div class="panel table-wrap"><table><thead><tr><th>Shape</th><th>Pass rate</th><th>Cost/success cũ → mới</th><th>Event TB cũ → mới</th></tr></thead><tbody id="baseline-body"></tbody></table></div>
  </section>

  <footer id="source-line"></footer>
</main>
<script id="demo-data" type="application/json">__DATA__</script>
<script>
(() => {
  const data = JSON.parse(document.getElementById('demo-data').textContent);
  const shapes = ['workflow','single','orchestrator','swarm'];
  const label = {workflow:'Workflow',single:'Single ReAct',orchestrator:'Orchestrator',swarm:'Swarm reference'};
  const statusLabel = {resolved:'resolved · hoàn tiền',needs_info:'needs_info · hỏi thêm',escalated:'escalated · chuyển xử lý',denied:'denied · từ chối',failed:'failed · lỗi'};
  const fmt = n => new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2}).format(n);
  const pct = n => (100*n).toLocaleString('vi-VN',{maximumFractionDigits:1}) + '%';
  const byId = id => document.getElementById(id);
  const claimSelect = byId('claim-select'), shapeSelect = byId('shape-select'), seedSelect = byId('seed-select');
  const trialByKey = new Map(data.trials.map(t => [t.claim_id+'|'+t.shape+'|'+t.seed,t]));
  data.claims.forEach(c => claimSelect.add(new Option(c.matrix_id+' · '+c.claim_id,c.claim_id)));
  shapes.forEach(s => shapeSelect.add(new Option(label[s],s)));
  data.seeds.forEach(s => seedSelect.add(new Option(String(s),String(s))));
  claimSelect.value='C-001'; shapeSelect.value=data.chosen_shape; seedSelect.value='11';
  byId('claim-count').textContent=data.claims.length;
  byId('trial-count').textContent=data.trials.length;
  byId('crash-pill').textContent='Crash safety '+data.crash;
  byId('chosen-name').textContent=label[data.chosen_shape];
  byId('chosen-score').textContent=data.by_shape[data.chosen_shape].successes+'/'+data.by_shape[data.chosen_shape].trials+' lượt pass';
  byId('chosen-pass5-label').textContent='Pass⁵ · '+label[data.chosen_shape];
  byId('chosen-pass5').textContent=pct(data.by_shape[data.chosen_shape].pass_5);
  byId('source-line').textContent='Nguồn: '+data.sources.benchmark+', '+data.sources.crash+', src/data/public_claims.jsonl và tài liệu kiến trúc. Snapshot này không chứa ticket, secret, header hoặc dữ liệu đơn thô.';
  if (data.baseline) {
    byId('baseline-section').hidden=false;
    const body=byId('baseline-body');
    shapes.forEach(shape=>{
      const old=data.baseline[shape], now=data.by_shape[shape];
      const row=document.createElement('tr');
      const cells=[label[shape],pct(old.pass_rate)+' → '+pct(now.pass_rate),fmt(old.cost_per_success_vnd)+' → '+fmt(now.cost_per_success_vnd)+' VND',fmt(old.mean_steps)+' → '+fmt(now.mean_steps)];
      cells.forEach((value,i)=>{const td=document.createElement('td');td.textContent=value;if(i===2&&now.cost_per_success_vnd<old.cost_per_success_vnd)td.className='delta-good';if(i===2&&now.cost_per_success_vnd>old.cost_per_success_vnd)td.className='delta-warn';row.append(td);});
      body.append(row);
    });
  }

  function flowFor(shape,claim,trial) {
    const common = [
      ['01','Đọc claim','Dùng claim_id và order_id có cấu trúc.'],
      ['02','Kiểm tra đơn','Chỉ xem đơn thuộc principal.'],
      ['03','Quote bằng code','Dựa vào order và policy hiệu lực.'],
      ['04','Cổng host','Approval, trần theo đơn, idempotency.'],
      ['05','Kết quả & trace','Ledger và audit trong một transaction.']
    ];
    if (shape==='single') common[1]=['02','ReAct chỉ đọc','Tối đa 8 bước; đọc đơn, tính quote.'];
    if (shape==='orchestrator') { common[1]=['02','Handoff allowlist','Không mang secret, header hay tool ghi.']; common[2]=['03','Investigator','Chỉ dùng tool đọc để lấy order và quote.']; }
    if (shape==='swarm') { common[0]=['01','Peers đọc ticket','Thêm model call để trao đổi.']; common[2]=['03','Quote & đối chiếu','Seed 55 có thể tin sai delay từ ticket.']; }
    if (claim.expected.status==='needs_info') { common[1]=['02','Dừng sớm','Thiếu order_id.']; common[2]=['03','Không thực hiện','Không lookup đơn hoặc quote.']; common[3]=['04','Không ghi tiền','Không gọi issue_refund.']; }
    if (claim.expected.status==='escalated') { common[2]=['03','Dừng sớm','Đơn không hiển thị trong phạm vi principal.']; common[3]=['04','Không ghi tiền','Không gọi issue_refund.']; }
    if (claim.expected.status==='denied' && claim.expected.proposal_amount===0) common[3]=['04','Không ghi tiền','Quote 0; không gọi issue_refund.'];
    if (claim.expected.status==='denied' && claim.expected.proposal_amount>0) common[3]=['04','Host từ chối','Quote dương; host ghi policy_denied.'];
    if (!trial.passed && shape==='swarm' && claim.matrix_id==='T02') { common[2]=['03','Quote lệch','Seed 55 lấy delay từ ticket thay vì order.']; common[3]=['04','Host chấp nhận','Approval hợp lệ nhưng quote đầu vào sai.']; }
    if (!trial.passed) common[4]=['05','Sai kỳ vọng','Outcome thực tế khác nhãn public.'];
    return common;
  }

  function render() {
    const claim=data.claims.find(c=>c.claim_id===claimSelect.value);
    const shape=shapeSelect.value, seed=Number(seedSelect.value);
    const trial=trialByKey.get(claim.claim_id+'|'+shape+'|'+seed);
    byId('case-line').textContent=claim.matrix_id+' · '+claim.description;
    const result=byId('result-line'); result.replaceChildren();
    const tag=document.createElement('span'); tag.className='tag '+(trial.passed?'good':'bad'); tag.textContent=trial.passed?'PASS':'FAIL'; result.append(tag);
    const observed=document.createElement('strong'); observed.textContent=statusLabel[trial.status]||trial.status; result.append(observed);
    const id=document.createElement('span'); id.className='run-id'; id.textContent=trial.run_id; result.append(id);
    const fields=[
      ['Kỳ vọng',statusLabel[claim.expected.status]||claim.expected.status],
      ['Quote kỳ vọng',fmt(claim.expected.proposal_amount)+' VND'],
      ['Refund kỳ vọng',fmt(claim.expected.refund_vnd)+' VND'],
      ['Đo được',trial.steps+' event · '+fmt(trial.cost_estimate)+' VND']
    ];
    const grid=byId('outcome-grid'); grid.replaceChildren();
    fields.forEach(([k,v])=>{ const box=document.createElement('div'); box.className='mini'; const a=document.createElement('span');a.textContent=k;const b=document.createElement('strong');b.textContent=v;box.append(a,b);grid.append(box); });
    const flow=byId('flow');flow.replaceChildren();
    flowFor(shape,claim,trial).forEach(([n,title,desc])=>{const li=document.createElement('li');const a=document.createElement('span');a.className='num';a.textContent=n;const b=document.createElement('b');b.textContent=title;const c=document.createElement('small');c.textContent=desc;li.append(a,b,c);flow.append(li);});
    const note=trial.passed ? (claim.expected.status==='resolved' ? 'Quote kỳ vọng là entitlement đầy đủ; host có thể ghi ít hơn do approval hoặc tiền đã hoàn trước đó.':'Nhánh này không có refund mới. Giá trị quote/refund phía trên là nhãn kỳ vọng, không phải dữ liệu thô trong trace.') : 'Benchmark ghi nhận: '+trial.reason+'. Với T02/seed 55, swarm tin delay trong ticket hơn order row; đây là lỗi đối chứng đã biết.';
    byId('case-note').textContent=note;
    renderMatrix(claim.claim_id,shape,seed);
    renderSummary(shape);
  }

  function renderMatrix(claimId,currentShape,currentSeed) {
    const matrix=byId('matrix');matrix.replaceChildren();
    const blank=document.createElement('div');matrix.append(blank);
    data.seeds.forEach(seed=>{const e=document.createElement('div');e.className='head';e.textContent='seed '+seed;matrix.append(e);});
    shapes.forEach(shape=>{
      const row=document.createElement('div');row.className='row-name';row.textContent=label[shape];matrix.append(row);
      data.seeds.forEach(seed=>{const t=trialByKey.get(claimId+'|'+shape+'|'+seed);const b=document.createElement('button');b.type='button';b.className='cell '+(t.passed?'good':'bad')+(shape===currentShape&&seed===currentSeed?' selected':'');b.textContent=t.passed?'PASS':'FAIL';b.setAttribute('aria-label',label[shape]+', seed '+seed+', '+(t.passed?'pass':'fail'));b.addEventListener('click',()=>{shapeSelect.value=shape;seedSelect.value=String(seed);render();window.scrollTo({top:byId('inspect-title').offsetTop-12,behavior:'smooth'});});matrix.append(b);});
    });
  }

  function renderSummary(currentShape) {
    const body=byId('summary-body');body.replaceChildren();
    shapes.forEach(shape=>{const m=data.by_shape[shape];const tr=document.createElement('tr');if(shape===currentShape)tr.className='chosen';const vals=[label[shape],pct(m.pass_rate),pct(m.pass_5),m.seed_variance.toFixed(6),fmt(m.cost_per_success_vnd)+' VND',fmt(m.mean_steps)+' / '+fmt(m.p95_steps),fmt(m.mean_model_calls)];vals.forEach((v,i)=>{const td=document.createElement('td');if(i===1){const bar=document.createElement('span');bar.className='bar';const fill=document.createElement('i');fill.className=m.pass_rate<1?'imperfect':'';fill.style.width=(m.pass_rate*100)+'%';bar.append(fill);td.append(bar);}td.append(document.createTextNode(v));tr.append(td);});body.append(tr);});
  }
  [claimSelect,shapeSelect,seedSelect].forEach(el=>el.addEventListener('change',render));
  render();
})();
</script>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=SRC / "reports" / "benchmark.json")
    parser.add_argument("--crash", type=Path, default=SRC / "reports" / "crash.json")
    parser.add_argument("--baseline", type=Path, help="Previous benchmark for a comparison table")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    crash = json.loads(args.crash.read_text(encoding="utf-8"))
    adr = (ROOT / "report" / "team" / "decision_adr.md").read_text(encoding="utf-8")
    chosen_shape = next(line.split(":", 1)[1].strip() for line in adr.splitlines()
                        if line.startswith("- Shape chọn:"))
    if chosen_shape not in benchmark["by_shape"]:
        raise SystemExit(f"ADR chose an unknown shape: {chosen_shape}")
    claims = [json.loads(line) for line in (SRC / "data" / "public_claims.jsonl").read_text(encoding="utf-8").splitlines() if line]
    safe_claims = [
        {
            "claim_id": claim["claim_id"],
            "matrix_id": claim["matrix_id"],
            "description": SCENARIOS[claim["matrix_id"]],
            "expected": {
                key: claim["expected"][key]
                for key in ("status", "proposal_amount", "refund_vnd")
            },
        }
        for claim in claims
    ]
    safe_trials = [
        {key: trial[key] for key in (
            "shape", "claim_id", "seed", "passed", "reason", "status",
            "cost_estimate", "steps", "run_id",
        )}
        for trial in benchmark["trials"]
    ]
    safe_metrics = {
        shape: {key: values[key] for key in (
            "trials", "successes", "pass_rate", "pass_5", "seed_variance",
            "cost_per_success_vnd", "mean_steps", "p95_steps", "mean_model_calls",
        )}
        for shape, values in benchmark["by_shape"].items()
    }
    data = {
        "claims": safe_claims,
        "trials": safe_trials,
        "seeds": benchmark["controlled_variables"]["seeds"],
        "by_shape": safe_metrics,
        "crash": crash["crash_safety"],
        "chosen_shape": chosen_shape,
        "sources": {"benchmark": str(args.benchmark), "crash": str(args.crash)},
    }
    if args.baseline:
        previous = json.loads(args.baseline.read_text(encoding="utf-8"))
        if (previous["controlled_variables"]["claim_ids"] != benchmark["controlled_variables"]["claim_ids"]
                or previous["controlled_variables"]["seeds"] != benchmark["controlled_variables"]["seeds"]):
            raise SystemExit("Baseline and current benchmark use different claims or seeds")
        data["baseline"] = {
            shape: {key: values[key] for key in ("pass_rate", "cost_per_success_vnd", "mean_steps")}
            for shape, values in previous["by_shape"].items()
        }
    if len(safe_claims) != 14 or len(safe_trials) != 280 or crash["crash_safety"] != "20/20":
        raise SystemExit("Expected 14 claims, 280 benchmark trials, and crash 20/20")
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(HTML.replace("__DATA__", serialized), encoding="utf-8")
    print(f"wrote {args.out} ({len(safe_trials)} trials)")


if __name__ == "__main__":
    main()
