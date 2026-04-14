import axios from "axios";

const api = axios.create({
  baseURL: "/api/cafe"
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
    return "/api/cafe/plot/static";
  }
  return `/api/cafe/plot/static?${queryString}`;
}
