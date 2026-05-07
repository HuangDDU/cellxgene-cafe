import React from "react";

import {
  cancelMethodJob,
  fetchMethodCatalog,
  fetchMethodJobLogs,
  fetchMethodJobResult,
  queryMethodJob,
  submitMethodJob,
} from "../../lib/api";

// ---- helpers ----

function buildDefaultValues(schema = []) {
  const defaults = {};
  schema.forEach((item) => {
    if (item.inputKind === "boolean") {
      defaults[item.name] = Boolean(item.default);
      return;
    }
    if (item.inputKind === "json") {
      defaults[item.name] =
        item.default === undefined || item.default === null
          ? ""
          : JSON.stringify(item.default, null, 2);
      return;
    }
    if (item.defaultText !== undefined && item.defaultText !== null) {
      defaults[item.name] = String(item.defaultText);
      return;
    }
    if (item.default !== undefined && item.default !== null) {
      defaults[item.name] =
        typeof item.default === "string" ? item.default : JSON.stringify(item.default);
      return;
    }
    defaults[item.name] = "";
  });
  return defaults;
}

function parseParameterValue(field, rawValue) {
  if (field.inputKind === "boolean") return Boolean(rawValue);
  if (field.inputKind === "number") {
    if (rawValue === "" || rawValue === null || rawValue === undefined) {
      if (field.required) throw new Error(`Parameter '${field.name}' is required.`);
      return undefined;
    }
    const n = Number(rawValue);
    if (Number.isNaN(n)) throw new Error(`Parameter '${field.name}' must be a number.`);
    return n;
  }
  if (field.inputKind === "json") {
    if (!rawValue) {
      if (field.required) throw new Error(`Parameter '${field.name}' is required.`);
      return undefined;
    }
    try {
      return JSON.parse(rawValue);
    } catch (e) {
      throw new Error(`Parameter '${field.name}' must be valid JSON.`);
    }
  }
  if ((rawValue === "" || rawValue === null || rawValue === undefined) && field.required)
    throw new Error(`Parameter '${field.name}' is required.`);
  if (rawValue === "" || rawValue === null || rawValue === undefined) return undefined;
  return rawValue;
}

class StatusBadge extends React.Component {
  render() {
    return (
      <span className={`cafe-status-badge is-${this.props.status || "unknown"}`}>
        {this.props.status || "unknown"}
      </span>
    );
  }
}

// ---- main component ----

