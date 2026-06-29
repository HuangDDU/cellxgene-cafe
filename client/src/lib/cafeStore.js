import cellxgeneReducer from "../reducers/cellxgene";
import contextReducer from "../reducers/context";
import trajectoryReducer from "../reducers/trajectory";
import { createDefaultCafeBridgeState } from "../reducers/selectors";

function getReduxDevToolsExtension() {
  if (typeof window === "undefined") {
    return null;
  }

  const candidates = [window];

  try {
    if (window.top && window.top !== window) {
      candidates.push(window.top);
    }
  } catch (error) {
    // Ignore cross-origin access failures.
  }

  try {
    if (window.parent && window.parent !== window) {
      candidates.push(window.parent);
    }
  } catch (error) {
    // Ignore cross-origin access failures.
  }

  for (const target of candidates) {
    const extension = target && target.__REDUX_DEVTOOLS_EXTENSION__;
    if (extension && typeof extension.connect === "function") {
      return extension;
    }
  }

  return null;
}

function buildSnapshot(state) {
  return {
    cellxgene: state.cellxgene,
    context: state.context,
    trajectory: state.trajectory,
  };
}

function sanitizeAction(action) {
  if (!action || typeof action !== "object") {
    return { type: "<non-object-action>" };
  }

  const sanitized = { type: action.type || "<anonymous-action>" };
  [
    "layoutChoice",
    "trajectoryName",
    "showTrajectory",
    "anchorTrajectory",
    "trajectoryType",
    "nodeSize",
    "edgeWidth",
  ].forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(action, key)) {
      sanitized[key] = action[key];
    }
  });

  if (action.patch && typeof action.patch === "object") {
    sanitized.patch = action.patch;
  }

  if (action.payload && typeof action.payload === "object") {
    sanitized.payload = action.payload;
  }

  return sanitized;
}

function rootReducer(state, action) {
  return {
    ...state,
    cellxgene: cellxgeneReducer(state.cellxgene, action),
    context: contextReducer(state.context, action),
    trajectory: trajectoryReducer(state.trajectory, action),
  };
}

function createStore() {
  let state = createDefaultCafeBridgeState();
  const listeners = new Set();
  let devtools = null;

  const notify = (action) => {
    const snapshot = buildSnapshot(state);

    if (devtools) {
      try {
        devtools.send(sanitizeAction(action), snapshot);
      } catch (error) {
        devtools = null;
        window.__CAFE_REDUX_DEVTOOLS_ACTIVE__ = false;
      }
    }

    listeners.forEach((listener) => {
      try {
        listener();
      } catch (error) {
        console.error("Cafe store listener failed", error);
      }
    });
  };

  const tryConnectDevTools = () => {
    if (typeof window === "undefined" || devtools) {
      return;
    }

    const extension = getReduxDevToolsExtension();
    if (!extension) {
      return;
    }

    try {
      devtools = extension.connect({
        name: "cellxgene-cafe",
        serialize: true,
        trace: false,
      });
      devtools.init(buildSnapshot(state));
      window.__CAFE_REDUX_DEVTOOLS_ACTIVE__ = true;
    } catch (error) {
      devtools = null;
      window.__CAFE_REDUX_DEVTOOLS_ACTIVE__ = false;
    }
  };

  const dispatch = (action) => {
    if (!action || typeof action !== "object") {
      return action;
    }

    state = rootReducer(state, action);
    tryConnectDevTools();
    notify(action);
    return action;
  };

  const subscribe = (listener) => {
    if (typeof listener !== "function") {
      return () => {};
    }

    listeners.add(listener);
    listener();
    return () => listeners.delete(listener);
  };

  const store = {
    getState() {
      return state;
    },
    dispatch,
    subscribe,
  };

  if (typeof window !== "undefined") {
    window.__CAFE_REDUX_STORE__ = store;
    window.__REDUX_STORE__ = store;
    if (process.env.NODE_ENV !== "production") {
      window.store = store;
    }

    dispatch({ type: "@@cafe/devtools_probe" });
  }

  return store;
}

const cafeStore = createStore();

export default cafeStore;
