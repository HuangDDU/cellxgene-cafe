import trajectory from "./trajectory";
import cellxgene from "./cellxgene";

export default function cafeReducer(state = {}, action) {
  return {
    cellxgene: cellxgene(state.cellxgene, action),
    trajectory: trajectory(state.trajectory, action),
  };
}
