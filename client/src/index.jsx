import React from "react";
import { createRoot } from "react-dom/client";

import App from "./components/app";
import { CafeAppProvider } from "./lib/appProvider";
import "./styles.css";

const roots = new Map();
let hotAcceptRegistered = false;

function render(root) {
  root.render(
    <CafeAppProvider>
      <App />
    </CafeAppProvider>,
  );

  if (module.hot && !hotAcceptRegistered) {
    hotAcceptRegistered = true;
    module.hot.accept("./components/app", () => {
      root.render(
        <CafeAppProvider>
          <App />
        </CafeAppProvider>,
      );
    });
  }
}

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

  render(root);
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
  version: "0.1.0",
};

window.mountCafeApp = mount;
