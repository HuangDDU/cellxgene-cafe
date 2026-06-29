import React from "react";

import DynamicPanel from "./DynamicPanel";
import StaticPanel from "./StaticPanel";

class Plot extends React.Component {
  render() {
    return (
      <div>
        <DynamicPanel />
        <StaticPanel />
      </div>
    );
  }
}

export default Plot;
