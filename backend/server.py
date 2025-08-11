from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ---------------
# Models
# ---------------
class WorkflowNode(BaseModel):
    id: str
    type: str
    name: str

class WorkflowEdge(BaseModel):
    source: str
    target: str

class WorkflowContract(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    test_webhook_path: str
    prod_webhook_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class HttpFixture(BaseModel):
    method: str
    path: str
    body: Dict[str, Any] = Field(default_factory=dict)

class FixturePack(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_contract_id: str
    fixtures: List[HttpFixture]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Assertion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operator: str
    args: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None

class AssertionPack(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_contract_id: str
    assertions: List[Assertion]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AssertionResult(BaseModel):
    assertion_id: str
    operator: str
    passed: bool
    message: str

class Run(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_contract_id: str
    status: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    results: List[AssertionResult] = Field(default_factory=list)
    junit_path: Optional[str] = None

class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    kind: str
    path: str
    url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ---------------
# Utilities
# ---------------

def mask_secrets(text: str) -> str:
    if not text:
        return text
    # mask token=, key=, secret=, password=
    import re
    return re.sub(r"(?i)(token|key|secret|password)=([^\s&]+)", r"\1=***", text)


def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


# Simple JSONPath-like extractor supporting paths like $.a.b.c and array indices

def jsonpath_get(data: Any, path: str) -> Any:
    if not path or not path.startswith("$"):
        return None
    parts = [p for p in path.split('.') if p]
    cur = data
    for part in parts[1:]:
        if isinstance(cur, list):
            # support [index]
            if part.endswith("]") and "[" in part:
                name, idx = part.split("[")
                idx = idx.replace("]", "")
                if name:
                    try:
                        cur = cur[int(name)]  # unlikely, keep simple
                    except Exception:
                        return None
                try:
                    cur = cur[int(idx)]
                except Exception:
                    return None
                continue
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        elif isinstance(cur, dict):
            # handle field[0]
            key = part
            arr_index = None
            if part.endswith("]") and "[" in part:
                key = part[: part.index("[")]
                try:
                    arr_index = int(part[part.index("[") + 1 : -1])
                except Exception:
                    return None
            if key not in cur:
                return None
            cur = cur[key]
            if arr_index is not None:
                try:
                    cur = cur[arr_index]
                except Exception:
                    return None
        else:
            return None
    return cur


# Assertion engine implementing a simple DSL

def eval_assertion(operator: str, args: Dict[str, Any], trace: Dict[str, Any]) -> (bool, str):
    op = operator
    try:
        if op == "pathTaken":
            expected = args.get("nodes", [])
            actual_types = [n.get("type") for n in trace.get("nodes", [])]
            # check expected appears in order
            idx = 0
            for e in expected:
                try:
                    pos = actual_types.index(e, idx)
                except ValueError:
                    return False, f"Missing node in path: {e}"
                idx = pos + 1
            return True, "Path contains expected sequence"
        if op == "httpOutgoing":
            # args: method?, urlContains?
            method = (args.get("method") or "").upper()
            url_contains = args.get("urlContains") or ""
            found = False
            for call in trace.get("httpOutgoing", []):
                m = (call.get("method") or "").upper()
                u = call.get("url") or ""
                if (not method or method == m) and (not url_contains or url_contains in u):
                    found = True
                    break
            should_exist = args.get("exists", True)
            if should_exist:
                return (found, "Found matching outgoing call" if found else "No matching outgoing call")
            else:
                return (not found, "No outgoing call as expected" if not found else "Unexpected outgoing call found")
        if op in ("eq", "neq", "gt", "lt", "contains", "notContains", "bodyContains"):
            jp = args.get("jsonpath")
            actual = jsonpath_get(trace, jp) if jp else None
            if op == "bodyContains":
                needle = str(args.get("contains"))
                hay = "" if actual is None else str(actual)
                ok = needle in hay
                return ok, f"'{needle}' in '{hay}'" if ok else f"Expected '{needle}' in '{hay}'"
            if op == "contains":
                needle = args.get("value")
                hay = actual
                if isinstance(hay, (list, str)):
                    ok = needle in hay
                    return ok, "contains ok" if ok else f"Expected {needle} in {hay}"
                return False, f"Actual not list/str: {hay}"
            if op == "notContains":
                needle = args.get("value")
                hay = actual
                if isinstance(hay, (list, str)):
                    ok = needle not in hay
                    return ok, "notContains ok" if ok else f"Did not expect {needle} in {hay}"
                return False, f"Actual not list/str: {hay}"
            if op == "eq":
                expected = args.get("value")
                ok = actual == expected
                return ok, f"{actual} == {expected}" if ok else f"{actual} != {expected}"
            if op == "neq":
                expected = args.get("value")
                ok = actual != expected
                return ok, f"{actual} != {expected}" if ok else f"{actual} == {expected}"
            if op in ("gt", "lt"):
                expected = args.get("value")
                try:
                    a = float(actual)
                    b = float(expected)
                except Exception:
                    return False, f"Non-numeric compare: {actual}, {expected}"
                if op == "gt":
                    ok = a > b
                    return ok, f"{a} &gt; {b}" if ok else f"{a} !&gt; {b}"
                else:
                    ok = a < b
                    return ok, f"{a} &lt; {b}" if ok else f"{a} !&lt; {b}"
        return False, f"Unknown operator: {op}"
    except Exception as e:
        return False, f"Exception evaluating {op}: {str(e)}"


def generate_junit_xml(run: Run) -> str:
    # Very small JUnit XML generator
    import xml.etree.ElementTree as ET
    ts = ET.Element("testsuite", name="assertions", tests=str(len(run.results)))
    for r in run.results:
        tc = ET.SubElement(ts, "testcase", name=f"{r.operator}:{r.assertion_id}")
        if not r.passed:
            failure = ET.SubElement(tc, "failure", message=r.message)
            failure.text = r.message
    xml_str = ET.tostring(ts, encoding="unicode")
    return xml_str


# ---------------
# API Schemas
# ---------------
class GoalInput(BaseModel):
    goal: str

class DesignResponse(BaseModel):
    workflowContract: WorkflowContract
    fixturePack: FixturePack
    assertionPack: AssertionPack

class TestRunInput(BaseModel):
    workflow_contract_id: Optional[str] = None

class TestRunResponse(BaseModel):
    run: Run


# ---------------
# Routes
# ---------------
@api_router.get("/")
async def root():
    return {"message": "Hello World"}


@api_router.post("/design", response_model=DesignResponse)
async def design(goal_input: GoalInput):
    goal = goal_input.goal.strip()
    # Minimal rule-based planner just for the uppercase goal
    name = "Uppercase Echo"
    description = "On POST {msg}, reply with uppercase msg"
    nodes = [
        WorkflowNode(id="webhook", type="Webhook", name="Incoming Webhook"),
        WorkflowNode(id="function", type="Function", name="Uppercase Function"),
        WorkflowNode(id="respond", type="Respond", name="HTTP Response"),
    ]
    edges = [
        WorkflowEdge(source="webhook", target="function"),
        WorkflowEdge(source="function", target="respond"),
    ]
    contract = WorkflowContract(
        name=name,
        description=description,
        nodes=nodes,
        edges=edges,
        test_webhook_path="/mock/test/uppercase",
        prod_webhook_path="/mock/prod/uppercase",
    )

    fixture = HttpFixture(method="POST", path=contract.test_webhook_path, body={"msg": "hello"})
    fixture_pack = FixturePack(workflow_contract_id=contract.id, fixtures=[fixture])

    assertions = [
        Assertion(
            operator="pathTaken",
            args={"nodes": ["Webhook", "Function", "Respond"]},
            description="Workflow path includes Webhook → Function → Respond",
        ),
        Assertion(
            operator="eq",
            args={"jsonpath": "$.response.body.upper", "value": "HELLO"},
            description="Response body.upper equals HELLO",
        ),
        Assertion(
            operator="bodyContains",
            args={"jsonpath": "$.response.body.upper", "contains": "HEL"},
            description="Response contains HEL substring",
        ),
    ]
    assertion_pack = AssertionPack(workflow_contract_id=contract.id, assertions=assertions)

    # persist in DB
    await db.workflow_contracts.insert_one(contract.model_dump())
    await db.fixture_packs.insert_one(fixture_pack.model_dump())
    await db.assertion_packs.insert_one(assertion_pack.model_dump())

    return DesignResponse(workflowContract=contract, fixturePack=fixture_pack, assertionPack=assertion_pack)


@api_router.post("/test-run", response_model=TestRunResponse)
async def test_run(payload: TestRunInput):
    if not payload.workflow_contract_id:
        raise HTTPException(status_code=400, detail="workflow_contract_id is required")
    wc = await db.workflow_contracts.find_one({"id": payload.workflow_contract_id})
    if not wc:
        raise HTTPException(status_code=404, detail="WorkflowContract not found")
    fp = await db.fixture_packs.find_one({"workflow_contract_id": payload.workflow_contract_id})
    ap = await db.assertion_packs.find_one({"workflow_contract_id": payload.workflow_contract_id})
    if not fp or not ap:
        raise HTTPException(status_code=404, detail="FixturePack or AssertionPack not found")

    run = Run(workflow_contract_id=payload.workflow_contract_id, status="QUEUED")
    await db.runs.insert_one(run.model_dump())

    # Simulate state machine
    run.status = "PROVISIONING"
    # no-op
    run.status = "EXECUTING"

    # Mock execution: take the only fixture and simulate uppercase response
    try:
        fixture = fp["fixtures"][0]
        body = fixture.get("body", {})
        msg = str(body.get("msg", ""))
        upper = msg.upper()
        trace = {
            "nodes": [
                {"id": "webhook", "type": "Webhook", "status": "completed"},
                {"id": "function", "type": "Function", "status": "completed"},
                {"id": "respond", "type": "Respond", "status": "completed"},
            ],
            "httpOutgoing": [],
            "response": {"status": 200, "body": {"upper": upper}},
        }
    except Exception as e:
        logging.exception("Execution error: %s", mask_secrets(str(e)))
        run.status = "FAIL"
        run.finished_at = datetime.utcnow()
        await db.runs.update_one({"id": run.id}, {"$set": run.model_dump()})
        return TestRunResponse(run=run)

    run.status = "ASSERTING"
    results: List[AssertionResult] = []
    for a in ap["assertions"]:
        ok, message = eval_assertion(a.get("operator"), a.get("args", {}), trace)
        results.append(AssertionResult(assertion_id=a.get("id"), operator=a.get("operator"), passed=ok, message=message))

    run.results = results
    all_pass = all(r.passed for r in results)
    run.status = "PASS" if all_pass else "FAIL"
    run.finished_at = datetime.utcnow()

    # Generate JUnit
    junit_xml = generate_junit_xml(run)
    artifacts_dir = ROOT_DIR / "artifacts"
    ensure_dir(artifacts_dir / "tmp")
    junit_path = artifacts_dir / f"{run.id}.xml"
    with open(junit_path, "w", encoding="utf-8") as f:
        f.write(junit_xml)
    run.junit_path = str(junit_path)

    await db.runs.update_one({"id": run.id}, {"$set": run.model_dump()})

    # Also persist artifact record (mock URL)
    artifact = Artifact(run_id=run.id, kind="junit", path=str(junit_path), url=None)
    await db.artifacts.insert_one(artifact.model_dump())

    return TestRunResponse(run=run)


@api_router.get("/runs/{run_id}", response_model=TestRunResponse)
async def get_run(run_id: str):
    r = await db.runs.find_one({"id": run_id})
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    return TestRunResponse(run=Run(**r))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()