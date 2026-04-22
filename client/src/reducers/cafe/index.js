import trajectory from "./trajectory";
import trajectoryChoice from "./trajectoryChoice";

function cafeReducer(state = {}, action) {
  return {
    trajectory: trajectory(state.trajectory, action),
    trajectoryChoice: trajectoryChoice(state.trajectoryChoice, action),
  };
}

export default cafeReducer;
