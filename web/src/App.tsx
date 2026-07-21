import { useEffect, useMemo, useReducer, useState } from 'react';
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import ReactMarkdown from 'react-markdown';
import { Activity, ArrowLeft, Bot, Box, Braces, Check, ChevronRight, CircleStop, GitBranch, ListFilter, Menu, PanelRight, Play, Plus, RefreshCw, RotateCcw, Search, Server, Terminal, X, Zap } from 'lucide-react';

import { ApiError, api, connectRunEvents } from './api';
import { eventReducer, initialEventState } from './eventReducer';
import type { AgentCall, Backend, Diagnostic, LoopDetail, LoopSummary, Occurrence, RunDetail, RunEvent, RunStatus, RunSummary } from './types';

type View = 'runs' | 'loops' | 'backends';

const statusIcon = { running: Zap, done: Check, failed: X, stopped: CircleStop, stale: RefreshCw, unreadable: Braces } as const;

function Status({ value }: { value: string }) {
  const Icon = statusIcon[value as RunStatus] ?? Activity;
  return <span className={`status status-${value}`}><Icon size={12} />{value}</span>;
}

function IconButton({ label, children, onClick, active = false }: { label: string; children: React.ReactNode; onClick?: () => void; active?: boolean }) {
  return <button className={`icon-button ${active ? 'is-active' : ''}`} aria-label={label} title={label} onClick={onClick}>{children}</button>;
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty"><Box size={22} /><strong>{title}</strong><span>{detail}</span></div>;
}

function AppShell() {
  const [view, setView] = useState<View>('runs');
  return <div className="app-shell">
    <nav className="rail" aria-label="Primary">
      <div className="brand" aria-label="loopflow">lf</div>
      <div className="rail-actions">
        <IconButton label="Runs" active={view === 'runs'} onClick={() => setView('runs')}><Activity /></IconButton>
        <IconButton label="Loops" active={view === 'loops'} onClick={() => setView('loops')}><GitBranch /></IconButton>
        <IconButton label="Backends" active={view === 'backends'} onClick={() => setView('backends')}><Server /></IconButton>
      </div>
      <span className="rail-version">v0.17</span>
    </nav>
    <main className="app-main">
      {view === 'runs' && <RunsWorkspace />}
      {view === 'loops' && <LoopsWorkspace />}
      {view === 'backends' && <BackendsWorkspace />}
    </main>
  </div>;
}

