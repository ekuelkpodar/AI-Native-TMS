import { useState } from "react";
import type { AIRecommendation } from "../api/client";

export default function AIRecommendationCard({
  rec,
  onApprove,
  onReject,
  busy,
}: {
  rec: AIRecommendation;
  onApprove?: () => void;
  onReject?: () => void;
  busy?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="ai-rec-card">
      <div className="ai-rec-head">
        <span className="ai-badge">AI</span>
        <span className="ai-conf">{Math.round(rec.confidence * 100)}% confidence</span>
        {rec.approval_required && <span className="pill pill-amber">approval required</span>}
      </div>
      <div className="ai-rec-title">{rec.recommendation}</div>
      <div className="ai-rec-reason">{rec.reason}</div>
      <div className="ai-rec-impact">Impact: {rec.expected_impact}</div>
      <button className="btn btn-ghost btn-sm" onClick={() => setExpanded((e) => !e)}>
        {expanded ? "Hide details ▲" : "Alternatives & risks ▼"}
      </button>
      {expanded && (
        <div className="ai-rec-details">
          <div><b>Alternatives:</b> {rec.alternatives.length ? rec.alternatives.join("; ") : "None listed"}</div>
          <div><b>Risks:</b> {rec.risks.length ? rec.risks.join("; ") : "None listed"}</div>
        </div>
      )}
      {(onApprove || onReject) && (
        <div className="ai-rec-actions">
          {onApprove && (
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={onApprove}>
              Approve
            </button>
          )}
          {onReject && (
            <button className="btn btn-ghost btn-sm" disabled={busy} onClick={onReject}>
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}
