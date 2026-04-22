import React from "react";

class TabNav extends React.Component {
  render() {
    const { items, activeKey, onChange } = this.props;
    return (
      <div className="cafe-tab-nav">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`cafe-tab-btn ${activeKey === item.key ? "is-active" : ""}`}
            onClick={() => onChange(item.key)}
          >
            {item.label}
            {!item.enabled ? " (TODO)" : ""}
          </button>
        ))}
      </div>
    );
  }
}

export default TabNav;