function RunsWorkspace() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => new URLSearchParams(window.location.search).get('run'));
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [status, setStatus] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [eventView, setEventView] = useState<'phase' | 'unattributed' | 'malformed'>('phase');
  const [streamState, setStreamState] = useState<'live' | 'closed' | 'error'>('closed');
  const [eventState, dispatchEvent] = useReducer(eventReducer, { items: [], lastEventId: 0 });
  const [showNew, setShowNew] = useState(false);
  const [mobilePane, setMobilePane] = useState<'list' | 'detail' | 'process'>('list');
  const [error, setError] = useState<string | null>(null);

  const loadRuns = async () => {
    try {
      const params = new URLSearchParams();
      if (status !== 'all') params.set('status', status);
      if (query) params.set('q', query);
      const items: RunSummary[] = [];
      let cursor: string | null = null;
      do {
        if (cursor) params.set('cursor', cursor); else params.delete('cursor');
        const page = await api.runs(params.size ? `?${params}` : '');
        items.push(...page.items);
        cursor = page.next_cursor;
      } while (cursor);
      setRuns(items);
      setSelectedId((current) => current && items.some((run) => run.run_id === current) ? current : items[0]?.run_id ?? null);
    } catch (cause) { setError(messageOf(cause)); }
  };

  useEffect(() => { void loadRuns(); }, [status, query]);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (selectedId) url.searchParams.set('run', selectedId); else url.searchParams.delete('run');
    window.history.replaceState(null, '', url);
  }, [selectedId]);
  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    void api.run(selectedId).then((value) => {
      setDetail(value);
      dispatchEvent({ type: '__reset__', items: value.events });
      const phaseId = value.graph.current_phase_id ?? value.occurrences.at(-1)?.phase_id ?? null;
      setSelectedPhaseId(phaseId);
      setSelectedCallId(value.calls.find((call) => call.phase_id === phaseId)?.call_id ?? null);
      setEventView(value.events.some((event) => event.phase_id) ? 'phase' : value.unattributed_count > 0 ? 'unattributed' : value.malformed_count > 0 ? 'malformed' : 'phase');
    }).catch((cause) => setError(messageOf(cause)));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !detail || detail.status !== 'running') return;
    return connectRunEvents(selectedId, eventState.lastEventId, dispatchEvent, setStreamState);
  }, [selectedId, detail?.status]);

  const occurrences = detail?.occurrences ?? [];
  const selectedOccurrence = occurrences.find((item) => item.phase_id === selectedPhaseId) ?? null;
  const calls = (detail?.calls ?? []).filter((call) => call.phase_id === selectedPhaseId);
  const selectedCall = calls.find((call) => call.call_id === selectedCallId) ?? calls[0] ?? null;
  const visibleEvents = eventState.items.filter((event) => !selectedPhaseId || event.phase_id === selectedPhaseId).filter((event) => !selectedCall || event.call_id === selectedCall.call_id);
  const displayedEvents = eventView === 'unattributed' ? detail?.unattributed ?? [] : eventView === 'malformed' ? detail?.malformed ?? [] : visibleEvents;

  const selectRun = (id: string) => { setSelectedId(id); setMobilePane('detail'); };
  const act = async (action: string) => {
    if (!selectedId) return;
    try { await api.runAction(selectedId, action, action === 'resume' ? {} : undefined); await loadRuns(); setDetail(await api.run(selectedId)); }
    catch (cause) { setError(messageOf(cause)); }
  };

  return <section className={`workspace runs-workspace ${selectedCall ? 'has-call' : 'no-call'}`} data-testid="runs-workspace" data-mobile-pane={mobilePane}>
    <aside className="panel run-list-panel">
      <header className="panel-header workspace-title"><div><span className="eyebrow">Workspace</span><h1>Runs</h1></div><button className="primary-button" onClick={() => setShowNew(true)}><Plus size={15} />New</button></header>
      <div className="filter-bar"><label className="search"><Search size={14} /><input aria-label="Search runs" placeholder="Run or loop" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="select-wrap"><ListFilter size={14} /><select aria-label="Filter status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All</option><option value="running">Running</option><option value="failed">Failed</option><option value="done">Done</option><option value="stopped">Stopped</option></select></label></div>
      <div className="run-list" role="list">{runs.length ? runs.map((run) => <button role="listitem" key={run.run_id} className={`run-row ${selectedId === run.run_id ? 'is-selected' : ''}`} onClick={() => selectRun(run.run_id)}><span className="run-row-top"><strong>{run.loop ?? 'Unreadable run'}</strong><Status value={run.status} /></span><code title={run.working_directory}>{run.working_directory}</code><span className="row-meta"><span>{run.current_phase ?? 'No phase'}</span><span>{formatDuration(run.duration_ms)}</span></span>{run.parse_error && <span className="row-error">{run.parse_error}</span>}</button>) : <Empty title="No runs" detail="Start a Loop to create the first Run." />}</div>
    </aside>
    <section className="panel run-detail-panel">
      {!detail ? <Empty title="Select a Run" detail="Phase execution and events appear here." /> : <>
        <header className="panel-header run-toolbar"><div className="mobile-back"><IconButton label="Back to Runs" onClick={() => setMobilePane('list')}><ArrowLeft /></IconButton></div><div className="run-heading"><span className="eyebrow">{detail.loop}</span><h2>{detail.run_id}</h2></div><div className="toolbar-actions"><Status value={detail.status} />{detail.allowed_actions.includes('stop') && <button aria-label="Stop run" className="secondary-button" onClick={() => void act('stop')}><CircleStop size={14} />Stop</button>}{detail.allowed_actions.includes('resume') && <button aria-label="Resume run" className="primary-button" onClick={() => void act('resume')}><Play size={14} />Resume</button>}{detail.allowed_actions.includes('rerun') && <button aria-label="Rerun run" className="secondary-button" onClick={() => void act('rerun')}><RotateCcw size={14} />Rerun</button>}{detail.allowed_actions.includes('reconcile') && <button aria-label="Reconcile run" className="secondary-button" onClick={() => void act('reconcile')}><RefreshCw size={14} />Reconcile</button>}{selectedCall && <IconButton label="Open process inspector" onClick={() => setMobilePane('process')}><PanelRight /></IconButton>}</div></header>
        <div className="run-metrics"><Metric label="Duration" value={formatDuration(detail.duration_ms)} /><Metric label="Iterations" value={String(detail.iteration_count)} /><Metric label="Calls" value={String(detail.calls.length)} /><Metric label="Stream" value={detail.status === 'running' ? streamState : 'closed'} /></div>
        <PhaseGraph key={`${selectedId}-${mobilePane === 'list' ? 'hidden' : 'visible'}`} detail={detail} selectedPhaseId={selectedPhaseId} onSelect={(phaseId) => { setSelectedPhaseId(phaseId); setSelectedCallId(detail.calls.find((call) => call.phase_id === phaseId)?.call_id ?? null); setEventView('phase'); }} />
        <section className="phase-detail"><div className="phase-detail-bar"><div className="phase-detail-title"><h3>{selectedOccurrence?.phase ?? 'Events'}</h3>{selectedOccurrence && <span>Occurrence {selectedOccurrence.occurrence}</span>}</div>
          <div className="event-scope-tabs" role="tablist" aria-label="Event scope"><button role="tab" aria-selected={eventView === 'phase'} onClick={() => setEventView('phase')}>Events <span>{visibleEvents.length}</span></button>{detail.unattributed_count > 0 && <button role="tab" aria-selected={eventView === 'unattributed'} onClick={() => setEventView('unattributed')}>Unattributed <span>{detail.unattributed_count}</span></button>}{detail.malformed_count > 0 && <button role="tab" aria-selected={eventView === 'malformed'} onClick={() => setEventView('malformed')}>Malformed <span>{detail.malformed_count}</span></button>}</div>
          {detail.malformed_count > 0 && <span className="warning-text">{detail.malformed_count} malformed</span>}</div>
          <div className={`call-event-grid ${eventView !== 'phase' || calls.length === 0 ? 'events-only' : ''}`}>{eventView === 'phase' && calls.length > 0 && <div className="call-list"><h4>Calls</h4>{calls.map((call) => <button key={call.call_id} className={call.call_id === selectedCall?.call_id ? 'is-selected' : ''} onClick={() => setSelectedCallId(call.call_id)}><Bot size={14} /><span><strong>{call.session ?? call.call_id}</strong><small>{call.backend ?? 'backend unknown'} · {call.status}</small></span><ChevronRight size={14} /></button>)}</div>}<EventTimeline events={displayedEvents} title={eventView === 'phase' ? 'Phase events' : eventView === 'unattributed' ? 'Unattributed events' : 'Malformed events'} /></div>
        </section>
      </>}
    </section>
    <aside className="panel process-panel"><header className="panel-header"><div><span className="eyebrow">Agent process</span><h2>{selectedCall?.session ?? 'No Call selected'}</h2></div><div className="mobile-back"><IconButton label="Close process inspector" onClick={() => setMobilePane('detail')}><X /></IconButton></div></header>{detail && <details className="run-state"><summary>Run state</summary><pre>{JSON.stringify(detail.state, null, 2)}</pre></details>}{selectedCall ? <CallInspector call={selectedCall} events={visibleEvents} /> : <Empty title="No Call" detail="Select a Phase and attributed Call." />}</aside>
    {showNew && <NewRunDialog onClose={() => setShowNew(false)} onCreated={(run) => { setShowNew(false); void loadRuns(); selectRun(run.run_id); }} />}
    {error && <div className="toast" role="alert">{error}<IconButton label="Dismiss error" onClick={() => setError(null)}><X /></IconButton></div>}
  </section>;
}

