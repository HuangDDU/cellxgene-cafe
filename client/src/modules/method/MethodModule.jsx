import React, { useEffect, useMemo, useState } from "react";

import {
  cancelMethodJob,
  fetchMethodCatalog,
  fetchMethodJobLogs,
  fetchMethodJobResult,
  queryMethodJob,
  submitMethodJob,
} from "../../lib/api";

function buildDefaultValues(schema = []) {
  const defaults = {};
  schema.forEach((item) => {
    if (item.inputKind === "boolean") {
      defaults[item.name] = Boolean(item.default);
      return;
    }
    if (item.inputKind === "json") {
      defaults[item.name] =
        item.default === undefined || item.default === null ? "" : JSON.stringify(item.default, null, 2);
      return;
    }
    if (item.defaultText !== undefined && item.defaultText !== null) {
      defaults[item.name] = String(item.defaultText);
      return;
    }
    if (item.default !== undefined && item.default !== null) {
      defaults[item.name] = typeof item.default === "string" ? item.default : JSON.stringify(item.default);
      return;
    }
    defaults[item.name] = "";
  });
  return defaults;
}

function parseParameterValue(field, rawValue) {
  if (field.inputKind === "boolean") {
    return Boolean(rawValue);
  }
  if (field.inputKind === "number") {
    if (rawValue === "" || rawValue === null || rawValue === undefined) {
      if (field.required) {
        throw new Error(`Parameter '${field.name}' is required.`);
      }
      return undefined;
    }
    const number = Number(rawValue);
    if (Number.isNaN(number)) {
      throw new Error(`Parameter '${field.name}' must be a number.`);
    }
    return number;
  }
  if (field.inputKind === "json") {
    if (!rawValue) {
      if (field.required) {
        throw new Error(`Parameter '${field.name}' is required.`);
      }
      return undefined;
    }
    try {
      return JSON.parse(rawValue);
    } catch (error) {
      throw new Error(`Parameter '${field.name}' must be valid JSON.`);
    }
  }
  if ((rawValue === "" || rawValue === null || rawValue === undefined) && field.required) {
    throw new Error(`Parameter '${field.name}' is required.`);
  }
  if (rawValue === "" || rawValue === null || rawValue === undefined) {
    return undefined;
  }
  return rawValue;
}

function StatusBadge({ status }) {
  const tone = status || "unknown";
  return <span className={`cafe-status-badge is-${tone}`}>{tone}</span>;
}

