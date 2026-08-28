export function PanelTitle({ eyebrow, title, description, action, meta }) {
  return (
    <header className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="min-w-0">
        <div className="mb-2 flex items-center gap-2">
          <span className="h-px w-5 bg-primary" />
          <p className="text-[10px] font-bold tracking-[.17em] text-primary-soft">
            {eyebrow}
          </p>
          {meta}
        </div>
        <h1 className="text-balance text-[26px] font-bold tracking-[-.02em] text-white sm:text-[32px]">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
            {description}
          </p>
        )}
      </div>
      {action && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {action}
        </div>
      )}
    </header>
  );
}