function PhaseNodeView({ data, selected }: NodeProps<Node<{ label: string; count: number; current: boolean }>>) {
  return <div className={`phase-node ${selected ? 'is-selected' : ''} ${data.current ? 'is-current' : ''}`}><Handle type="target" position={Position.Left} /><span>{data.label}</span><small>{data.count} occurrence{data.count === 1 ? '' : 's'}</small><Handle type="source" position={Position.Right} /></div>;
}

function PhaseGraph({ detail, selectedPhaseId, onSelect }: { detail: RunDetail; selectedPhaseId: string | null; onSelect: (phaseId: string) => void }) {
  const nodeTypes = useMemo(() => ({ phase: PhaseNodeView }), []);
  const phaseToOccurrence = new Map(detail.occurrences.map((item) => [item.phase, item.phase_id]));
  const nodes: Node[] = detail.graph.nodes.map((item, index) => ({ id: item.phase, type: 'phase', position: { x: 40 + (index % 4) * 190, y: 54 + Math.floor(index / 4) * 110 }, data: { label: item.phase, count: item.occurrence_count, current: item.is_current }, selected: phaseToOccurrence.get(item.phase) === selectedPhaseId }));
  const edges: Edge[] = detail.graph.edges.map((item, index) => ({ id: `${item.from}-${item.to}-${index}`, source: item.from, target: item.to, animated: item.to === detail.current_phase, label: item.count > 1 ? String(item.count) : undefined, className: item.is_backedge ? 'backedge' : '' }));
  return <section className={`phase-graph ${nodes.length > 4 ? 'is-multiline' : ''}`} aria-label="Phase graph"><div className="section-heading"><div><span className="eyebrow">Execution path</span><h3>Phase graph</h3></div><span className="muted">{detail.graph.nodes.length} phases</span></div>{nodes.length ? <div className="flow-canvas" data-testid="phase-flow"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.35} maxZoom={1.5} nodesDraggable={false} onNodeClick={(_, node) => { const occurrences = detail.occurrences.filter((item) => item.phase === node.id); onSelect(occurrences.at(-1)?.phase_id ?? ''); }}><Background color="#292d2c" gap={24} size={1} /><Controls showInteractive={false} /></ReactFlow></div> : <Empty title="No phase events" detail="Raw Run events remain available below." />}</section>;
}

