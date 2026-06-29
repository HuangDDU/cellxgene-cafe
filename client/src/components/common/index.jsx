import React from "react";

export function CardSection({ title, defaultOpen = true, badge, children, className = "" }) {
  const [open, setOpen] = React.useState(defaultOpen);

  return (
    <div className={`cafe-card ${className}`.trim()}>
      <div className="cafe-card-header" onClick={() => setOpen(!open)}>
        <span className="cafe-card-chevron">{open ? "▾" : "▸"}</span>
        <h4>{title}</h4>
        {badge ? <span className="cafe-card-badge">{badge}</span> : null}
      </div>
      {open ? <div className="cafe-card-body">{children}</div> : null}
    </div>
  );
}

export function InfoGrid({ items = [], className = "" }) {
  return (
    <div className={`cafe-info-grid ${className}`.trim()}>
      {items.map(({ label, value }) => (
        <div key={label} className="cafe-info-item">
          <div className="cafe-info-label">{label}</div>
          <div className="cafe-info-value">{value ?? "n/a"}</div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ children }) {
  return <div className="cafe-note cafe-empty-state">{children}</div>;
}

export function StatusBadge({ status }) {
  return <span className={`cafe-status-badge is-${status || "unknown"}`}>{status || "unknown"}</span>;
}
