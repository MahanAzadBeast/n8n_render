import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Textarea } from "./components/ui/textarea";
import { Badge } from "./components/ui/badge";
import { CheckCircle2, Circle, CircleAlert, Play, Rocket, Wand2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const pretty = (obj) => JSON.stringify(obj, null, 2);

const Home = () => {
  const [goal, setGoal] = useState("On POST {msg}, reply with uppercase msg");
  const [design, setDesign] = useState(null);
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState({ design: false, run: false });
  const [error, setError] = useState(null);

  useEffect(() => {
    // sanity check API
    axios
      .get(`${API}/`)
      .then((res) => console.log(res.data.message))
      .catch((e) => console.warn("/api root check failed", e?.message));
  }, []);

  const doDesign = async () => {
    setError(null);
    setRun(null);
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
      });
      setRun(res.data.run);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading((s) => ({ ...s, run: false }));
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

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-neutral-50 to-neutral-100">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Agentic Vibecoder (Mock)</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Design → Test-run → Assertions without external calls. Powered by your /api.
            </p>
          </div>
          <div className="flex gap-2">
            <a href="https://emergent.sh" target="_blank" rel="noreferrer">
              <Badge variant="secondary">Docs</Badge>
            </a>
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
          No secrets are logged. All mock operations are local.
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