function EventTimeline({ events, title }: { events: RunEvent[]; title: string }) {
  return <div className="event-list"><div className="event-list-heading"><h4>{title}</h4><span>{events.length} events</span></div>{events.length ? events.map((event, index) => <div className="event-row" key={`${event.event_id ?? 'legacy'}-${index}`}><span className="event-marker" /><div className="event-body"><div className="event-meta"><span className="event-type">{eventLabel(event)}</span><time>{formatTime(event.ts)}</time></div><EventContent event={event} /></div></div>) : <span className="muted">No events for this selection</span>}</div>;
}

function CallInspector({ call, events }: { call: AgentCall; events: RunEvent[] }) {
  const output = events.filter(isProcessOutput);
  return <div className="inspector"><div className="inspector-facts"><Fact label="Status" value={call.status} /><Fact label="Backend" value={call.backend ?? 'Unknown'} /><Fact label="Model" value={call.model ?? 'Default'} /><Fact label="Exit code" value={call.exit_code === null ? '—' : String(call.exit_code)} /></div><div className="log-heading"><Terminal size={14} /><span>Process output</span></div><div className="process-log">{output.length ? output.map((event, index) => <article key={`${event.event_id}-${index}`}><header><span>{eventLabel(event)}</span><time>{formatTime(event.ts)}</time></header><EventContent event={event} /></article>) : <span className="muted">No process output</span>}</div></div>;
}

