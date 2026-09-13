const STATUS_COLORS: Record<string, string> = {
  // load statuses
  draft: "gray", quoted: "blue", tendered: "blue", available: "cyan",
  assigned: "indigo", confirmed: "indigo", dispatched: "violet",
  at_pickup: "amber", picked_up: "amber", in_transit: "sky",
  at_delivery: "amber", delivered: "green", pod_received: "green",
  invoiced: "teal", paid: "green", cancelled: "red",
  // severity
  critical: "red", high: "orange", medium: "amber", low: "gray",
  // exception / approval states
  open: "red", acknowledged: "amber", resolved: "green",
  pending: "amber", approved: "green", rejected: "red", expired: "gray",
  // invoices
  issued: "blue", overdue: "red", void: "gray",
  // misc
  active: "green", paused: "amber", disabled: "gray",
  compliant: "green", warning: "amber",
  maintenance: "amber", out_of_service: "red",
  en_route: "sky", off_duty: "gray", unavailable: "gray", loading: "amber",
  connected: "green", mock: "amber",
};

export function statusColor(status: string | undefined): string {
  if (!status) return "gray";
  const key = status.toLowerCase().replace(/[\s-]/g, "_");
  return STATUS_COLORS[key] || "gray";
}

export default function StatusPill({ status, className = "" }: { status: string | undefined; className?: string }) {
  const label = (status || "—").replace(/_/g, " ");
  return (
    <span className={`pill pill-${statusColor(status)} ${className}`}>
      {label}
    </span>
  );
}
