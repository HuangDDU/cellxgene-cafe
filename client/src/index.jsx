import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

const roots = new Map();

function mount(containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error("Cafe plugin mount target not found:", containerId);
    return;
  }

  let root = roots.get(containerId);
  if (!root) {
    root = createRoot(container);
    roots.set(containerId, root);
  }

  root.render(<App />);
}

function unmount(containerId) {
  const root = roots.get(containerId);
  if (!root) {
    return;
  }
  root.unmount();
  roots.delete(containerId);
}

window.CafePlugin = {
  mount,
  unmount,
  version: "0.1.0"
};

window.mountCafeApp = mount;
