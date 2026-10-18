import type { ReactNode } from "react";

/** Screen title block: a plain heading, a short description and optional actions. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="reveal mb-4 flex flex-wrap items-end justify-between gap-3 px-1">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-text">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Header for a panel inside a tabbed page: the tab already names it, so no big title. */
export function PanelIntro({ description, actions }: { title?: string; description?: ReactNode; actions?: ReactNode }) {
  if (!description && !actions) return null;
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3 px-1">
      {description && <p className="max-w-3xl text-sm text-muted">{description}</p>}
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
