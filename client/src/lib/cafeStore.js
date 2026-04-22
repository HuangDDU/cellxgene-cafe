import {
  CAFE_LAYOUT_CHOICE_SET,
  CAFE_TRAJECTORY_ANCHOR_SET,
  CAFE_TRAJECTORY_CHOICE_BOOTSTRAP,
  CAFE_TRAJECTORY_CHOICE_SET,
  CAFE_TRAJECTORY_EDGE_WIDTH_SET,
  CAFE_TRAJECTORY_NODE_SIZE_SET,
  CAFE_TRAJECTORY_TYPE_SET,
  CAFE_TRAJECTORY_UPDATE,
  CAFE_TRAJECTORY_VISIBILITY_SET,
} from "../reducers/cafe/actions";
import { createDefaultCafeBridgeState } from "../reducers/cafe/selectors";

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
    layoutChoice: state.layoutChoice,
    trajectoryChoice: state.trajectoryChoice,
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
    "trajectoryChoice",
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

function reduceLayoutChoice(state, action) {
  switch (action.type) {
    case CAFE_LAYOUT_CHOICE_SET:
      return {
        ...state,
        layoutChoice: {
          ...state.layoutChoice,
          current: action.layoutChoice ?? state.layoutChoice.current,
          currentDimNames: action.currentDimNames ?? state.layoutChoice.currentDimNames,
        },
      };
    default:
      return state;
  }
}

function reduceTrajectoryChoice(state, action) {
  switch (action.type) {
    case CAFE_TRAJECTORY_CHOICE_BOOTSTRAP:
      return {
        ...state,
        trajectoryChoice: {
          ...state.trajectoryChoice,
          ...(action.payload || {}),
        },
      };
    case CAFE_TRAJECTORY_CHOICE_SET:
      return {
        ...state,
        trajectoryChoice: {
          ...state.trajectoryChoice,
          current: action.trajectoryChoice ?? state.trajectoryChoice.current,
          available: Array.isArray(action.available)
            ? action.available
            : state.trajectoryChoice.available,
        },
      };
    default:
      return state;
  }
}

function reduceTrajectory(state, action) {
  const currentTrajectory = state.trajectory || createDefaultCafeBridgeState().trajectory;

  switch (action.type) {
    case CAFE_TRAJECTORY_UPDATE: {
      const patch = action.patch || {};
      const nextTrajectory = { ...currentTrajectory };

      if (patch.trajectory && typeof patch.trajectory === "object") {
        Object.assign(nextTrajectory, patch.trajectory);
      }

      [
        "showTrajectory",
        "anchorTrajectory",
        "trajectoryType",
        "nodeSize",
        "edgeWidth",
      ].forEach((key) => {
        if (Object.prototype.hasOwnProperty.call(patch, key)) {
          nextTrajectory[key] = patch[key];
        }
      });

      return {
        ...state,
        trajectory: nextTrajectory,
      };
    }
    case CAFE_TRAJECTORY_VISIBILITY_SET:
      return {
        ...state,
        trajectory: {
          ...currentTrajectory,
          showTrajectory: action.showTrajectory ?? currentTrajectory.showTrajectory,
        },
      };
    case CAFE_TRAJECTORY_ANCHOR_SET:
      return {
        ...state,
        trajectory: {
          ...currentTrajectory,
          anchorTrajectory: action.anchorTrajectory ?? currentTrajectory.anchorTrajectory,
        },
      };
    case CAFE_TRAJECTORY_TYPE_SET:
      return {
        ...state,
        trajectory: {
          ...currentTrajectory,
          trajectoryType: action.trajectoryType ?? currentTrajectory.trajectoryType,
        },
      };
    case CAFE_TRAJECTORY_NODE_SIZE_SET:
      return {
        ...state,
        trajectory: {
          ...currentTrajectory,
          nodeSize: action.nodeSize ?? currentTrajectory.nodeSize,
        },
      };
    case CAFE_TRAJECTORY_EDGE_WIDTH_SET:
      return {
        ...state,
        trajectory: {
          ...currentTrajectory,
          edgeWidth: action.edgeWidth ?? currentTrajectory.edgeWidth,
        },
      };
    default:
      return state;
  }
}

function reducer(state, action) {
  let nextState = reduceLayoutChoice(state, action);
  nextState = reduceTrajectoryChoice(nextState, action);
  nextState = reduceTrajectory(nextState, action);
  return nextState;
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

    state = reducer(state, action);
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
