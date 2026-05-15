import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Database,
  FileSearch,
  Gauge,
  Lock,
  ScanText,
  Send,
  ShieldCheck,
  Upload,
  UserRound,
} from "lucide-react";
import "./styles.css";

const API = "http://127.0.0.1:8000/api";

function App() {
  const [users, setUsers] = useState([]);
  const [sources, setSources] = useState([]);
  const [audits, setAudits] = useState([]);
  const [health, setHealth] = useState(null);
  const [selectedUser, setSelectedUser] = useState("");
  const [question, setQuestion] = useState("Which services are at SLA risk and what evidence supports that?");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadForm, setUploadForm] = useState({
    title: "",
    departments: "operations,engineering",
    allowed_roles: "Ops Lead,Platform Engineer",
    min_clearance: "2",
    sensitivity: "internal",
    description: "",
    file: null,
  });

  useEffect(() => {
    Promise.all([
      fetch(`${API}/users/`).then((res) => res.json()),
      fetch(`${API}/sources/`).then((res) => res.json()),
      fetch(`${API}/audits/`).then((res) => res.json()),
      fetch(`${API}/health/`).then((res) => res.json()),
    ])
      .then(([userData, sourceData, auditData, healthData]) => {
        setUsers(userData);
        setSources(sourceData);
        setAudits(auditData);
        setHealth(healthData);
        setSelectedUser(userData[0]?.username || "");
      })
      .catch(() => setError("Backend is not reachable. Start Django on port 8000."));
  }, []);

  const activeUser = useMemo(
    () => users.find((user) => user.username === selectedUser),
    [users, selectedUser],
  );

  const sourceMix = useMemo(() => {
    return sources.reduce((acc, source) => {
      acc[source.source_type] = (acc[source.source_type] || 0) + 1;
      return acc;
    }, {});
  }, [sources]);

  async function refreshWorkspace() {
    const [sourceResponse, auditResponse, healthResponse] = await Promise.all([
      fetch(`${API}/sources/`),
      fetch(`${API}/audits/`),
      fetch(`${API}/health/`),
    ]);
    setSources(await sourceResponse.json());
    setAudits(await auditResponse.json());
    setHealth(await healthResponse.json());
  }

  async function askQuestion(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API}/query/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: selectedUser, question }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Query failed");
      setResult(payload);
      await refreshWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadSource(event) {
    event.preventDefault();
    if (!uploadForm.file) {
      setUploadMessage("Choose a file before uploading.");
      return;
    }
    setUploading(true);
    setError("");
    setUploadMessage("");

    const formData = new FormData();
    Object.entries(uploadForm).forEach(([key, value]) => {
      if (value !== null) formData.append(key, value);
    });

    try {
      const response = await fetch(`${API}/upload/`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || payload.detail || "Upload failed");
      setUploadMessage(
        `Indexed ${payload.source.title} with ${payload.chunks_created} chunks. OCR ${
          payload.ocr.available ? "ready" : "not available"
        }.`,
      );
      setUploadForm((current) => ({ ...current, title: "", description: "", file: null }));
      await refreshWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="shell">
      <section className="masthead">
        <div>
          <p className="eyebrow">Secure enterprise retrieval</p>
          <h1>RAG Intelligence Console</h1>
          <p className="subcopy">
            Query disconnected records, upload new evidence, and inspect how every answer was retrieved.
          </p>
        </div>
        <div className="status-strip">
          <Status icon={<ShieldCheck />} label="RBAC" value="enforced" />
          <Status icon={<Database />} label="Sources" value={sources.length || "0"} />
          <Status icon={<ScanText />} label="OCR" value={health?.ocr?.available ? "ready" : "optional"} />
          <Status icon={<Activity />} label="Model" value={health?.model?.mode || "checking"} />
        </div>
      </section>

      <section className="workspace">
        <aside className="side-panel">
          <div className="panel-title">
            <UserRound size={18} />
            <span>Query as</span>
          </div>
          <select value={selectedUser} onChange={(event) => setSelectedUser(event.target.value)}>
            {users.map((user) => (
              <option key={user.username} value={user.username}>
                {user.display_name}
              </option>
            ))}
          </select>
          {activeUser && (
            <div className="identity">
              <strong>{activeUser.role}</strong>
              <span>{activeUser.department} department</span>
              <span>Clearance L{activeUser.clearance}</span>
            </div>
          )}

          <div className="panel-title source-title">
            <BookOpen size={18} />
            <span>Data silos</span>
          </div>
          <div className="source-list">
            {sources.map((source) => (
              <div className="source-row" key={source.source_id}>
                <span className={`type ${source.source_type}`}>{source.source_type}</span>
                <div>
                  <strong>{source.title}</strong>
                  <small>{source.sensitivity} - {source.chunk_count} chunks</small>
                </div>
              </div>
            ))}
          </div>

          <div className="panel-title source-title">
            <Gauge size={18} />
            <span>Source mix</span>
          </div>
          <div className="mini-chart">
            {Object.entries(sourceMix).map(([type, count]) => (
              <div key={type}>
                <span>{type}</span>
                <div className="bar-track">
                  <div style={{ width: `${Math.max(12, (count / Math.max(sources.length, 1)) * 100)}%` }} />
                </div>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </aside>

        <section className="query-panel">
          <form onSubmit={uploadSource} className="upload-box">
            <div className="panel-title">
              <Upload size={18} />
              <span>Add custom source</span>
            </div>
            <div className="upload-grid">
              <input
                type="file"
                accept=".pdf,.csv,.json,.txt,.md,.sqlite,.db,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
                onChange={(event) => setUploadForm((current) => ({ ...current, file: event.target.files?.[0] || null }))}
              />
              <input
                value={uploadForm.title}
                onChange={(event) => setUploadForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Source title"
              />
              <input
                value={uploadForm.departments}
                onChange={(event) => setUploadForm((current) => ({ ...current, departments: event.target.value }))}
                placeholder="Departments, comma separated"
              />
              <input
                value={uploadForm.allowed_roles}
                onChange={(event) => setUploadForm((current) => ({ ...current, allowed_roles: event.target.value }))}
                placeholder="Allowed roles, comma separated"
              />
              <select
                value={uploadForm.sensitivity}
                onChange={(event) => setUploadForm((current) => ({ ...current, sensitivity: event.target.value }))}
              >
                <option value="internal">internal</option>
                <option value="confidential">confidential</option>
                <option value="restricted">restricted</option>
              </select>
              <input
                type="number"
                min="1"
                max="5"
                value={uploadForm.min_clearance}
                onChange={(event) => setUploadForm((current) => ({ ...current, min_clearance: event.target.value }))}
                placeholder="Min clearance"
              />
            </div>
            <textarea
              className="compact-textarea"
              value={uploadForm.description}
              onChange={(event) => setUploadForm((current) => ({ ...current, description: event.target.value }))}
              rows={2}
              placeholder="Routing hints, e.g. finance vendor invoice risk, security audit alert, operations SLA..."
            />
            <button disabled={uploading}>
              <Upload size={18} />
              {uploading ? "Ingesting" : "Upload and index"}
            </button>
            {uploadMessage && <p className="success-text">{uploadMessage}</p>}
          </form>

          <form onSubmit={askQuestion} className="ask-box">
            <label htmlFor="question">Natural language question</label>
            <textarea
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={4}
              placeholder="Ask about incidents, controls, vendors, architecture, assets, or service reliability..."
            />
            <button disabled={loading || !selectedUser || !question.trim()}>
              <Send size={18} />
              {loading ? "Retrieving" : "Ask securely"}
            </button>
          </form>

          {error && (
            <div className="notice error">
              <AlertTriangle size={18} />
              {error}
            </div>
          )}

          {result && (
            <div className="answer-area">
              <div className="answer-card">
                <div className="answer-header">
                  <FileSearch size={20} />
                  <div>
                    <strong>Grounded answer</strong>
                    <span>Confidence {Math.round(result.confidence * 100)}% - routes {result.routes.join(", ")}</span>
                  </div>
                </div>
                <p>{result.answer}</p>
              </div>

              <div className="explainability-panel">
                <div className="panel-title">
                  <Gauge size={18} />
                  <span>Explainability indicators</span>
                </div>
                <div className="metric-grid">
                  <Metric label="Accessible sources" value={result.explainability.accessible_sources} />
                  <Metric label="Blocked sources" value={result.explainability.blocked_sources} tone="warn" />
                  <Metric label="Candidate chunks" value={result.explainability.candidate_chunks} />
                  <Metric label="Top score" value={`${Math.round(result.explainability.top_score * 100)}%`} />
                </div>
                <div className="trace-row">
                  <strong>Retrieval method</strong>
                  <span>{result.explainability.retrieval_method}</span>
                </div>
                <div className="pill-row">
                  {result.explainability.query_terms.map((term) => (
                    <span key={term}>{term}</span>
                  ))}
                </div>
              </div>

              <div className="evidence-grid">
                <section>
                  <h2>Citations</h2>
                  {result.citations.map((item) => (
                    <article className="citation" key={`${item.source_id}-${item.citation}`}>
                      <strong>{item.title}</strong>
                      <span>
                        {item.citation} - score {item.score} - semantic {item.semantic_score} - lexical {item.lexical_overlap}
                      </span>
                      <div className="score-bars">
                        <ScoreBar label="semantic" value={item.semantic_score} />
                        <ScoreBar label="lexical" value={item.lexical_overlap} />
                      </div>
                      <span>parser {item.parser} - OCR {item.ocr_used ? "used" : "not used"}</span>
                      <p>{item.excerpt}</p>
                    </article>
                  ))}
                </section>
                <section>
                  <h2>Access boundary</h2>
                  {result.blocked_sources.length === 0 && <p className="quiet">No matching source was blocked for this query.</p>}
                  {result.blocked_sources.map((item) => (
                    <article className="blocked" key={item.source_id}>
                      <Lock size={16} />
                      <div>
                        <strong>{item.title}</strong>
                        <span>{item.reason}</span>
                      </div>
                    </article>
                  ))}
                </section>
              </div>
            </div>
          )}
        </section>

        <aside className="audit-panel">
          <div className="panel-title">
            <Activity size={18} />
            <span>Recent audit</span>
          </div>
          {audits.map((audit) => (
            <div className="audit-row" key={audit.id}>
              <strong>{audit.user?.display_name || "Unknown"}</strong>
              <p>{audit.question}</p>
              <small>{Math.round(audit.confidence * 100)}% confidence</small>
            </div>
          ))}
          {audits.length === 0 && <p className="quiet">Queries will appear here after the first run.</p>}
        </aside>
      </section>
    </main>
  );
}

function Metric({ label, value, tone = "good" }) {
  return (
    <div className={`metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ScoreBar({ label, value }) {
  return (
    <div className="score-bar">
      <span>{label}</span>
      <div className="bar-track">
        <div style={{ width: `${Math.min(100, Math.max(2, value * 100))}%` }} />
      </div>
    </div>
  );
}

function Status({ icon, label, value }) {
  return (
    <div className="status">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
