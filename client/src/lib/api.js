import axios from "axios";

let baseURL = "/api/cafe";
if (typeof window !== "undefined" && window.location.port === "3000") {
  const host = window.location.hostname || "localhost";
  baseURL = `http://${host}:5005/api/cafe`;
}

const api = axios.create({
  baseURL,
});

export async function fetchManifest() {
  const response = await api.get("/manifest");
  return response.data;
}

export async function fetchContext(params = {}) {
  const response = await api.get("/context", { params });
  return response.data;
}

export async function fetchDataSummary() {
  const response = await api.get("/data/summary");
  return response.data;
}

export async function fetchCafeCache() {
  const response = await api.get("/data/cafe-cache");
  return response.data;
}

export async function importTrajectory(name, importAll) {
  const response = await api.post("/data/import-trajectory", { name, all: importAll });
  return response.data;
}

export async function fetchExplorerSummary(params = {}) {
  const response = await api.get("/explorer/summary", { params });
  return response.data;
}

export async function fetchMethodCatalog() {
  const response = await api.get("/method/catalog");
  return response.data;
}

export async function submitMethodJob(payload) {
  const response = await api.post("/job/submit", payload);
  return response.data;
}

export async function queryMethodJob(jobId) {
  const response = await api.get(`/job/${jobId}`);
  return response.data;
}

export async function cancelMethodJob(jobId) {
  const response = await api.post(`/job/${jobId}/cancel`);
  return response.data;
}

export async function fetchMethodJobLogs(jobId) {
  const response = await api.get(`/job/${jobId}/logs`);
  return response.data;
}

export async function fetchMethodJobResult(jobId) {
  const response = await api.get(`/job/${jobId}/result`);
  return response.data;
}

export function buildStaticPlotUrl(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    const text = String(value);
    if (!text) {
      return;
    }
    query.set(key, text);
  });

  const queryString = query.toString();
  if (!queryString) {
    return `${baseURL}/plot/static`;
  }
  return `${baseURL}/plot/static?${queryString}`;
}
