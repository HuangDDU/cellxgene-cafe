import React from "react";

function DataModule({ context }) {
  return (
    <div className="cafe-placeholder">
      <h4>Data Module (TODO)</h4>
      <p className="cafe-note">该模块预留用于展示 FateAnnData 结构摘要和导出入口。</p>
      <p className="cafe-note">当前数据集: {context?.dataset?.name || "unknown"}</p>
    </div>
  );
}

export default DataModule;