function EventContent({ event }: { event: RunEvent }) {
  const payload = eventPayload(event);
  const message = firstString(payload, 'content', 'message', 'text', 'error', 'summary');
  const details = Object.entries(payload).filter(([key]) => !['content', 'message', 'text', 'error', 'summary', 'session'].includes(key));
  return <>{message && <div className="event-message markdown"><ReactMarkdown>{message}</ReactMarkdown></div>}{!message && event.type === 'phase' && <p className="event-message">Entered {event.phase ?? firstString(payload, 'title') ?? 'phase'}</p>}{!message && event.type === 'agent_start' && <p className="event-message">Agent started</p>}{!message && event.type === 'agent_done' && <p className="event-message">Agent completed</p>}{details.length > 0 && <dl className="event-details">{details.map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{formatEventValue(value)}</dd></div>)}</dl>}{!message && details.length === 0 && !['phase', 'agent_start', 'agent_done'].includes(event.type) && <p className="event-message muted">Event recorded</p>}</>;
}

function NewRunDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (run: RunSummary) => void }) {
  const [loops, setLoops] = useState<LoopSummary[]>([]);
  const [loop, setLoop] = useState('');
  const [args, setArgs] = useState('{}');
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void api.loops().then((page) => { setLoops(page.items); setLoop(page.items[0]?.name ?? ''); }); }, []);
  const submit = async () => { try { onCreated(await api.createRun({ loop, args: JSON.parse(args) })); } catch (cause) { setError(messageOf(cause)); } };
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><div className="dialog" role="dialog" aria-modal="true" aria-labelledby="new-run-title"><header><div><span className="eyebrow">Command</span><h2 id="new-run-title">New Run</h2></div><IconButton label="Close" onClick={onClose}><X /></IconButton></header><label>Loop<select value={loop} onChange={(event) => setLoop(event.target.value)}>{loops.map((item) => <option key={item.name}>{item.name}</option>)}</select></label><label>Arguments<textarea value={args} onChange={(event) => setArgs(event.target.value)} spellCheck={false} /></label>{error && <span className="form-error">{error}</span>}<footer><button className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={!loop} onClick={() => void submit()}><Play size={14} />Start Run</button></footer></div></div>;
}

