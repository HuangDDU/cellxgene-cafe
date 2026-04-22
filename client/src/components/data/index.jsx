import React from "react";

class Data extends React.Component {
  render() {
    const { context } = this.props;
    return (
      <div className="cafe-placeholder">
        <h4>Data (TODO)</h4>
        <p className="cafe-note">该模块预留用于展示 FateAnnData 结构摘要和导出入口。</p>
        <p className="cafe-note">当前数据集: {context?.dataset?.name || "unknown"}</p>
      </div>
    );
  }
}

export default Data;