function MethodModule({ context, onJobSucceeded }) {
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedMethodKey, setSelectedMethodKey] = useState("");
  const [selectedRuntime, setSelectedRuntime] = useState("");
  const [formValues, setFormValues] = useState({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState(null);
  const [jobLogs, setJobLogs] = useState("");
  const [jobResult, setJobResult] = useState(null);
  const [lastSuccessJobId, setLastSuccessJobId] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCatalog() {
      setLoading(true);
      setError("");
      try {
        const nextCatalog = await fetchMethodCatalog();
        if (cancelled) {
          return;
        }
        setCatalog(nextCatalog);
        const defaultMethod = nextCatalog?.methods?.[0];
        if (defaultMethod) {
          setSelectedMethodKey(defaultMethod.key);
          setSelectedRuntime(defaultMethod.defaultRuntime || defaultMethod.availableRuntimes?.[0]?.key || "");
          setFormValues(buildDefaultValues(defaultMethod.schema));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Failed to load method catalog");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedMethod = useMemo(
    () => catalog?.methods?.find((item) => item.key === selectedMethodKey) || null,
    [catalog, selectedMethodKey]
  );

  const loadedTrajectoryNames = useMemo(() => {
    const names = new Set();
    (context?.trajectories || []).forEach((item) => {
      if (item) {
        names.add(String(item));
      }
    });
    (context?.trajectoryOptions || []).forEach((item) => {
      if (item?.loaded && item?.id) {
        names.add(String(item.id));
      }
    });
    return names;
  }, [context]);

  const selectedMethodLoaded = Boolean(selectedMethod && loadedTrajectoryNames.has(selectedMethod.key));

  useEffect(() => {
    if (!selectedMethod) {
      return;
    }
    setSelectedRuntime(selectedMethod.defaultRuntime || selectedMethod.availableRuntimes?.[0]?.key || "");
    setFormValues(buildDefaultValues(selectedMethod.schema));
    setSubmitError("");
  }, [selectedMethodKey, selectedMethod]);

  useEffect(() => {
    if (!job?.jobId) {
      return undefined;
    }

    const shouldPoll = ["queued", "running", "cancel_requested"].includes(job.status);
    let intervalId = null;
    let cancelled = false;

    async function refreshJobState() {
      try {
        const [nextJob, nextLogs] = await Promise.all([queryMethodJob(job.jobId), fetchMethodJobLogs(job.jobId)]);
        if (cancelled) {
          return;
        }
        setJob(nextJob);
        setJobLogs(nextLogs.logs || "");
        if (["succeeded", "failed", "cancelled"].includes(nextJob.status)) {
          const nextResult = await fetchMethodJobResult(job.jobId);
          if (!cancelled) {
            setJobResult(nextResult);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setSubmitError(err?.message || "Failed to refresh method job");
        }
      }
    }

    refreshJobState();
    if (shouldPoll) {
      intervalId = window.setInterval(refreshJobState, 2500);
    }

    return () => {
      cancelled = true;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [job?.jobId, job?.status]);

  useEffect(() => {
    if (job?.status !== "succeeded" || !job?.jobId || job.jobId === lastSuccessJobId) {
      return;
    }
    const resolvedResult = jobResult || job?.result || null;
    if (!resolvedResult?.trajectoryId) {
      return;
    }
    setLastSuccessJobId(job.jobId);
    if (typeof onJobSucceeded === "function") {
      onJobSucceeded({
        ...job,
        result: resolvedResult,
      });
    }
  }, [job, jobResult, lastSuccessJobId, onJobSucceeded]);

  const onSelectMethod = (methodKey) => {
    setSelectedMethodKey(methodKey);
    setJob(null);
    setJobLogs("");
    setJobResult(null);
  };

  const onChangeField = (fieldName, value) => {
    setFormValues((prev) => ({
      ...prev,
      [fieldName]: value,
    }));
  };

  const onSubmit = async () => {
    if (!selectedMethod) {
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    try {
      const parameters = {};
      selectedMethod.schema.forEach((field) => {
        const parsedValue = parseParameterValue(field, formValues[field.name]);
        if (parsedValue !== undefined) {
          parameters[field.name] = parsedValue;
        }
      });
      const nextJob = await submitMethodJob({
        methodName: selectedMethod.key,
        backendName: selectedRuntime,
        trajectoryId: selectedMethod.key,
        parameters,
      });
      setJob(nextJob);
      setJobLogs("");
      setJobResult(null);
    } catch (err) {
      setSubmitError(err?.message || "Failed to submit method job");
    } finally {
      setSubmitting(false);
    }
  };

  const onCancel = async () => {
    if (!job?.jobId) {
      return;
    }
    try {
      const nextJob = await cancelMethodJob(job.jobId);
      setJob(nextJob);
    } catch (err) {
      setSubmitError(err?.message || "Failed to cancel method job");
    }
  };

  if (loading) {
    return <div className="cafe-loading">Loading method catalog...</div>;
  }

  if (error) {
    return <div className="cafe-error">{error}</div>;
  }

  return (
    <div>
      <div className="cafe-card">
        <h4>Method Overview</h4>
        <div className="cafe-info-grid">
          <div className="cafe-info-item">
            <div className="cafe-info-label">Dataset</div>
            <div className="cafe-info-value">{catalog?.dataset?.name || context?.dataset?.name || "dataset"}</div>
          </div>
          <div className="cafe-info-item">
            <div className="cafe-info-label">Methods</div>
            <div className="cafe-info-value">{catalog?.methods?.length || 0}</div>
          </div>
          <div className="cafe-info-item">
            <div className="cafe-info-label">Runtimes</div>
            <div className="cafe-info-value">
              {(catalog?.runtimeOptions || []).map((item) => item.label).join(", ") || "none"}
            </div>
          </div>
        </div>
      </div>

      <div className="cafe-method-layout">
        <div className="cafe-card">
          <h4>Available Methods</h4>
          <div className="cafe-method-list">
            {(catalog?.methods || []).map((method) => (
              <button
                key={method.key}
                type="button"
                className={`cafe-method-item ${selectedMethodKey === method.key ? "is-active" : ""}`}
                onClick={() => onSelectMethod(method.key)}
              >
                <span className="cafe-method-name">{method.label}</span>
                <span className="cafe-note">{method.availableRuntimes?.map((item) => item.label).join(", ") || "n/a"}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="cafe-card">
            <h4>Method Configuration</h4>
            {selectedMethod ? (
              <div>
                <div className="cafe-method-header">
                  <div>
                    <div className="cafe-method-title">{selectedMethod.label}</div>
                    <div className="cafe-note">{selectedMethod.description || "No description available."}</div>
                    <div className="cafe-note" style={{ marginTop: "6px" }}>
                      {selectedMethodLoaded
                        ? "This method is already loaded. Submitting again will rerun it and overwrite the existing result."
                        : "Submitting will create or refresh the trajectory result for this method."}
                    </div>
                  </div>
                </div>

                <div className="cafe-field" style={{ marginBottom: "12px" }}>
                  <label htmlFor="method-runtime">Runtime</label>
                  <select
                    id="method-runtime"
                    value={selectedRuntime}
                    onChange={(event) => setSelectedRuntime(event.target.value)}
                  >
                    {(selectedMethod.availableRuntimes || []).map((runtime) => (
                      <option key={runtime.key} value={runtime.key}>
                        {runtime.label} ({runtime.target})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="cafe-method-form-grid">
                  {(selectedMethod.schema || []).map((field) => (
                    <div key={field.name} className="cafe-field">
                      <label htmlFor={`field-${field.name}`}>
                        {field.name}
                        {field.required ? " *" : ""}
                      </label>
                      {field.inputKind === "boolean" ? (
                        <label className="cafe-checkbox-field">
                          <input
                            id={`field-${field.name}`}
                            type="checkbox"
                            checked={Boolean(formValues[field.name])}
                            onChange={(event) => onChangeField(field.name, event.target.checked)}
                          />
                          <span>{field.annotation || "boolean"}</span>
                        </label>
                      ) : field.inputKind === "json" ? (
                        <textarea
                          id={`field-${field.name}`}
                          className="cafe-textarea"
                          rows={4}
                          value={formValues[field.name] ?? ""}
                          onChange={(event) => onChangeField(field.name, event.target.value)}
                        />
                      ) : (
                        <input
                          id={`field-${field.name}`}
                          type={field.inputKind === "number" ? "number" : "text"}
                          value={formValues[field.name] ?? ""}
                          onChange={(event) => onChangeField(field.name, event.target.value)}
                        />
                      )}
                      <div className="cafe-note">
                        {field.annotation || field.kind}
                        {field.default !== undefined && field.default !== null ? ` | default: ${field.defaultText}` : ""}
                      </div>
                    </div>
                  ))}
                </div>

                {submitError ? <div className="cafe-error">{submitError}</div> : null}

                <div className="cafe-form-actions">
                  <button type="button" className="cafe-btn" onClick={onSubmit} disabled={submitting || !selectedRuntime}>
                    {submitting ? "Submitting..." : selectedMethodLoaded ? "Rerun Method" : "Submit Job"}
                  </button>
                  {job?.jobId ? (
                    <button
                      type="button"
                      className="cafe-btn"
                      onClick={onCancel}
                      disabled={!["queued", "running", "cancel_requested"].includes(job.status)}
                    >
                      Cancel Job
                    </button>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="cafe-note">No method is available in the current catalog.</div>
            )}
          </div>

          <div className="cafe-card">
            <h4>Job Status</h4>
            {!job ? (
              <div className="cafe-note">No job submitted yet.</div>
            ) : (
              <div>
                <div className="cafe-job-header">
                  <div>
                    <div className="cafe-method-title">{job.methodName}</div>
                    <div className="cafe-note">{job.jobId}</div>
                  </div>
                  <StatusBadge status={job.status} />
                </div>
                <div className="cafe-info-grid" style={{ marginTop: "10px" }}>
                  <div className="cafe-info-item">
                    <div className="cafe-info-label">Runtime</div>
                    <div className="cafe-info-value">{job.backendName}</div>
                  </div>
                  <div className="cafe-info-item">
                    <div className="cafe-info-label">Created</div>
                    <div className="cafe-info-value">{job.createdAt}</div>
                  </div>
                  <div className="cafe-info-item">
                    <div className="cafe-info-label">Updated</div>
                    <div className="cafe-info-value">{job.updatedAt}</div>
                  </div>
                </div>
                {job.error ? <div className="cafe-error">{job.error}</div> : null}
              </div>
            )}
          </div>

          <div className="cafe-card">
            <h4>Logs</h4>
            <pre className="cafe-log-block">{jobLogs || "No logs yet."}</pre>
          </div>

          <div className="cafe-card">
            <h4>Result</h4>
            <pre className="cafe-json-block">
              {JSON.stringify(jobResult || { status: job?.status || "idle", result: null }, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MethodModule;
