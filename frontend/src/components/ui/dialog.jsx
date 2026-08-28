import { useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "./button";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
  size = "md",
}) {
  useEffect(() => {
    if (!open) return undefined;
    function closeOnEscape(event) {
      if (event.key === "Escape") onClose();
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open, onClose]);

  if (!open) return null;
  const widths = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-3xl",
    xl: "max-w-5xl",
  };
  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-center overflow-y-auto bg-[#02040a]/80 p-4 backdrop-blur-sm"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "my-auto w-full animate-slide-up overflow-hidden rounded-[22px] border border-line bg-surface shadow-popover",
          widths[size],
          className,
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-line/70 px-5 py-4 sm:px-6">
          <div>
            <h2 className="font-semibold text-white">{title}</h2>
            {description && (
              <p className="mt-1.5 text-xs leading-6 text-slate-500">
                {description}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="-ml-2 -mt-1 size-9"
            onClick={onClose}
            aria-label="بستن"
          >
            <X size={18} />
          </Button>
        </header>
        <div className="max-h-[78vh] overflow-y-auto p-5 sm:p-6">
          {children}
        </div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = "آیا مطمئن هستید؟",
  description,
  loading = false,
  confirmLabel = "حذف",
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title} size="sm">
      <div className="flex gap-3 rounded-xl border border-rose-400/15 bg-rose-400/[.06] p-4">
        <AlertTriangle className="mt-0.5 shrink-0 text-rose-300" size={19} />
        <p className="text-sm leading-7 text-slate-300">{description}</p>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          انصراف
        </Button>
        <Button variant="danger" loading={loading} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
