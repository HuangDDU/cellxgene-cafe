import React from "react";

import DynamicPanel from "./DynamicPanel";
import StaticPanel from "./StaticPanel";

export default class Plot extends React.Component {
  render() {
    return (
      <div>
        <DynamicPanel />
        <StaticPanel />
      </div>
    );
  }
}
