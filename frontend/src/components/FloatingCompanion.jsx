import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  ChevronDown,
  Maximize2,
  Minimize2,
  Sparkles,
} from "lucide-react";
import { CompanionPanel } from "./CompanionPanel";
import { cn } from "../lib/utils";

const STORAGE_KEY = "hamrah-companion-open";

/**
 * همـراه — the always-available floating assistant.
 * Lives at the edge of the desktop next to every panel; collapses to a
 * launcher orb and opens as a full-height sheet on small screens.
 */
export function FloatingCompanion({
  open = true,
  onOpenChange = () => {},
  system = {},
  approvals = 0,
  onNavigate = () => {},
  notify = () => {},
  onChanged = () => {},
}) {
  const [expanded, setExpanded] = useState(false);
  const panelRef = useRef(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
  }, [open]);

  const collapse = useCallback(() => {
    setExpanded(false);
    onOpenChange(false);
  }, [onOpenChange]);

  useEffect(() => {
    if (!open || !expanded) return undefined;
    function onKey(event) {
      if (event.key === "Escape") {
        setExpanded(false);
        onOpenChange(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, expanded, onOpenChange]);

  // Close the panel when clicking outside of it while docked.
  useEffect(() => {
    if (!open || expanded) return undefined;
    function onPointer(event) {
      if (
        panelRef.current &&
        !panelRef.current.contains(event.target) &&
        event.target instanceof Node
      ) {
        onOpenChange(false);
      }
    }
    window.addEventListener("pointerdown", onPointer);
    return () => window.removeEventListener("pointerdown", onPointer);
  }, [open, expanded, onOpenChange]);

  const online = Boolean(system.gemini_configured);

  return (
    <>
      {/* ------- docked floating panel ------- */}
      <div
        ref={panelRef}
        data-testid="floating-companion"
        className={cn(
          "fixed z-50 transition-all duration-300",
          expanded
            ? "inset-x-3 top-16 bottom-3 mx-auto max-w-4xl sm:inset-x-6"
            : "bottom-4 left-4 h-[min(660px,calc(100dvh-2rem))] w-[min(430px,calc(100vw-2rem))]",
        )}
      >
        <div
          className={cn(
            "flex h-full flex-col overflow-hidden rounded-3xl border shadow-orb transition-transform duration-300",
            "border-primary/20 glass-strong",
            open
              ? "translate-y-0 scale-100 opacity-100"
              : "pointer-events-none translate-y-6 scale-[.97] opacity-0",
          )}
        >
          {/* aurora accent */}
          <div className="pointer-events-none absolute -top-24 right-0 h-48 w-72 rounded-full bg-primary/25 blur-[90px]" />
          <div className="pointer-events-none absolute -bottom-24 left-0 h-44 w-56 rounded-full bg-mint/[.12] blur-[80px]" />

          {/* shell header */}
          <header className="relative z-10 flex h-14 shrink-0 items-center gap-2.5 border-b border-white/[.06] px-3.5">
            <span
              className={cn(
                "hamrah-orb grid size-9 shrink-0 place-items-center text-white",
                online ? "hamrah-orb--idle" : "opacity-70 saturate-50",
              )}
            >
              <Bot size={17} strokeWidth={2} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1.5 text-[12.5px] font-bold text-white">
                همـراه
                <span className="rounded-full bg-primary/15 px-1.5 py-px text-[8px] font-medium text-primary-soft">
                  AI
                </span>
              </p>
              <p className="mt-px flex items-center gap-1.5 text-[9px] text-slate-500">
                <span
                  className={cn(
                    "size-1.5 rounded-full",
                    online ? "bg-emerald-400" : "bg-amber-400",
                  )}
                />
                {online
                  ? system.reasoning_model || "آنلاین و آماده"
                  : "بدون کلید Gemini — آفلاین"}
              </p>
            </div>
            <button
              type="button"
              aria-label={expanded ? "کوچک کردن همراه" : "بزرگ کردن همراه"}
              onClick={() => setExpanded((value) => !value)}
              className="grid size-8 place-items-center rounded-xl text-slate-500 transition hover:bg-white/[.06] hover:text-slate-200"
            >
              {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </button>
            <button
              type="button"
              aria-label="جمع کردن همراه"
              onClick={collapse}
              className="grid size-8 place-items-center rounded-xl text-slate-500 transition hover:bg-white/[.06] hover:text-slate-200"
            >
              <ChevronDown size={16} />
            </button>
          </header>

          {/* chat body */}
          <div className="relative z-10 min-h-0 flex-1">
            <CompanionPanel
              variant="dock"
              system={system}
              approvals={approvals}
              onNavigate={onNavigate}
              notify={notify}
              onChanged={onChanged}
            />
          </div>
        </div>
      </div>

      {/* ------- launcher orb (collapsed) ------- */}
      <div
        className={cn(
          "fixed bottom-4 left-4 z-50 transition-all duration-300",
          open ? "pointer-events-none translate-y-4 scale-75 opacity-0" : "",
        )}
      >
        <button
          type="button"
          data-testid="companion-launcher"
          aria-label="باز کردن همراه"
          onClick={() => onOpenChange(true)}
          className="group relative grid size-14 place-items-center rounded-full text-white transition hover:scale-105 active:scale-95"
        >
          <span className="launcher-ring" />
          <span className="hamrah-orb hamrah-orb--idle grid size-14 place-items-center">
            <Bot size={24} strokeWidth={1.9} />
          </span>
          {approvals > 0 && (
            <span className="absolute -top-0.5 left-0 grid min-w-5 place-items-center rounded-full border-2 border-background bg-rose-500 px-1 py-0.5 text-[9px] font-bold">
              {approvals.toLocaleString("fa-IR")}
            </span>
          )}
          <span className="pointer-events-none absolute right-full top-1/2 mr-3 -translate-y-1/2 whitespace-nowrap rounded-xl border border-line bg-surface/95 px-3 py-1.5 text-[10px] text-slate-300 opacity-0 shadow-popover backdrop-blur-xl transition group-hover:opacity-100">
            <Sparkles size={10} className="ml-1 inline text-primary-soft" />
            همـراه اینجاست — چیزی که می‌خواهی را بگو
          </span>
        </button>
      </div>
    </>
  );
}
