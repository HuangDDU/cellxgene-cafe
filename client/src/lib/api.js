import axios from "axios";

let baseURL = "/api/cafe";
if (typeof window !== "undefined" && window.location.port === "3000") {
  const host = window.location.hostname || "localhost";
  baseURL = `http://${host}:5005/api/cafe`;
}

const api = axios.create({
  baseURL,
});

const getCache = new Map();
const GET_CACHE_TTL_MS = 5 * 60 * 1000;

function cacheKey(path, params = {}) {
  const query = new URLSearchParams();
  Object.keys(params || {}).sort().forEach((key) => {
    const value = params[key];
    if (value === undefined || value === null) {
      return;
    }
    query.set(key, String(value));
  });
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

async function cachedGet(path, params = {}) {
  const key = cacheKey(path, params);
  const cached = getCache.get(key);
  if (cached && Date.now() - cached.startedAt < GET_CACHE_TTL_MS) {
    return cached.request;
  }
  if (cached) {
    getCache.delete(key);
  }

  const requestArgs = Object.keys(params || {}).length ? [path, { params }] : [path];
  const request = api.get(...requestArgs)
    .then((response) => response.data)
    .catch((error) => {
      getCache.delete(key);
      throw error;
    });
  getCache.set(key, { request, startedAt: Date.now() });
  return request;
}

export function clearCafeApiCache() {
  getCache.clear();
}

export async function fetchManifest() {
  return cachedGet("/manifest");
}

export async function fetchContext(params = {}) {
  return cachedGet("/context", params);
}

export async function fetchDataSummary() {
  return cachedGet("/data/summary");
}

export async function fetchCafeCache() {
  return cachedGet("/data/cafe-cache");
}

export async function importTrajectory(name, importAll) {
  const response = await api.post("/data/import-trajectory", { name, all: importAll });
  clearCafeApiCache();
  return response.data;
}

export async function fetchExplorerSummary(params = {}) {
  return cachedGet("/explorer/summary", params);
}

export async function fetchMethodCatalog() {
  return cachedGet("/method/catalog");
}

export async function prefetchModuleData(selection = {}) {
  const trajectory = selection.trajectory || "";
  const layout = selection.layout || "";
  return Promise.allSettled([
    fetchDataSummary(),
    fetchCafeCache(),
    fetchMethodCatalog(),
    fetchExplorerSummary({ trajectory, layout, includeHeavy: "0" }),
  ]);
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
