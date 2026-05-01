import axios from "axios";

let baseURL = "/api/cafe";
if (typeof window !== "undefined" && window.location.port === "3000") {
  const host = window.location.hostname || "localhost";
  baseURL = `http://${host}:5005/api/cafe`;
}

const api = axios.create({
  baseURL
});

export async function fetchManifest() {
  const response = await api.get("/manifest");
  return response.data;
}

export async function fetchContext(params = {}) {
  const response = await api.get("/context", { params });
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
    return baseURL + "/plot/static";
  }
  return `${baseURL}/plot/static?${queryString}`;
}
