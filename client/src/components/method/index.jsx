import React from "react";
import { connect } from "react-redux";

import { CardSection, StatusBadge } from "../common";
import { cancelMethodJob, fetchMethodCatalog, fetchMethodJobLogs, fetchMethodJobResult, queryMethodJob, submitMethodJob } from "../../lib/api";

function buildDefaultValues(schema = []) {
  const defaults = {};
  schema.forEach((item) => {
    if (item.inputKind === "boolean") { defaults[item.name] = Boolean(item.default); return; }
    if (item.inputKind === "json") { defaults[item.name] = item.default === undefined || item.default === null ? "" : JSON.stringify(item.default, null, 2); return; }
    if (item.inputKind === "choice" && item.choices?.length) { defaults[item.name] = item.default || item.choices[0]; return; }
    if (item.defaultText !== undefined && item.defaultText !== null) { defaults[item.name] = String(item.defaultText); return; }
    if (item.default !== undefined && item.default !== null) { defaults[item.name] = typeof item.default === "string" ? item.default : JSON.stringify(item.default); return; }
    defaults[item.name] = "";
  });
  return defaults;
}

function parseParameterValue(field, rawValue) {
  if (field.inputKind === "boolean") return Boolean(rawValue);
  if (field.inputKind === "number") { if (rawValue === "" || rawValue === null || rawValue === undefined) { if (field.required) throw new Error(`Parameter '${field.name}' is required.`); return undefined; } const n = Number(rawValue); if (Number.isNaN(n)) throw new Error(`Parameter '${field.name}' must be a number.`); return n; }
  if (field.inputKind === "json") { if (!rawValue) { if (field.required) throw new Error(`Parameter '${field.name}' is required.`); return undefined; } try { return JSON.parse(rawValue); } catch (e) { throw new Error(`Parameter '${field.name}' must be valid JSON.`); } }
  if ((rawValue === "" || rawValue === null || rawValue === undefined) && field.required) throw new Error(`Parameter '${field.name}' is required.`);
  if (rawValue === "" || rawValue === null || rawValue === undefined) return undefined;
  return rawValue;
}

function Toast({ message, type, onClose }) { if (!message) return null; React.useEffect(() => { const t = setTimeout(onClose, 6000); return () => clearTimeout(t); }, [message]); return <div className={`cafe-toast cafe-toast-${type || "info"}`} onClick={onClose}>{message}</div>; }

function ParamField({ field, value, onChange }) {
  const fieldId = `method-param-${field.name}`;
  if (field.name === "runtime") { const runtimes = field.availableRuntimes || []; if (!runtimes.length) return null; return (<div className="cafe-field"><label htmlFor={fieldId}>{field.label || "Runtime"}{field.required ? " *" : ""}</label><select id={fieldId} value={value || runtimes[0]?.key || ""} onChange={(e) => onChange(e.target.value)}>{runtimes.map((r) => (<option key={r.key} value={r.key}>{r.label || r.key}</option>))}</select>{field.description && <div className="cafe-note">{field.description}</div>}</div>); }
  if (field.inputKind === "boolean") return (<div className="cafe-field cafe-checkbox-field"><label><input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />{" "}{field.label || field.name}{field.required ? " *" : ""}</label>{field.description && <div className="cafe-note">{field.description}</div>}</div>);
  if (field.inputKind === "choice" && field.choices?.length) return (<div className="cafe-field"><label htmlFor={fieldId}>{field.label || field.name}{field.required ? " *" : ""}</label><select id={fieldId} value={value || ""} onChange={(e) => onChange(e.target.value)}>{field.choices.map((c) => (<option key={c} value={c}>{c}</option>))}</select>{field.description && <div className="cafe-note">{field.description}</div>}</div>);
  if (field.inputKind === "json") return (<div className="cafe-field"><label htmlFor={fieldId}>{field.label || field.name}{field.required ? " *" : ""}</label><textarea id={fieldId} rows={4} value={value || ""} onChange={(e) => onChange(e.target.value)} />{field.description && <div className="cafe-note">{field.description}</div>}</div>);
  return (<div className="cafe-field"><label htmlFor={fieldId}>{field.label || field.name}{field.required ? " *" : ""}</label><input id={fieldId} type={field.inputKind === "number" ? "number" : "text"} value={value ?? ""} onChange={(e) => onChange(e.target.value)} step={field.step || "any"} min={field.min} max={field.max} />{field.description && <div className="cafe-note">{field.description}</div>}</div>);
}

