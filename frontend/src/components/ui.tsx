import { cloneElement, isValidElement } from "react";
import type { ReactNode, ReactElement } from "react";

export function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="page" aria-labelledby="page-title">
      <header className="page-heading"><p className="eyebrow">Your next great session</p>
      <h2 id="page-title" tabIndex={-1}>{title}</h2></header>
      {children}
    </section>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="feedback loading" role="status"><span className="status-dot" aria-hidden="true" />{label}</p>;
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <p className="feedback error-notice" role="alert">
      {message}{" "}
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </p>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty-state" role="status"><strong>{title}</strong>{children && <p>{children}</p>}</div>;
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}

export function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {isValidElement(children) ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        "aria-invalid": error ? true : undefined,
        "aria-describedby": [children.props && (children.props as Record<string, unknown>)["aria-describedby"], error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined,
      }) : children}
      {error && (
        <p className="field-error" role="alert" id={`${id}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}