function LoopsWorkspace() {
  const [loops, setLoops] = useState<LoopSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<LoopDetail | null>(null);
  const [tab, setTab] = useState<'overview' | 'workflow' | 'agents'>('overview');
  const [file, setFile] = useState('loop.md');
  const [content, setContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [mobileList, setMobileList] = useState(true);
  useEffect(() => { void api.loops().then((page) => { setLoops(page.items); setSelected(page.items[0]?.name ?? null); }); }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setDetail(null);
    setContent('');
    setFile('');
    void api.loop(selected).then((value) => {
      if (!active) return;
      setDetail(value);
      setTab('overview');
      setFile('loop.md');
      setMobileList(false);
    }).catch((cause) => { if (active) setError(messageOf(cause)); });
    return () => { active = false; };
  }, [selected]);
  useEffect(() => {
    if (!selected || detail?.name !== selected || !file || !detail.files.some((item) => item.path === file && item.previewable)) return;
    let active = true;
    setContent('');
    void api.loopFile(selected, file).then((value) => { if (active) setContent(value.content); }).catch((cause) => { if (active) { setContent(''); setError(messageOf(cause)); } });
    return () => { active = false; };
  }, [selected, detail, file]);
  const selectTab = (next: 'overview' | 'workflow' | 'agents') => {
    setTab(next);
    if (next === 'overview') setFile('loop.md');
    if (next === 'workflow') setFile(detail?.files.find((item) => item.path === 'workflow.py')?.path ?? 'workflow.py');
    if (next === 'agents') setFile(detail?.agents[0]?.path ?? '');
  };
  return <section className={`workspace loops-workspace ${mobileList ? 'show-list' : 'show-detail'}`} data-testid="loops-workspace"><aside className="panel loop-list-panel"><header className="panel-header workspace-title"><div><span className="eyebrow">Declarations</span><h1>Loops</h1></div><GitBranch size={18} /></header><div className="loop-list">{loops.map((loop) => <button key={loop.name} className={selected === loop.name ? 'is-selected' : ''} onClick={() => setSelected(loop.name)}><span><strong>{loop.name}</strong><small>{loop.description || 'No description'}</small></span><span className="loop-count">{loop.agent_count}</span>{!loop.valid && <Status value="failed" />}</button>)}</div></aside><section className="panel loop-detail-panel">{detail ? <><header className="loop-definition-header"><div className="mobile-back"><IconButton label="Back to Loops" onClick={() => setMobileList(true)}><ArrowLeft /></IconButton></div><div className="loop-identity"><span className="eyebrow">Loop definition</span><h2>{detail.name}</h2><p>{detail.description || 'No description'}</p></div><span className="muted">{detail.agents.length} Agents</span></header><nav className="loop-tabs" aria-label="Loop definition sections"><button aria-current={tab === 'overview' ? 'page' : undefined} onClick={() => selectTab('overview')}>Overview</button><button aria-current={tab === 'workflow' ? 'page' : undefined} onClick={() => selectTab('workflow')}>Workflow</button><button aria-current={tab === 'agents' ? 'page' : undefined} onClick={() => selectTab('agents')}>Agents <span>{detail.agents.length}</span></button></nav><div className="loop-content">{tab === 'overview' && <article className="definition-document markdown"><ReactMarkdown>{stripFrontmatter(content)}</ReactMarkdown></article>}{tab === 'workflow' && <article className="definition-code"><header><span>workflow.py</span><span>Read only</span></header><pre className="code-preview">{content}</pre></article>}{tab === 'agents' && (detail.agents.length ? <div className="agents-workspace"><div className="agent-grid">{detail.agents.map((agent) => <button key={agent.path} className={file === agent.path ? 'is-selected' : ''} onClick={() => setFile(agent.path)}><Bot size={16} /><span><strong>{agent.name}</strong><small>{agent.description || agent.path}</small></span><ChevronRight size={15} /></button>)}</div><article className="agent-definition markdown"><ReactMarkdown>{stripFrontmatter(content)}</ReactMarkdown></article></div> : <Empty title="0 Agents" detail="This Loop has no Agent definitions." />)}</div></> : <Empty title="No Loop selected" detail="Select a declaration from the list." />}</section>{error && <div className="toast" role="alert">{error}<IconButton label="Dismiss error" onClick={() => setError(null)}><X /></IconButton></div>}</section>;
}

