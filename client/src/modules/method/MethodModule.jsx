import React from "react";

function MethodModule({ context }) {
  return (
    <div className="cafe-placeholder">
      <h4>Method Module (TODO)</h4>
      <p className="cafe-note">该模块预留用于方法参数表单、任务提交和任务状态查询。</p>
      <p className="cafe-note">
        已预留后端接口: <code>/api/cafe/job/submit</code> 和 <code>/api/cafe/job/&lt;job_id&gt;</code>
      </p>
      <p className="cafe-note">可用轨迹方法: {(context?.trajectories || []).join(", ") || "none"}</p>
    </div>
  );
}

export default MethodModule;
