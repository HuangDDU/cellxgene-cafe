import React from "react";
import { connect } from "react-redux";

import { CardSection } from "../common";

const API_BASE = typeof window !== "undefined" && window.location.port === "3000"
  ? `http://${window.location.hostname || "localhost"}:5005/api/cafe`
  : "/api/cafe";

const ANALYSIS_TEMPLATES = [
  { id: "trajectory_overview", label: "Trajectory Overview", prompt: "Provide a comprehensive overview of the current cell fate trajectories. Describe the lineage branching structure, key milestones, and pseudotime ordering." },
  { id: "driver_genes", label: "Driver Gene Analysis", prompt: "Analyze the driver genes identified for each trajectory. Which genes show the strongest association with specific cell fate decisions?" },
  { id: "method_comparison", label: "Method Comparison", prompt: "Compare the different trajectory inference methods available. What are the strengths and weaknesses of each approach?" },
  { id: "benchmark_interpret", label: "Benchmark Interpretation", prompt: "Interpret the benchmark metrics. What do pseudotime correlation, edge flip, and F1 scores tell us about trajectory quality?" },
  { id: "next_steps", label: "Suggested Next Steps", prompt: "Based on the current analysis, suggest next steps for deeper investigation." },
];

class Agent extends React.Component {
  constructor(props) { super(props); this.state = { messages: [], input: "", sending: false, error: "" }; this._msgEnd = React.createRef(); }

  _scrollToBottom() { if (this._msgEnd.current) this._msgEnd.current.scrollIntoView({ behavior: "smooth" }); }

  _sendMessage = async (text) => {
    const content = String(text || this.state.input).trim();
    if (!content || this.state.sending) return;
    const messages = [...this.state.messages, { role: "user", content }];
    this.setState({ messages, input: "", sending: true, error: "" });
    this._scrollToBottom();
    try {
      const resp = await fetch(`${API_BASE}/agent/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: content, context: this.props.context }) });
      const data = await resp.json();
      if (resp.ok) { this.setState((prev) => ({ messages: [...prev.messages, { role: "assistant", content: data.response || "No response." }], sending: false })); }
      else { this.setState((prev) => ({ messages: [...prev.messages, { role: "assistant", content: `Error: ${data.message}` }], sending: false })); }
    } catch (err) { this.setState((prev) => ({ messages: [...prev.messages, { role: "assistant", content: `Request failed: ${err.message}` }], sending: false })); }
    setTimeout(() => this._scrollToBottom(), 100);
  };

  _handleKeyDown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this._sendMessage(); } };

  render() {
    const { messages, input, sending } = this.state;
    return (
      <div className="cafe-agent">
        <CardSection title="Conversation" defaultOpen badge={`${messages.length} messages`} className="cafe-agent-chat">
          <div className="cafe-agent-templates">{ANALYSIS_TEMPLATES.map((tpl) => (<button key={tpl.id} type="button" className="cafe-chip-btn" onClick={() => this._sendMessage(tpl.prompt)}>{tpl.label}</button>))}</div>
          <div className="cafe-agent-messages">
            {!messages.length && <div className="cafe-note" style={{ textAlign: "center", padding: "20px 0" }}>Select an analysis template or type a question about cell fate trajectories.</div>}
            {messages.map((msg, i) => (<div key={i} className={`cafe-agent-msg cafe-agent-msg-${msg.role}`}><div className="cafe-agent-msg-role">{msg.role === "user" ? "You" : "Cafe Agent"}</div><div className="cafe-agent-msg-content">{msg.content}</div></div>))}
            {sending && <div className="cafe-agent-msg cafe-agent-msg-assistant"><div className="cafe-agent-msg-role">Cafe Agent</div><div className="cafe-agent-msg-content"><span className="cafe-agent-typing">Analyzing...</span></div></div>}
            <div ref={this._msgEnd} />
          </div>
          <div className="cafe-agent-input-row">
            <input type="text" className="cafe-agent-input" value={input} onChange={(e) => this.setState({ input: e.target.value })} onKeyDown={this._handleKeyDown} placeholder="Ask about cell fate analysis..." disabled={sending} />
            <button type="button" className="cafe-btn cafe-btn-primary" onClick={() => this._sendMessage()} disabled={sending || !input.trim()}>Send</button>
          </div>
        </CardSection>
      </div>
    );
  }
}

const mapState = (state) => ({
  context: { manifest: state.context?.manifest },
});

export default connect(mapState)(Agent);
