import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, BadgeCheck, Bell, Boxes,
  Check, CheckCircle2, ChevronDown, CircleHelp, Clock3, Cloud, FileCheck2,
  Fingerprint, GitBranch, History, Layers3, LoaderCircle, LockKeyhole,
  Menu, Search, Shield, ShieldCheck, Sparkles, X,
} from 'lucide-react';

const stages = ['Discover', 'Audit', 'Compare', 'Analyze', 'Approve', 'Act', 'Verify'];
const money = (amount, currency = 'USD') => amount == null ? 'Unavailable' : new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(amount));
const shortDate = (date) => date ? new Date(date).toLocaleString() : '—';
const humanize = (value = '') => value.toLowerCase().replaceAll('_', ' ');

async function api(path, options) {
  const response = await fetch(path, { ...options, headers: { 'content-type': 'application/json', ...(options?.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function App() {
  const [form, setForm] = useState({ instance_id: '', target_instance_type: 't3.small', health_check_url: '' });
  const [instances, setInstances] = useState([]);
  const [proposal, setProposal] = useState(null);
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [approver, setApprover] = useState('operator@company.com');
  const [allowRollback, setAllowRollback] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [serviceHealth, setServiceHealth] = useState(null);

  useEffect(() => {
    api('/healthz').then(setServiceHealth).catch(() => setServiceHealth({ status: 'offline' }));
    api('/v1/instances').then((data) => {
      setInstances(data);
      if (data && data.length > 0) {
        const first = data.find((i) => i.managed) || data[0];
        setForm((prev) => ({
          ...prev,
          instance_id: first.instance_id,
          target_instance_type: first.recommended_target || 't3.small',
        }));
      }
    }).catch(() => {});
    const saved = localStorage.getItem('chronoArchitectRun');
    if (!saved) return;
    api(`/v1/runs/${encodeURIComponent(saved)}/proposal`).then(setProposal).catch(() => localStorage.removeItem('chronoArchitectRun'));
  }, []);


  useEffect(() => {
    if (proposal?.run_id) refreshAudit(proposal.run_id);
  }, [proposal?.run_id]);

  async function refreshAudit(runId = proposal?.run_id) {
    if (!runId) return;
    try { setAudit(await api(`/v1/runs/${encodeURIComponent(runId)}/audit`)); }
    catch (e) { setError(`Could not load the audit trail: ${e.message}`); }
  }

  function resetSimulation() {
    localStorage.removeItem('chronoArchitectRun');
    setProposal(null);
    setAudit(null);
    setError('');
    setMessage('Simulation state reset. Ready for a new investigation.');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }


  async function investigate(event) {
    event.preventDefault(); setLoading(true); setError(''); setMessage('Gathering live AWS evidence…');
    try {
      const payload = { ...form };
      if (!payload.health_check_url) delete payload.health_check_url;
      const result = await api('/v1/investigations', { method: 'POST', body: JSON.stringify(payload) });
      setProposal(result); setAudit(null); localStorage.setItem('chronoArchitectRun', result.run_id);
      setMessage('Investigation complete. Review the evidence before approving.');
    } catch (e) { setError(e.message); setMessage(''); }
    finally { setLoading(false); }
  }

  async function approve(event) {
    event.preventDefault(); if (!proposal) return;
    setExecuting(true); setError(''); setMessage('Submitting your approval and executing the change…');
    const now = new Date();
    const expiry = new Date(Math.min(now.getTime() + 15 * 60_000, new Date(proposal.expires_at).getTime()));
    try {
      const result = await api(`/v1/runs/${encodeURIComponent(proposal.run_id)}/execute`, { method: 'POST', body: JSON.stringify({
        decision: 'approve', proposal_hash: proposal.proposal_hash, approver: approver.trim(), approved_at: now.toISOString(),
        expires_at: expiry.toISOString(), allow_rollback: allowRollback,
      }) });
      setMessage(`Execution finished: ${result.state}${result.audit_chain_valid ? ' · audit chain verified' : ''}`);
      await refreshAudit(proposal.run_id);
    } catch (e) { setError(e.message); setMessage(''); await refreshAudit(proposal.run_id); }
    finally { setExecuting(false); }
  }

  const failedChecks = useMemo(() => proposal?.checks?.filter((check) => check.critical && check.status !== 'PASS') || [], [proposal]);
  const rightSize = proposal?.scenarios?.find((scenario) => scenario.name === 'right-size');
  const currentScenario = proposal?.scenarios?.find((scenario) => scenario.name === 'no-change');
  const cpu = proposal?.metrics?.find((metric) => /cpu/i.test(metric.metric));
  const memory = proposal?.metrics?.find((metric) => /memory|mem/i.test(metric.metric));
  const completed = proposal ? ['Discover', 'Audit', 'Compare', 'Analyze'] : [];
  const activeStage = !proposal ? 'Discover' : audit?.events?.some((event) => event.state === 'VERIFIED') ? 'Verify' : 'Approve';
  const approvalAlreadySubmitted = audit?.events?.some((event) => event.kind === 'approval_validated') || false;

  return <div className="min-h-screen bg-[#f6f8f6] text-ink">
    <aside className={`fixed inset-y-0 left-0 z-30 flex w-[238px] flex-col bg-[#101918] px-4 py-6 text-white transition-transform md:translate-x-0 ${mobileNav ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="mb-8 flex items-start gap-2.5 px-2"><img src="/logo.png" alt="" className="h-8 w-8 rounded-lg" /><div className="font-display text-base font-extrabold tracking-tight">chrono<span className="font-medium text-emerald-100/70">/architect</span><small className="mt-1 block font-mono text-[9px] font-normal tracking-[.08em] text-slate-400">INFRASTRUCTURE INTELLIGENCE</small></div></div>
      <div className="mb-8 flex items-center gap-2 rounded-lg border border-slate-700/80 p-2"><div className="grid h-7 w-7 place-items-center rounded-md bg-emerald-100 font-bold text-emerald-800">A</div><div className="min-w-0"><b className="block text-[11px]">AWS workspace</b><span className="text-[10px] text-slate-400">Connected environment</span></div><ChevronDown className="ml-auto h-4 w-4 text-slate-400" /></div>
      <div className="mb-2 px-2 font-mono text-[9px] tracking-widest text-slate-500">WORKSPACE</div>
      <nav className="space-y-1 text-xs"><a onClick={() => setMobileNav(false)} className="flex items-center gap-3 rounded-md bg-emerald-950/70 px-3 py-2.5 text-emerald-50" href="#overview"><Layers3 size={15} className="text-emerald-300" />Overview<Check size={13} className="ml-auto text-emerald-300" /></a><a onClick={() => setMobileNav(false)} className="flex items-center gap-3 rounded-md px-3 py-2.5 text-slate-300 hover:bg-white/5" href="#investigate"><Search size={15} />Investigations</a><a onClick={() => setMobileNav(false)} className="flex items-center gap-3 rounded-md px-3 py-2.5 text-slate-300 hover:bg-white/5" href="#review"><FileCheck2 size={15} />Approval queue{proposal && <span className="ml-auto font-mono text-[10px]">1</span>}</a><a onClick={() => setMobileNav(false)} className="flex items-center gap-3 rounded-md px-3 py-2.5 text-slate-300 hover:bg-white/5" href="#audit"><History size={15} />Audit trail</a></nav>
      <div className="mt-auto border-t border-slate-700/80 pt-4"><div className="flex items-center gap-2 px-2"><span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_3px_#1d3930]" /><div><b className="block text-[11px]">Safety gates active</b><span className="text-[10px] text-slate-400">Approval required to execute</span></div></div><div className="mt-5 flex items-center gap-2 border-t border-slate-700/80 px-2 pt-4"><div className="grid h-7 w-7 place-items-center rounded-full bg-slate-700 text-[9px]">OP</div><div><b className="block text-[10px]">Review as</b><span className="text-[10px] text-slate-400">Operator</span></div></div></div>
    </aside>

    <main id="overview" className="min-h-screen md:ml-[238px]">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-9"><div className="flex items-center gap-3 text-[11px] text-slate-500"><button onClick={() => setMobileNav(!mobileNav)} className="md:hidden"><Menu size={18} /></button>Cloud operations <span className="text-slate-300">/</span><b className="text-slate-800">Overview</b></div><div className="flex items-center gap-3"><span className="hidden font-mono text-[10px] text-slate-500 sm:inline-flex sm:items-center"><Cloud size={14} className="mr-1 text-forest" />AWS · configured region</span><span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-100 text-[9px] font-bold text-emerald-800">OP</span></div></header>

      <div className="mx-auto max-w-[1450px] space-y-4 p-4 md:p-8">
        <section className="flex flex-wrap items-end justify-between gap-4"><div><p className={`flex items-center gap-2 font-mono text-[9px] tracking-[.12em] ${serviceHealth?.status === 'ok' ? 'text-emerald-800' : 'text-amber-700'}`}><span className={`h-1.5 w-1.5 rounded-full ${serviceHealth?.status === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'}`} /> API {serviceHealth?.status === 'ok' ? 'ONLINE' : serviceHealth?.status === 'offline' ? 'OFFLINE' : 'CONNECTING'} <span className="text-slate-300">·</span> AWS EVIDENCE ON DEMAND</p><h1 className="mt-3 font-display text-[27px] font-bold leading-tight tracking-[-.045em] md:text-[32px]">See the future<br />before you change the cloud.</h1><p className="mt-2 text-xs text-slate-500">Evidence-led infrastructure changes, reviewed at every step.</p></div><div className="flex gap-2"><button onClick={resetSimulation} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-[11px] font-semibold text-slate-700 shadow-sm hover:bg-slate-50">🔄 Reset simulation</button><button onClick={() => document.querySelector('#investigate')?.scrollIntoView({ behavior: 'smooth' })} className="inline-flex h-9 items-center gap-2 rounded-md bg-forest px-3.5 text-[11px] font-semibold text-white shadow-sm hover:bg-emerald-800"><span className="text-base">＋</span> New investigation</button></div></section>


        <section className="grid grid-cols-2 gap-2.5 xl:grid-cols-4">
          <Stat label="ACTIVE INVESTIGATION" value={proposal?.instance?.instance_id || '—'} note={proposal ? `${proposal.instance.region} · ${proposal.instance.instance_type}` : 'Select a managed instance'} icon={<Search size={14} />} />
          <Stat label="VERIFIED SAVINGS" value="—" note="Reported after verified changes" icon={<ArrowDownRight size={15} />} />
          <Stat label="AWAITING YOUR REVIEW" value={proposal && !approvalAlreadySubmitted ? '1 proposal' : '0 proposals'} note="Explicit human approval gate" icon={<FileCheck2 size={15} />} amber />
          <Stat label="WORKFLOW STAGES" value="7 steps" note="Discover through verify" icon={<BadgeCheck size={15} />} />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 md:p-5"><div className="flex items-end justify-between"><div><Eyebrow>DETERMINISTIC WORKFLOW</Eyebrow><h2 className="mt-1 font-display text-sm font-bold">Operational lifecycle</h2></div><span className="font-mono text-[9px] text-slate-400">{proposal ? `RUN ${proposal.run_id.slice(0, 8)}` : 'NO ACTIVE RUN'}</span></div><div className="mt-5 grid grid-cols-7">{stages.map((stage, index) => { const done = completed.includes(stage) || (stage === 'Approve' && audit?.events?.some((e) => ['APPROVED', 'PRECONDITIONS_RECHECKED'].includes(e.state))) || (stage === 'Act' && audit?.events?.some((e) => ['RUNNING', 'VERIFIED'].includes(e.state))) || (stage === 'Verify' && audit?.events?.some((e) => e.state === 'VERIFIED')); const active = activeStage === stage && !done; return <div key={stage} className={`min-w-0 border-t-2 px-1.5 pt-2 ${done || active ? 'border-emerald-500' : 'border-slate-200'}`}><span className={`font-mono text-[9px] ${done || active ? 'text-emerald-700' : 'text-slate-400'}`}>{String(index + 1).padStart(2, '0')}</span><b className={`mt-1 block text-[9px] sm:text-[10px] ${done || active ? 'text-emerald-900' : 'text-slate-500'}`}>{stage}</b><span className="mt-1 hidden text-[9px] text-slate-400 sm:block">{['Instance selected','Gather evidence','Compare futures','Check policy','Human review','Execute via MCP','Confirm health'][index]}</span></div> })}</div></section>

        <div className="grid gap-4 xl:grid-cols-[minmax(320px,.78fr)_minmax(500px,1.5fr)]">
          <section id="investigate" className="scroll-mt-20 rounded-lg border border-slate-200 bg-white p-4 md:p-5"><div className="flex gap-3"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700"><Search size={17} /></div><div><Eyebrow>STEP 01—04</Eyebrow><h2 className="mt-1 font-display text-sm font-bold">Investigate a resource</h2><p className="mt-1 text-[10px] text-slate-500">Collect live AWS evidence and compare a proposed instance type.</p></div></div>
            <form onSubmit={investigate} className="mt-5 space-y-3.5">
              <Field label="Select EC2 instance" hint={<>Discovered instances in AWS region (<code className="rounded bg-emerald-50 px-1 text-[9px] text-emerald-800">chrono-architect:managed=true</code>).</>}>
                {instances.length > 0 ? <select required className="w-full rounded border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-800 focus:border-emerald-600 focus:outline-none" value={form.instance_id} onChange={(e) => {
                  const sel = instances.find((i) => i.instance_id === e.target.value);
                  setForm({ ...form, instance_id: e.target.value, target_instance_type: sel?.recommended_target || 't3.small' });
                }}>
                  {instances.map((inst) => <option key={inst.instance_id} value={inst.instance_id}>{inst.name} — {inst.instance_id} {inst.managed ? ' (Opt-in Managed)' : ''}</option>)}
                </select> : <input required pattern="i-[0-9a-f]{8,17}" placeholder="i-0123456789abcdef0" value={form.instance_id} onChange={(e) => setForm({ ...form, instance_id: e.target.value })} />}
              </Field>
              <div className="grid grid-cols-2 gap-2.5"><Field label="Target instance type"><input required pattern="[a-z0-9]+[a-z0-9-]*\.[a-z0-9]+" placeholder="m6i.large" value={form.target_instance_type} onChange={(e) => setForm({ ...form, target_instance_type: e.target.value })} /></Field><Field label="Region"><div className="flex h-[35px] items-center justify-between rounded border border-slate-200 bg-slate-50 px-2 text-[9px] text-slate-500">AWS <span>Server configured</span></div></Field></div>

              <Field label="External health check URL" hint="Must use HTTPS and resolve to a public address."><input type="url" placeholder="https://service.example/health" value={form.health_check_url} onChange={(e) => setForm({ ...form, health_check_url: e.target.value })} /><span className="font-mono text-[8px] font-normal text-amber-700">OPTIONAL · REQUIRED FOR PRODUCTION</span></Field>
              <div className="flex gap-2 rounded-md bg-slate-50 p-2.5 text-[9px] leading-relaxed text-slate-500"><ShieldCheck size={14} className="mt-0.5 shrink-0 text-emerald-700" />Read-only investigation first. No infrastructure changes happen without separate human approval.</div>
              <button disabled={loading} className="flex h-9 w-full items-center justify-center gap-2 rounded-md bg-forest px-3 text-[11px] font-semibold text-white hover:bg-emerald-800 disabled:opacity-60">{loading ? <><LoaderCircle size={14} className="animate-spin" /> Collecting AWS evidence…</> : <>Run evidence investigation <ArrowRight size={14} className="ml-auto" /></>}</button>
            </form>
          </section>

          <section className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 md:p-5"><div className="flex items-center justify-between"><div><Eyebrow>CURRENT RUN</Eyebrow><h2 className="mt-1 font-display text-sm font-bold">Investigation evidence</h2></div><Tag tone={proposal ? 'green' : 'slate'}>{proposal ? 'EVIDENCE READY' : 'STANDBY'}</Tag></div>
            {!proposal ? <div className="flex min-h-[330px] flex-col items-center justify-center px-5 text-center"><div className="grid h-12 w-12 place-items-center rounded-full border border-emerald-100 bg-emerald-50 text-emerald-700"><Clock3 size={22} /></div><h3 className="mt-4 font-display text-sm font-bold">Your next safe change starts here.</h3><p className="mt-2 max-w-sm text-[10px] leading-relaxed text-slate-500">Run an investigation to see AWS telemetry, cost evidence, policy checks, and possible futures.</p><div className="mt-7 flex flex-wrap justify-center gap-4 border-t border-slate-100 pt-4 text-[9px] text-slate-500"><span><b className="font-mono text-emerald-700">01</b> Forensic evidence</span><span><b className="font-mono text-emerald-700">02</b> Scenario comparison</span><span><b className="font-mono text-emerald-700">03</b> Human approval</span></div></div> : <>
              <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4"><Evidence label="CURRENT MONTHLY ESTIMATE" value={money(currentScenario?.estimated_cost?.current_monthly, currentScenario?.estimated_cost?.currency)} note={currentScenario?.estimated_cost?.basis || 'AWS pricing evidence'} /><Evidence label="CPU AVERAGE · P95" value={cpu?.average == null ? 'No datapoints' : `${Number(cpu.average).toFixed(1)} ${cpu.unit}`} note={cpu?.p95 == null ? 'p95 unavailable' : `p95 ${Number(cpu.p95).toFixed(1)} ${cpu.unit}`} /><Evidence label="MEMORY AVERAGE" value={memory?.average == null ? 'Not reported' : `${Number(memory.average).toFixed(1)} ${memory.unit}`} note="CloudWatch agent dependent" /><Evidence label="HISTORICAL COST" value={proposal.historical_cost ? money(proposal.historical_cost.amount, proposal.historical_cost.currency) : 'Unavailable'} note={proposal.historical_cost?.source || 'Cost Explorer data'} /></div>
              <div className="mt-4 flex flex-wrap items-start justify-between gap-2 border-t border-slate-100 pt-3"><div><h3 className="font-display text-xs font-bold">{proposal.instance.instance_id}</h3><p className="mt-1 font-mono text-[9px] text-slate-500">{proposal.instance.instance_type} · {proposal.instance.region} · {proposal.instance.state}</p></div><Tag tone={proposal.production ? 'amber' : 'slate'}>{proposal.production ? 'PRODUCTION' : 'MANAGED RESOURCE'}</Tag></div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">{proposal.scenarios?.map((scenario) => <article key={scenario.name} className={`rounded-md border p-3 ${scenario.name === 'right-size' ? 'border-emerald-200 bg-emerald-50/30' : scenario.name === 'idle-decommission' ? 'border-amber-200 bg-amber-50/20' : 'border-slate-200'}`}><div className="flex items-center justify-between gap-1"><h4 className="text-[10px] font-semibold">{scenario.name === 'right-size' ? '↘ Right-size · proposed' : scenario.name === 'idle-decommission' ? '⚠️ Decommission / Idle' : 'Keep current size'}</h4>{scenario.name === 'right-size' && <Tag tone="green">PROPOSED</Tag>}</div><p className="mt-2 font-display text-base font-bold">{money(scenario.estimated_cost.monthly_savings, scenario.estimated_cost.currency)}<span className="ml-1 font-sans text-[9px] font-normal text-slate-500">/ mo savings</span></p><p className="mt-1 text-[9px] text-slate-500">Target {scenario.target_instance_type} · {scenario.estimated_cost.savings_percent}% estimate</p><p className="mt-2 border-t border-slate-100 pt-2 text-[9px] leading-relaxed text-slate-500">Risk {scenario.risk_score}/100 · {scenario.downtime_required ? 'Downtime required' : 'No downtime'} · {scenario.reversible ? 'Reversible' : 'Not reversible'}{scenario.blast_radius?.length > 0 && <><br />Blast radius: {scenario.blast_radius.join(' · ')}</>}</p></article>)}</div>
              {proposal.manager_analysis && <div className="mt-4 rounded-md border border-emerald-900 bg-emerald-950 p-3 text-emerald-50"><div className="flex items-center gap-1.5 font-mono text-[9px] tracking-wider text-emerald-300"><Sparkles size={13} /> OPENAI MANAGER AGENT · FINOPS SYNTHESIS &amp; NEGOTIATION PLAN</div><p className="mt-1.5 text-[10px] leading-relaxed text-emerald-100">{proposal.manager_analysis}</p></div>}
              <div className="mt-4 font-mono text-[9px] text-slate-600">POLICY &amp; EVIDENCE CHECKS <span className="text-slate-400">· {proposal.evidence_window_days}-day window</span></div><div className="mt-1 divide-y divide-slate-100">{proposal.checks?.map((check) => <div key={check.name} className="flex items-start gap-2 py-2 text-[9px]"><span className={check.status === 'PASS' ? 'text-emerald-700' : check.status === 'FAIL' ? 'text-red-600' : 'text-amber-600'}>{check.status === 'PASS' ? <CheckCircle2 size={13} /> : check.status === 'FAIL' ? <X size={13} /> : <AlertTriangle size={13} />}</span><div className="min-w-0 flex-1"><b className="capitalize">{humanize(check.name)}</b><p className="mt-0.5 leading-relaxed text-slate-500">{check.explanation}</p></div><Tag tone={check.status === 'PASS' ? 'green' : check.status === 'FAIL' ? 'red' : 'amber'}>{check.status}</Tag></div>)}</div>

              {rightSize?.estimated_cost?.caveats?.length > 0 && <p className="mt-2 text-[9px] leading-relaxed text-slate-500">{rightSize.estimated_cost.caveats.join(' ')}</p>}
            </>}</section>
        </div>

        <section id="review" className="scroll-mt-20 rounded-lg border border-slate-200 bg-white p-4 md:p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div><Eyebrow>HUMAN IN THE LOOP</Eyebrow><h2 className="mt-1 font-display text-sm font-bold">Forensic review &amp; execution</h2></div><Tag tone="amber">EXPLICIT APPROVAL REQUIRED</Tag></div>
          {!proposal ? <p className="pt-5 text-[10px] text-slate-500">Complete an investigation to review its proposed change and prepare an approval.</p> : <div className="mt-4">
            <div className={`rounded-md border p-3 text-[9px] leading-relaxed ${failedChecks.length ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-100 bg-amber-50 text-amber-900'}`}><b>{failedChecks.length ? 'Execution blocked by unresolved critical checks:' : 'Change preview:'}</b> {failedChecks.length ? failedChecks.map((check) => check.name).join(', ') : <>{proposal.instance.instance_type} → {proposal.target_instance_type} for {proposal.instance.instance_id}. Stopping the instance is required during this change.</>}<br />Proposal SHA-256 <code className="break-all font-mono">{proposal.proposal_hash}</code> · expires {shortDate(proposal.expires_at)}</div>
            <div className="my-3 grid gap-3 border-b border-slate-100 py-1 sm:grid-cols-3"><ReviewValue label="PROPOSED MONTHLY SAVINGS" value={money(rightSize?.estimated_cost?.monthly_savings, rightSize?.estimated_cost?.currency)} /><ReviewValue label="PROPOSAL HASH · SHA-256" value={proposal.proposal_hash} mono /><ReviewValue label="ROLLBACK" value="Only if explicitly enabled" /></div>
            {approvalAlreadySubmitted && <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-[9px] text-slate-600">An approval was already submitted for this run. Review the audit events below before taking further action.</div>}
            <form onSubmit={approve} className="grid items-end gap-3 md:grid-cols-[1fr_1fr_auto]"><Field label="Approver identity"><input required minLength={1} placeholder="name@company.com" value={approver} onChange={(e) => setApprover(e.target.value)} /></Field><div className="rounded-md bg-slate-50 p-2.5 text-[9px] leading-relaxed text-slate-600"><LockKeyhole size={13} className="mr-1 inline text-emerald-700" />Approval expires within 15 minutes and cannot outlive the proposal.</div><button disabled={executing || failedChecks.length > 0 || approvalAlreadySubmitted} className="flex h-9 items-center justify-center gap-2 rounded-md bg-forest px-4 text-[10px] font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50">{executing ? <><LoaderCircle size={13} className="animate-spin" /> Executing…</> : <>Approve &amp; execute <ArrowRight size={13} /></>}</button>
              <label className="flex cursor-pointer items-center gap-2 text-[9px] text-slate-600 md:col-span-3"><input type="checkbox" checked={allowRollback} onChange={(e) => setAllowRollback(e.target.checked)} className="h-3.5 w-3.5 accent-emerald-700" />Allow automated rollback to {proposal.instance.instance_type} if execution fails</label>
            </form>
          </div>}
        </section>

        <section id="audit" className="scroll-mt-20 rounded-lg border border-slate-200 bg-white p-4 md:p-5"><div className="flex items-center justify-between"><div><Eyebrow>IMMUTABLE RECORD</Eyebrow><h2 className="mt-1 font-display text-sm font-bold">Run audit trail</h2></div><button disabled={!proposal} onClick={() => refreshAudit()} className="inline-flex h-7 items-center gap-1 rounded border border-slate-200 px-2 text-[9px] text-slate-600 disabled:opacity-40"><Activity size={12} />Refresh</button></div>
          {!audit ? <p className="pt-4 text-[10px] text-slate-500">{proposal ? 'Loading audit events…' : 'Audit events will appear here when an investigation starts.'}</p> : <div className="mt-3 divide-y divide-slate-100">{audit.events?.map((event) => <div key={`${event.sequence}-${event.event_hash}`} className="grid gap-1 py-2 text-[9px] sm:grid-cols-[125px_1fr_auto] sm:items-start"><time className="font-mono text-slate-500">{shortDate(event.at)}</time><span><b className="capitalize">{humanize(event.kind)}</b>{event.state && <Tag tone="slate">{event.state}</Tag>}<code className="mt-1 block break-all font-mono text-[8px] text-slate-400">{event.event_hash || 'Hash not present'}</code></span><Tag tone={audit.chain_valid ? 'green' : 'red'}>{audit.chain_valid ? 'CHAIN VALID' : 'CHAIN INVALID'}</Tag></div>)}</div>}
        </section>
        {(error || message) && <div role="status" className={`flex items-start gap-2 rounded-md border p-3 text-[10px] ${error ? 'border-red-200 bg-red-50 text-red-800' : 'border-emerald-200 bg-emerald-50 text-emerald-900'}`}>{error ? <AlertTriangle size={14} /> : <Sparkles size={14} />}<span>{error || message}</span><button className="ml-auto" onClick={() => { setError(''); setMessage(''); }} aria-label="Dismiss"><X size={13} /></button></div>}
        <footer className="flex flex-wrap justify-between gap-2 px-1 py-2 font-mono text-[8px] tracking-wide text-slate-400"><span>CHRONO-ARCHITECT · SAFETY FIRST, ACTION SECOND</span><span>Evidence sourced from your AWS environment</span></footer>
      </div>
    </main>
    {mobileNav && <button aria-label="Close navigation" onClick={() => setMobileNav(false)} className="fixed inset-0 z-20 bg-black/30 md:hidden" />}
  </div>;
}

function Stat({ label, value, note, icon, amber = false }) {
  return <article className="rounded-lg border border-slate-200 bg-white p-3.5"><div className="flex items-center justify-between font-mono text-[8px] tracking-wide text-slate-500"><span>{label}</span><span className={`grid h-6 w-6 place-items-center rounded-md ${amber ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>{icon}</span></div><div className="mt-2 truncate font-display text-lg font-bold tracking-tight">{value}</div><p className="mt-1 truncate text-[9px] text-slate-500">{note}</p></article>;
}
function Eyebrow({ children }) { return <span className="font-mono text-[9px] tracking-[.08em] text-slate-500">{children}</span>; }
function Tag({ children, tone = 'slate' }) {
  const styles = { slate: 'bg-slate-100 text-slate-600', green: 'bg-emerald-50 text-emerald-800', amber: 'bg-amber-50 text-amber-800', red: 'bg-red-50 text-red-700' };
  return <span className={`inline-flex shrink-0 items-center rounded px-1.5 py-1 font-mono text-[8px] leading-none ${styles[tone]}`}>{children}</span>;
}
function Field({ label, hint, children }) { return <label className="grid gap-1.5 text-[10px] font-semibold text-slate-700">{label}{children}{hint && <span className="text-[9px] font-normal leading-relaxed text-slate-500">{hint}</span>}</label>; }
function Evidence({ label, value, note }) { return <div className="min-w-0 rounded-md border border-slate-100 bg-slate-50 p-2.5"><span className="block font-mono text-[7px] leading-relaxed text-slate-500">{label}</span><b className="mt-1 block truncate font-display text-[11px]">{value}</b><span className="mt-1 block truncate text-[8px] text-slate-400">{note}</span></div>; }
function ReviewValue({ label, value, mono = false }) { return <div className="min-w-0"><span className="block font-mono text-[8px] text-slate-500">{label}</span><b className={`mt-1 block truncate text-[10px] ${mono ? 'font-mono' : ''}`} title={value}>{value}</b></div>; }

export default App;
