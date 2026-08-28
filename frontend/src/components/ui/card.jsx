import { cn } from "../../lib/utils";

export function Card({ className, children, interactive = false, ...props }) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-line/80 bg-surface/90 shadow-card",
        interactive &&
          "transition duration-200 hover:-translate-y-0.5 hover:border-slate-600/80 hover:shadow-glow",
        className,
      )}
      {...props}
    >
      {children}
    </section>
  );
}

export function CardHeader({ className, children }) {
  return (
    <div
      className={cn(
        "flex min-h-16 items-center justify-between gap-4 border-b border-line/65 px-5 py-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardContent({ className, children }) {
  return <div className={cn("p-5", className)}>{children}</div>;
}
