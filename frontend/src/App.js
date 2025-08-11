import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Textarea } from "./components/ui/textarea";
import { Badge } from "./components/ui/badge";
import { Switch } from "./components/ui/switch";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./components/ui/tooltip";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "./components/ui/dialog";
import { Input } from "./components/ui/input";
import { CheckCircle2, Circle, CircleAlert, Play, Rocket, Wand2, Link as LinkIcon, LockKeyhole, Download } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const pretty = (obj) => JSON.stringify(obj, null, 2);

const goalExamples = [
  { label: "Demo: Uppercase (ready)", value: "On POST {msg}, reply with uppercase msg" },
  { label: "Email: Welcome sender (design only)", value: "On POST {email}, send welcome email" },
  { label: "Slack: Notify on lead (design only)", value: "When a new lead arrives, send Slack notification" },
];

const Home = () => {
  const [goal, setGoal] = useState("On POST {msg}, reply with uppercase msg");
  const [design, setDesign] = useState(null);
  const [run, setRun] = useState(null);
  const [useN8n, setUseN8n] = useState(false);
  const [connOpen, setConnOpen] = useState(false);
  const [conn, setConn] = useState({ base_url: "", api_key: "", remember: false, id: null, persisted: false });
  const [artifacts, setArtifacts] = useState([]);
  const [wfGraph, setWfGraph] = useState(null);
  const [loading, setLoading] = useState({ design: false, run: false, saveConn: false });
  const [error, setError] = useState(null);

  useEffect(() => {
    axios
      .get(`${API}/`)
      .then((res) => console.log(res.data.message))
      .catch((e) => console.warn("/api root check failed", e?.message));
  }, []);

  useEffect(() => {
    const loadArtifacts = async () => {
      if (!run?.id) return;
      try {
        const res = await axios.get(`${API}/runs/${run.id}/artifacts`);
        setArtifacts(res.data.artifacts || []);
      } catch {}
      try {
        const res2 = await axios.get(`${API}/runs/${run.id}/workflow`);
        setWfGraph(res2.data);
      } catch { setWfGraph(null); }
    };
    loadArtifacts();
  }, [run?.id]);

  const doDesign = async () => {
    setError(null);
    setRun(null);
    setArtifacts([]);
    setWfGraph(null);
    setLoading((s) => ({ ...s, design: true }));
    try {
      const res = await axios.post(`${API}/design`, { goal });
      setDesign(res.data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading((s) => ({ ...s, design: false }));
    }
  };

  const doRun = async () => {
    if (!design?.workflowContract?.id) return;
    setError(null);
    setLoading((s) => ({ ...s, run: true }));
    try {
      const res = await axios.post(`${API}/test-run`, {
        workflow_contract_id: design.workflowContract.id,
        use_n8n: useN8n,
        n8n_connection_id: conn.id || undefined,
      });
      setRun(res.data.run);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading((s) => ({ ...s, run: false }));
    }
  };

  const saveConnection = async () => {
    setLoading((s) => ({ ...s, saveConn: true }));
    setError(null);
    try {
      const res = await axios.post(`${API}/n8n/connections`, {
        base_url: conn.base_url,
        api_key: conn.api_key,
        remember: !!conn.remember,
      });
      setConn((c) => ({ ...c, id: res.data.id, persisted: res.data.persisted }));
      setConnOpen(false);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading((s) => ({ ...s, saveConn: false }));
    }
  };

  const statusBadge = useMemo(() => {
    if (!run?.status) return null;
    const ok = run.status === "PASS";
    return (
      <div className="flex items-center gap-2">
        <Badge variant={ok ? "default" : "destructive"}>
          <div className="flex items-center gap-2">
            {ok ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}
            {ok ? "PASS" : "FAIL"}
          </div>
        </Badge>
        {run?.junit_path && (
          <span className="text-xs text-muted-foreground">JUnit saved (server)</span>
        )}
      </div>
    );
  }, [run]);

  const ArtifactButtons = () => {
    if (!artifacts?.length) return null;
    const junit = artifacts.find((a) => a.kind === "junit");
    const wf = artifacts.find((a) => a.kind === "workflow_json");
    return (
      <div className="flex flex-wrap gap-2">
        {junit && (
          <a href={`${API}/artifacts/${junit.id}`}>
            <Button variant="outline"><Download size={14} /> Download JUnit</Button>
          </a>
        )}
        {wf && (
          <a href={`${API}/artifacts/${wf.id}`}>
            <Button variant="outline"><Download size={14} /> Download Workflow JSON</Button>
          </a>
        )}
      </div>
    );
  };

  const WorkflowGraph = () => {
    if (!wfGraph?.nodes) return null;
    // naive layout: use provided positions, fallback to grid
    const nodes = wfGraph.nodes;
    const conns = wfGraph.connections || {};
    const width = 700, height = 260;
    const nodeMap = nodes.reduce((acc, n) => { acc[n.name] = n; return acc; }, {});
    const edges = Object.entries(conns).flatMap(([from, data]) => (data?.main || []).flatMap((arr) => arr.map((e) => ({ from, to: e.node }))));
    const pos = (n) => ({ x: (n.position?.[0] || 100)/1.5, y: (n.position?.[1] || 100)/1.5 });
    return (
      <svg width={width} height={height} className="rounded-md border bg-white">
        {edges.map((e, i) => {
          const a = nodeMap[e.from];
          const b = nodeMap[e.to];
          if (!a || !b) return null;
          const pa = pos(a), pb = pos(b);
          return <line key={i} x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} stroke="#9CA3AF" strokeWidth={2} />;
        })}
        {nodes.map((n, i) => {
          const p = pos(n);
          return (
            <g key={i}>
              <rect x={p.x-70} y={p.y-18} width={140} height={36} rx={8} fill="#111827" />
              <text x={p.x} y={p.y+4} textAnchor="middle" fill="#F9FAFB" fontSize="12" fontFamily="monospace">{n.name}</text>
            </g>
          );
        })}
      </svg>
    );
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-neutral-50 to-neutral-100">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Agentic Vibecoder</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Design → Test-run → Assertions. Toggle n8n to execute on your instance.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-2">
                    <Switch checked={useN8n} onCheckedChange={setUseN8n} />
                    <span className="text-sm select-none">Use n8n (Real)</span>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  Executes on your n8n instance with your API key. Uses webhook-test; cleans up after run.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Dialog open={connOpen} onOpenChange={setConnOpen}>
              <DialogTrigger asChild>
                <Button variant="outline"><LockKeyhole size={16} /> Set n8n API</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Connect to your n8n</DialogTitle>
                  <DialogDescription>
                    Enter your n8n base URL and API key. We never log your key. You can optionally store it encrypted on this server.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Base URL</div>
                    <Input placeholder="https://your-instance.app.n8n.cloud" value={conn.base_url} onChange={(e) => setConn({ ...conn, base_url: e.target.value })} />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">API Key</div>
                    <Input type="password" placeholder="X-N8N-API-KEY" value={conn.api_key} onChange={(e) => setConn({ ...conn, api_key: e.target.value })} />
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch checked={conn.remember} onCheckedChange={(v) => setConn({ ...conn, remember: v })} />
                    <span className="text-sm">Remember on this server (encrypted)</span>
                  </div>
                </div>
                <DialogFooter>
                  <Button onClick={saveConnection} disabled={loading.saveConn}>Save</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            {conn.id && (
              <Badge variant="secondary">Connected {conn.persisted ? "(encrypted)" : "(session)"}</Badge>
            )}
          </div>
        </header>

        <main className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="backdrop-blur-md">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Wand2 size={18} /> Goal</CardTitle>
              <CardDescription>Describe the workflow behavior you want.</CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                className="min-h-[120px]"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                {goalExamples.map((g) => (
                  <Badge key={g.label} className="cursor-pointer" onClick={() => setGoal(g.value)}>{g.label}</Badge>
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                <Button onClick={doDesign} disabled={loading.design}>
                  <Rocket size={16} /> {loading.design ? "Designing..." : "Design"}
                </Button>
                <Button onClick={doRun} variant="secondary" disabled={!design || loading.run}>
                  <Play size={16} /> {loading.run ? "Running..." : "Run Test"}
                </Button>
              </div>
              {error && (
                <p className="text-sm text-red-600 mt-3">{String(error)}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Circle size={16} /> Result</CardTitle>
              <CardDescription>Test execution status and assertion results.</CardDescription>
            </CardHeader>
            <CardContent>
              {!run ? (
                <p className="text-sm text-muted-foreground">No run yet. Click Run Test after designing.</p>
              ) : (
                <div className="space-y-3">
                  {statusBadge}
                  <div className="rounded-md border p-3 bg-white">
                    <div className="text-xs text-muted-foreground">Run ID</div>
                    <div className="font-mono text-sm">{run.id}</div>
                  </div>
                  {run?.meta?.n8nError && (
                    <div className="rounded-md border p-3 bg-white text-red-700 text-sm">
                      n8n error: {run.meta.n8nError}
                    </div>
                  )}
                  {run?.meta?.workflowId && (
                    <div className="rounded-md border p-3 bg-white">
                      <div className="text-xs text-muted-foreground mb-2">n8n Workflow</div>
                      <div className="text-sm">Workflow ID: <span className="font-mono">{run.meta.workflowId}</span></div>
                      <div className="text-sm truncate">Test URL: <span className="font-mono">{run.meta.webhookTestUrl}</span></div>
                      <div className="text-sm truncate">Prod URL: <span className="font-mono">{run.meta.webhookProdUrl}</span></div>
                      {run?.meta?.workflowEditorUrl && (
                        <div className="text-sm flex items-center gap-2 mt-2">
                          <LinkIcon size={14} />
                          <a className="underline" href={run.meta.workflowEditorUrl} target="_blank" rel="noreferrer">Open in n8n (login required)</a>
                        </div>
                      )}
                    </div>
                  )}
                  {Array.isArray(run?.meta?.executionLogFirst20) && run.meta.executionLogFirst20.length > 0 && (
                    <div className="rounded-md border p-3 bg-white">
                      <div className="text-xs text-muted-foreground mb-2">Execution log (first 20 lines)</div>
                      <pre className="text-xs font-mono whitespace-pre-wrap">{run.meta.executionLogFirst20.join("\n")}</pre>
                    </div>
                  )}
                  <div className="rounded-md border p-3 bg-white">
                    <div className="text-xs text-muted-foreground mb-1">Downloads</div>
                    <ArtifactButtons />
                  </div>
                  {wfGraph && (
                    <div className="rounded-md border p-3 bg-white">
                      <div className="text-xs text-muted-foreground mb-2">Created n8n Workflow (mini map)</div>
                      <WorkflowGraph />
                    </div>
                  )}
                  <div className="rounded-md border p-3 bg-white">
                    <div className="text-xs text-muted-foreground">Assertions</div>
                    <ul className="mt-2 space-y-2">
                      {run.results?.map((r) => (
                        <li key={r.assertion_id} className="flex items-center justify-between gap-3">
                          <div className="text-sm">
                            <span className="font-mono text-xs text-muted-foreground">{r.operator}</span>
                            <span className="mx-2">—</span>
                            <span className={r.passed ? "text-green-700" : "text-red-700"}>{r.message}</span>
                          </div>
                          <Badge variant={r.passed ? "secondary" : "destructive"}>
                            {r.passed ? "PASS" : "FAIL"}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Design Artifacts</CardTitle>
              <CardDescription>Planner output: contract, fixtures, and assertions.</CardDescription>
            </CardHeader>
            <CardContent>
              {!design ? (
                <p className="text-sm text-muted-foreground">No design yet. Enter a goal and click Design.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="rounded-lg border p-3 bg-white">
                    <div className="text-xs text-muted-foreground mb-2">Workflow Contract</div>
                    <pre className="text-xs font-mono overflow-auto max-h-72">{pretty(design.workflowContract)}</pre>
                  </div>
                  <div className="rounded-lg border p-3 bg-white">
                    <div className="text-xs text-muted-foreground mb-2">Fixture Pack</div>
                    <pre className="text-xs font-mono overflow-auto max-h-72">{pretty(design.fixturePack)}</pre>
                  </div>
                  <div className="rounded-lg border p-3 bg-white">
                    <div className="text-xs text-muted-foreground mb-2">Assertion Pack</div>
                    <pre className="text-xs font-mono overflow-auto max-h-72">{pretty(design.assertionPack)}</pre>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </main>

        <footer className="mt-10 py-8 text-center text-xs text-muted-foreground">
          No secrets are logged. All sensitive headers/queries are redacted in UI.
        </footer>
      </div>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />}>
            <Route index element={<Home />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;