export default class Method extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      catalog: null,
      loading: true,
      error: "",
      selectedMethodKey: "",
      selectedRuntime: "",
      formValues: {},
      submitError: "",
      submitting: false,
      job: null,
      jobLogs: "",
      jobResult: null,
      lastSuccessJobId: "",
    };
    this._cancelled = false;
    this._pollTimer = null;
  }

  componentDidMount() {
    this._loadCatalog();
  }

  componentWillUnmount() {
    this._cancelled = true;
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  async _loadCatalog() {
    this.setState({ loading: true, error: "" });
    try {
      const nextCatalog = await fetchMethodCatalog();
      if (this._cancelled) return;
      const defaultMethod = nextCatalog?.methods?.[0];
      this.setState({
        catalog: nextCatalog,
        selectedMethodKey: defaultMethod?.key || "",
        selectedRuntime:
          defaultMethod?.defaultRuntime || defaultMethod?.availableRuntimes?.[0]?.key || "",
        formValues: defaultMethod ? buildDefaultValues(defaultMethod.schema) : {},
        loading: false,
      });
    } catch (err) {
      if (!this._cancelled)
        this.setState({ error: err?.message || "Failed to load method catalog", loading: false });
    }
  }

  _selectMethod = (key) => {
    const method = this.state.catalog?.methods?.find((m) => m.key === key);
    if (!method) return;
    this.setState({
      selectedMethodKey: key,
      selectedRuntime: method.defaultRuntime || method.availableRuntimes?.[0]?.key || "",
      formValues: buildDefaultValues(method.schema),
      submitError: "",
      job: null,
      jobLogs: "",
      jobResult: null,
    });
  };

  _handleSubmit = async () => {
    const { selectedMethodKey, selectedRuntime, formValues } = this.state;
    const method = this.state.catalog?.methods?.find((m) => m.key === selectedMethodKey);
    if (!method) return;
    this.setState({ submitError: "", submitting: true });
    try {
      const params = {};
      (method.schema || []).forEach((field) => {
        const val = formValues[field.name];
        if (val === "" || val === null || val === undefined) {
          if (field.required) throw new Error(`Parameter '${field.name}' is required.`);
          return;
        }
        params[field.name] = parseParameterValue(field, val);
      });
      const job = await submitMethodJob({
        method: selectedMethodKey,
        runtime: selectedRuntime,
        params,
      });
      if (this._cancelled) return;
      this.setState({ job, submitting: false, lastSuccessJobId: job?.jobId || "" });
      this._startPolling(job?.jobId);
    } catch (err) {
      if (!this._cancelled)
        this.setState({ submitError: err?.message || "Job submission failed", submitting: false });
    }
  };

  _startPolling(jobId) {
    if (this._pollTimer) clearInterval(this._pollTimer);
    this._pollTimer = setInterval(async () => {
      try {
        const snapshot = await queryMethodJob(jobId);
        if (this._cancelled) return;
        this.setState({ job: snapshot });
        if (snapshot.status === "completed" || snapshot.status === "succeeded") {
          if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
          }
        } else if (snapshot.status === "failed" || snapshot.status === "cancelled") {
          if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
          }
        }
      } catch (e) {
        /* polling error, ignore */
      }
    }, 1200);
  }

  _handleCancel = async () => {
    const { job } = this.state;
    if (!job?.jobId) return;
    try {
      await cancelMethodJob(job.jobId);
    } catch (e) {
      /* ignore */
    }
  };

  _handleFetchLogs = async () => {
    const { job } = this.state;
    if (!job?.jobId) return;
    try {
      const logs = await fetchMethodJobLogs(job.jobId);
      if (!this._cancelled) this.setState({ jobLogs: logs });
    } catch (e) {
      /* ignore */
    }
  };

  _handleFetchResult = async () => {
    const { job } = this.state;
    if (!job?.jobId) return;
    try {
      const result = await fetchMethodJobResult(job.jobId);
      if (!this._cancelled) this.setState({ jobResult: result });
    } catch (e) {
      /* ignore */
    }
  };

  render() {
    const { context } = this.props;
    const {
      catalog,
      loading,
      error,
      selectedMethodKey,
      selectedRuntime,
      formValues,
      submitError,
      submitting,
      job,
      jobLogs,
      jobResult,
    } = this.state;
    if (loading) return <div className="cafe-loading">Loading method catalog...</div>;
    if (error) return <div className="cafe-error">{error}</div>;

    const methods = catalog?.methods || [];
    const selectedMethod = methods.find((m) => m.key === selectedMethodKey) || null;
    const runtimes = selectedMethod?.availableRuntimes || [];

    return (
      <div>
        <div className="cafe-card">
          <h4>Method Catalog</h4>
          {!methods.length ? (
            <div className="cafe-note">No methods registered in this dataset.</div>
          ) : (
            <div className="cafe-method-grid">
              {methods.map((m) => (
                <div
                  key={m.key}
                  className={`cafe-method-card ${selectedMethodKey === m.key ? "is-selected" : ""}`}
                  onClick={() => this._selectMethod(m.key)}
                >
                  <div className="cafe-method-header">
                    <div className="cafe-method-title">{m.label || m.key}</div>
                    <StatusBadge status={m.status || "available"} />
                  </div>
                  <div className="cafe-note" style={{ marginTop: "6px" }}>
                    {m.description || "No description."}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {selectedMethod && (
          <div className="cafe-card">
            <h4>Parameters: {selectedMethod.label || selectedMethod.key}</h4>
            <div className="cafe-method-form">
              <div className="cafe-field">
                <label>Runtime</label>
                <select
                  value={selectedRuntime}
                  onChange={(e) => this.setState({ selectedRuntime: e.target.value })}
                >
                  {runtimes.map((r) => (
                    <option key={r.key} value={r.key}>
                      {r.label || r.key}
                    </option>
                  ))}
                </select>
              </div>
              {(selectedMethod.schema || []).map((field) => (
                <div key={field.name} className="cafe-field">
                  <label>
                    {field.label || field.name} {field.required ? "*" : ""}
                  </label>
                  {field.inputKind === "boolean" ? (
                    <input
                      type="checkbox"
                      checked={!!formValues[field.name]}
                      onChange={(e) =>
                        this.setState((prev) => ({
                          formValues: { ...prev.formValues, [field.name]: e.target.checked },
                        }))
                      }
                    />
                  ) : field.inputKind === "json" ? (
                    <textarea
                      rows={4}
                      value={formValues[field.name] || ""}
                      onChange={(e) =>
                        this.setState((prev) => ({
                          formValues: { ...prev.formValues, [field.name]: e.target.value },
                        }))
                      }
                    />
                  ) : (
                    <input
                      type="text"
                      value={formValues[field.name] || ""}
                      onChange={(e) =>
                        this.setState((prev) => ({
                          formValues: { ...prev.formValues, [field.name]: e.target.value },
                        }))
                      }
                    />
                  )}
                  <div className="cafe-note">{field.description}</div>
                </div>
              ))}
              {submitError && <div className="cafe-error">{submitError}</div>}
              <button
                type="button"
                className="cafe-btn"
                onClick={this._handleSubmit}
                disabled={submitting}
              >
                {submitting ? "Submitting..." : "Submit Job"}
              </button>
            </div>
          </div>
        )}

        {job && (
          <div className="cafe-card">
            <h4>Job Status</h4>
            <div className="cafe-method-job-info">
              <div>
                <strong>ID:</strong> {job.jobId}
              </div>
              <div>
                <strong>Status:</strong> <StatusBadge status={job.status} />
              </div>
              {job.message && (
                <div>
                  <strong>Message:</strong> {job.message}
                </div>
              )}
            </div>
            <div className="cafe-switch-row" style={{ marginTop: "8px" }}>
              <button type="button" className="cafe-btn" onClick={this._handleFetchLogs}>
                Fetch Logs
              </button>
              <button type="button" className="cafe-btn" onClick={this._handleFetchResult}>
                Fetch Result
              </button>
              {["queued", "running"].includes(job.status) && (
                <button type="button" className="cafe-btn" onClick={this._handleCancel}>
                  Cancel
                </button>
              )}
            </div>
            {jobLogs && (
              <pre className="cafe-json-block" style={{ marginTop: "10px" }}>
                {jobLogs}
              </pre>
            )}
            {jobResult && (
              <pre className="cafe-json-block" style={{ marginTop: "10px" }}>
                {JSON.stringify(jobResult, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    );
  }
}