class Method extends React.Component {
  constructor(props) { super(props); this.state = { catalog: null, loading: true, error: "", selectedMethodKey: "", formValues: {}, submitError: "", submitting: false, job: null, jobLogs: "", jobResult: null, toastMsg: "", toastType: "info" }; this._cancelled = false; this._pollTimer = null; }

  componentDidMount() { this._loadCatalog(); }
  componentWillUnmount() { this._cancelled = true; if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; } }

  async _loadCatalog() { this.setState({ loading: true, error: "" }); try { const nextCatalog = await fetchMethodCatalog(); if (this._cancelled) return; const defaultMethod = nextCatalog?.methods?.[0]; const vals = defaultMethod ? buildDefaultValues(defaultMethod.schema) : {}; if (defaultMethod) vals.runtime = defaultMethod.defaultRuntime || defaultMethod.availableRuntimes?.[0]?.key || ""; this.setState({ catalog: nextCatalog, selectedMethodKey: defaultMethod?.key || "", formValues: vals, loading: false }); } catch (err) { if (!this._cancelled) this.setState({ error: err?.message || "Failed to load method catalog", loading: false }); } }

  _selectMethod = (key) => { const method = this.state.catalog?.methods?.find((m) => m.key === key); if (!method) return; const vals = buildDefaultValues(method.schema); vals.runtime = method.defaultRuntime || method.availableRuntimes?.[0]?.key || ""; this.setState({ selectedMethodKey: key, formValues: vals, submitError: "", job: null, jobLogs: "", jobResult: null }); };

  _handleSubmit = async () => { const { selectedMethodKey, formValues } = this.state; const method = this.state.catalog?.methods?.find((m) => m.key === selectedMethodKey); if (!method) return; this.setState({ submitError: "", submitting: true }); try { const params = {}; (method.schema || []).forEach((field) => { if (field.name === "runtime") return; const val = formValues[field.name]; if (val === "" || val === null || val === undefined) { if (field.required) throw new Error(`Parameter '${field.name}' is required.`); return; } params[field.name] = parseParameterValue(field, val); }); const runtime = formValues.runtime || method.defaultRuntime || method.availableRuntimes?.[0]?.key || ""; const job = await submitMethodJob({ method: selectedMethodKey, runtime, params }); if (this._cancelled) return; this.setState({ job, submitting: false, toastMsg: `Job ${job?.jobId} submitted`, toastType: "info" }); this._startPolling(job?.jobId); } catch (err) { if (!this._cancelled) this.setState({ submitError: err?.message || "Submission failed", submitting: false, toastMsg: `Failed: ${err?.message}`, toastType: "error" }); } };

  _startPolling(jobId) { if (this._pollTimer) clearInterval(this._pollTimer); this._pollTimer = setInterval(async () => { try { const snapshot = await queryMethodJob(jobId); if (this._cancelled) return; this.setState({ job: snapshot }); if (snapshot.status === "completed" || snapshot.status === "succeeded") { clearInterval(this._pollTimer); this._pollTimer = null; this.setState({ toastMsg: `Job ${jobId} completed`, toastType: "success" }); } else if (snapshot.status === "failed" || snapshot.status === "cancelled") { clearInterval(this._pollTimer); this._pollTimer = null; this.setState({ toastMsg: `Job ${jobId} ${snapshot.status}`, toastType: "error" }); } } catch (e) { /* ignore */ } }, 1500); }

  _handleCancel = async () => { const { job } = this.state; if (!job?.jobId) return; try { await cancelMethodJob(job.jobId); } catch (e) {} };
  _handleFetchLogs = async () => { const { job } = this.state; if (!job?.jobId) return; try { const logs = await fetchMethodJobLogs(job.jobId); if (!this._cancelled) this.setState({ jobLogs: logs }); } catch (e) {} };
  _handleFetchResult = async () => { const { job } = this.state; if (!job?.jobId) return; try { const result = await fetchMethodJobResult(job.jobId); if (!this._cancelled) this.setState({ jobResult: result }); } catch (e) {} };

  render() {
    const { catalog, loading, error, selectedMethodKey, formValues, submitError, submitting, job, jobLogs, jobResult, toastMsg, toastType } = this.state;
    if (loading) return <div className="cafe-loading">Loading method catalog...</div>;
    if (error) return <div className="cafe-error">{error}</div>;

    const methods = catalog?.methods || [];
    const selectedMethod = methods.find((m) => m.key === selectedMethodKey) || null;
    const schema = selectedMethod?.schema || [];
    const runtimes = selectedMethod?.availableRuntimes || [];

    return (<div><Toast message={toastMsg} type={toastType} onClose={() => this.setState({ toastMsg: "" })} />
      <CardSection title="Method" defaultOpen badge={selectedMethod?.status || null}>
        {!methods.length ? <div className="cafe-note">No methods registered.</div> : (<div className="cafe-method-selector">
          <div className="cafe-field"><label htmlFor="method-select">Select method</label>
            <select id="method-select" value={selectedMethodKey} onChange={(e) => this._selectMethod(e.target.value)}>
              {methods.map((m) => (<option key={m.key} value={m.key}>{m.label || m.key}</option>))}
            </select></div>
          {selectedMethod && <div className="cafe-note" style={{ marginTop: 8 }}>{selectedMethod.description || ""}{selectedMethod.status && <span style={{ marginLeft: 10 }}><StatusBadge status={selectedMethod.status} /></span>}</div>}
        </div>)}
      </CardSection>

      {selectedMethod && (<CardSection title="Parameters" defaultOpen badge={`${schema.length + (runtimes.length ? 1 : 0)} fields`}>
        {runtimes.length > 0 && <div className="cafe-method-param-group">
          <div className="cafe-data-subtitle">Runtime</div>
          {/* <div className="cafe-method-form-grid">
            <ParamField field={{ name: "runtime", label: "Runtime", description: "Execution environment", availableRuntimes: runtimes }} value={formValues.runtime} onChange={(v) => this.setState((prev) => ({ formValues: { ...prev.formValues, runtime: v } }))} />
          </div> */}
        </div>}
        <div className="cafe-method-param-group">
          <div className="cafe-data-subtitle">Method Parameters</div>
          <div className="cafe-method-form-grid">
            {schema.map((field) => (<ParamField key={field.name} field={field} value={formValues[field.name]} onChange={(v) => this.setState((prev) => ({ formValues: { ...prev.formValues, [field.name]: v } }))} />))}
          </div>
        </div>
        {submitError && <div className="cafe-error">{submitError}</div>}
        <div className="cafe-form-actions"><button type="button" className="cafe-btn cafe-btn-primary" onClick={this._handleSubmit} disabled={submitting}>{submitting ? "Submitting..." : "Submit Job"}</button></div>
      </CardSection>)}

      {job && (<CardSection title="Job" defaultOpen badge={job.status}>
        <div className="cafe-method-job-info"><div><strong>ID:</strong> {job.jobId}</div><div><strong>Status:</strong> <StatusBadge status={job.status} /></div>{job.message && <div><strong>Message:</strong> {job.message}</div>}{job.progress !== undefined && <div><strong>Progress:</strong> {job.progress}% {job.stage ? `(${job.stage})` : ""}</div>}</div>
        <div className="cafe-switch-row" style={{ marginTop: 8 }}><button type="button" className="cafe-btn" onClick={this._handleFetchLogs}>Logs</button><button type="button" className="cafe-btn" onClick={this._handleFetchResult}>Result</button>{["queued", "running"].includes(job.status) && <button type="button" className="cafe-btn" onClick={this._handleCancel}>Cancel</button>}</div>
        {jobLogs && <pre className="cafe-json-block" style={{ marginTop: 10 }}>{jobLogs}</pre>}
        {jobResult && <pre className="cafe-json-block" style={{ marginTop: 10 }}>{JSON.stringify(jobResult, null, 2)}</pre>}
      </CardSection>)}
    </div>);
  }
}

export default connect()(Method);
