// Mock API module for tests that import from this path
export const fetchManifest = jest.fn();
export const fetchContext = jest.fn();
export const fetchDataSummary = jest.fn();
export const fetchExplorerSummary = jest.fn();
export const fetchMethodCatalog = jest.fn();
export const submitMethodJob = jest.fn();
export const queryMethodJob = jest.fn();
export const cancelMethodJob = jest.fn();
export const fetchMethodJobLogs = jest.fn();
export const fetchMethodJobResult = jest.fn();
export const buildStaticPlotUrl = jest.fn(() => "/api/cafe/plot/static?view=trajectory");
