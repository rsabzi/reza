import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";

/**
 * Inline draft-text dialog: shows a generated outreach/proposal text right
 * where the user asked for it, with one-click copy. Drafting has no side
 * effects, so no task/approval round-trip is needed.
 */
export function DraftPreviewDialog({
  open,
  title,
  text,
  loading = false,
  error = "",
  onClose,
  onCopy,
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard?.writeText(text);
    setCopied(true);
    onCopy?.();
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title || "متن آماده‌شده"}
      size="md"
    >
      <div className="space-y-4 px-5 py-5 sm:px-6" data-testid="draft-preview">
        {loading ? (
          <p className="py-8 text-center text-xs text-slate-500">
            در حال آماده‌سازی متن…
          </p>
        ) : error ? (
          <p className="text-xs leading-6 text-rose-300" role="alert">
            {error}
          </p>
        ) : (
          <>
            <p
              className="whitespace-pre-line rounded-xl border border-line bg-background/60 p-4 text-[13px] leading-8 text-slate-200"
              data-testid="draft-preview-text"
            >
              {text}
            </p>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[10px] text-slate-600">
                این متن پیش‌نویس است؛ با دکمه کپی بردار و personalize‌اش کن.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={copy}
                disabled={!text}
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "کپی شد" : "کپی متن"}
              </Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}