function BackendsWorkspace() {
  const [items, setItems] = useState<Backend[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [diagnostic, setDiagnostic] = useState<Diagnostic | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = () => api.backends().then(({ items: values }) => { setItems(values); setSelected((current) => current ?? values[0]?.name ?? null); }).catch((cause) => setError(messageOf(cause)));
  useEffect(() => { void load(); }, []);
  const current = items.find((item) => item.name === selected) ?? null;
  const availableCount = items.filter((item) => item.status === 'available').length;
  const diagnose = async () => { if (!selected) return; setBusy(true); try { setDiagnostic(await api.diagnose(selected)); } catch (cause) { setError(messageOf(cause)); } finally { setBusy(false); } };
  return <section className="workspace backends-workspace" data-testid="backends-workspace">
    <header className="backends-header">
      <div><span className="eyebrow">Diagnostics</span><h1>Backends</h1><p>Inspect CLI availability, versions, and runtime configuration.</p></div>
      <div className="backends-actions">
        <button className="secondary-button" onClick={() => void load()}><RefreshCw size={14} />Scan</button>
        <button className="primary-button" disabled={!current || busy} onClick={() => void diagnose()}><Zap size={14} />{busy ? 'Running' : 'Run check'}</button>
      </div>
    </header>
    {items.length ? <>
      <div className="backend-overview">
        <section className="backend-health" aria-label="System health">
          <header><span className="eyebrow">System health</span><Activity size={16} /></header>
          <div className="health-score"><strong>{availableCount}<span>/{items.length}</span></strong><small>Available</small></div>
          <dl><div><dt>Selected</dt><dd>{current?.name ?? '—'}</dd></div><div><dt>Transport</dt><dd>{current?.transport ?? '—'}</dd></div></dl>
        </section>
        <section className="backend-status-panel">
          <header><div><span className="eyebrow">Provider status</span><h2>{items.length} configured providers</h2></div><span className="backend-availability">{availableCount} available</span></header>
          <div className="backend-table">
            <div className="table-head"><span>Backend</span><span>Status</span><span>CLI path</span><span>Version</span><span>Transport</span><span /></div>
            {items.map((backend) => <button key={backend.name} aria-pressed={selected === backend.name} className={selected === backend.name ? 'is-selected' : ''} onClick={() => { setSelected(backend.name); setDiagnostic(null); }}>
              <span className="backend-name"><Server size={14} /><strong>{backend.name}</strong><small>{Object.entries(backend.capabilities).filter(([, value]) => value).map(([key]) => key.replace('_', ' ')).join(' · ') || 'No capabilities reported'}</small></span>
              <Status value={backend.status} /><code>{backend.cli_path ?? 'CLI not found'}</code><span>{backend.version ?? 'Unknown'}</span><span>{backend.transport}</span><ChevronRight size={14} />
            </button>)}
          </div>
        </section>
      </div>
      <section className="diagnostic-panel">
        <header><div><span className="eyebrow">Last diagnostic result</span><h2>{current?.name ?? 'No Backend selected'}</h2></div>{current && <div className="diagnostic-context"><span>{current.version ?? 'Unknown'}</span><code>{current.cli_path ?? 'Not installed'}</code></div>}</header>
        <div className="diagnostic-console">
          <div className="console-heading"><Terminal size={14} /><span>Diagnostic log</span>{diagnostic && <><Status value={diagnostic.status} /><span>exit {diagnostic.exit_code ?? '—'}</span><time>{formatTime(diagnostic.diagnosed_at)}</time></>}</div>
          <pre>{diagnostic ? [diagnostic.stdout, diagnostic.stderr].filter(Boolean).join('\n') || 'Diagnostic completed without output.' : 'Run a diagnostic to inspect CLI availability and configuration.'}</pre>
        </div>
      </section>
    </> : <Empty title="No Backends found" detail="Scan the environment after installing a supported CLI." />}
    {error && <div className="toast" role="alert">{error}<IconButton label="Dismiss error" onClick={() => setError(null)}><X /></IconButton></div>}
  </section>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="fact"><span>{label}</span><strong>{value}</strong></div>; }
function formatDuration(ms: number | null) { if (ms === null) return '—'; if (ms < 1000) return `${ms} ms`; const seconds = Math.round(ms / 1000); return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`; }
function formatTime(value: unknown) { if (typeof value !== 'string') return ''; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
function eventPayload(event: RunEvent): Record<string, unknown> { return event.payload ?? Object.fromEntries(Object.entries(event).filter(([key]) => !['version', 'event_id', 'type', 'ts', 'run_id', 'phase', 'phase_id', 'call_id'].includes(key))); }
function firstString(value: Record<string, unknown>, ...keys: string[]) { for (const key of keys) if (typeof value[key] === 'string' && value[key]) return value[key] as string; return null; }
function eventLabel(event: RunEvent) { return (({ phase: 'Phase entered', agent_start: 'Agent started', agent_message: 'Agent message', agent_message_chunk: 'Agent message', agent_done: 'Agent completed', log: 'Log', error: 'Error' } as Record<string, string>)[event.type] ?? event.type.replaceAll('_', ' ')) || 'Malformed event'; }
function isProcessOutput(event: RunEvent) { return ['agent_message', 'agent_message_chunk', 'log', 'error'].includes(event.type) || Boolean(firstString(eventPayload(event), 'content', 'message', 'text', 'error')) && !['agent_start', 'agent_done', 'phase'].includes(event.type); }
function formatEventValue(value: unknown) { return typeof value === 'string' ? value : value === null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value); }
function stripFrontmatter(value: string) { return value.replace(/^---\s*\r?\n[\s\S]*?\r?\n---\s*\r?\n?/, ''); }
function messageOf(cause: unknown) { return cause instanceof ApiError ? `${cause.code}: ${cause.message}` : cause instanceof Error ? cause.message : 'Unexpected error'; }

export default AppShell;
