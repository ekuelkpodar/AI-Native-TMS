import React, { useMemo, useState } from "react";
import EmptyState from "./EmptyState";

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  width?: string;
  render?: (row: T) => React.ReactNode;
  getValue?: (row: T) => string | number | undefined | null;
}

export default function DataTable<T extends { id: string }>({
  columns,
  rows,
  loading,
  error,
  onRetry,
  emptyTitle = "No results",
  emptyHint,
  searchKeys,
  initialSearch = "",
  pageSize = 15,
  onRowClick,
  actions,
}: {
  columns: Column<T>[];
  rows: T[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyHint?: string;
  searchKeys?: (keyof T)[];
  initialSearch?: string;
  pageSize?: number;
  onRowClick?: (row: T) => void;
  actions?: (row: T) => React.ReactNode;
}) {
  const [search, setSearch] = useState(initialSearch);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    let out = rows;
    const q = search.trim().toLowerCase();
    if (q && searchKeys) {
      out = out.filter((r) =>
        searchKeys.some((k) => String(r[k] ?? "").toLowerCase().includes(q))
      );
    }
    if (sortKey) {
      const col = columns.find((c) => c.key === sortKey);
      if (col) {
        out = [...out].sort((a, b) => {
          const av = col.getValue ? col.getValue(a) : (a as Record<string, unknown>)[sortKey];
          const bv = col.getValue ? col.getValue(b) : (b as Record<string, unknown>)[sortKey];
          if (av == null && bv == null) return 0;
          if (av == null) return 1;
          if (bv == null) return -1;
          if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
          return String(av).localeCompare(String(bv)) * sortDir;
        });
      }
    }
    return out;
  }, [rows, search, searchKeys, sortKey, sortDir, columns]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const cur = Math.min(page, pages);
  const slice = filtered.slice((cur - 1) * pageSize, cur * pageSize);

  if (loading) {
    return (
      <div className="table-wrap">
        <div className="table-skeleton">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton-row" />
          ))}
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="table-wrap">
        <EmptyState title="Couldn't load data" hint={error} action={onRetry && (
          <button className="btn btn-primary" onClick={onRetry}>Retry</button>
        )} />
      </div>
    );
  }

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(key);
      setSortDir(1);
    }
    setPage(1);
  };

  return (
    <div className="table-wrap">
      {searchKeys && (
        <div className="table-toolbar">
          <input
            className="input search-input"
            placeholder="Search…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
          <span className="table-count">{filtered.length} result{filtered.length === 1 ? "" : "s"}</span>
        </div>
      )}
      {slice.length === 0 ? (
        <EmptyState title={emptyTitle} hint={emptyHint} />
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th
                    key={c.key}
                    style={c.width ? { width: c.width } : undefined}
                    className={c.sortable ? "sortable" : ""}
                    onClick={c.sortable ? () => toggleSort(c.key) : undefined}
                  >
                    {c.header}
                    {c.sortable && sortKey === c.key && (
                      <span className="sort-arrow">{sortDir === 1 ? " ↑" : " ↓"}</span>
                    )}
                  </th>
                ))}
                {actions && <th style={{ width: 90 }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {slice.map((row) => (
                <tr key={row.id} className={onRowClick ? "row-click" : ""} onClick={onRowClick ? () => onRowClick(row) : undefined}>
                  {columns.map((c) => (
                    <td key={c.key}>
                      {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "—")}
                    </td>
                  ))}
                  {actions && <td onClick={(e) => e.stopPropagation()}>{actions(row)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          {pages > 1 && (
            <div className="pagination">
              <button className="btn btn-ghost btn-sm" disabled={cur <= 1} onClick={() => setPage(cur - 1)}>
                ← Prev
              </button>
              <span>Page {cur} of {pages}</span>
              <button className="btn btn-ghost btn-sm" disabled={cur >= pages} onClick={() => setPage(cur + 1)}>
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
