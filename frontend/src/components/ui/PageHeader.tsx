import type { ReactNode } from "react";

/** Screen title block: display-font heading, kanji subtitle and optional actions. */
export function PageHeader({
  title,
  kanji,
  description,
  actions,
}: {
  title: string;
  kanji?: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-3 px-1">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-bold tracking-wide text-text md:text-3xl">
          {title}
          {kanji && <span className="ml-3 align-middle text-base font-medium text-gold/80">{kanji}</span>}
        </h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
