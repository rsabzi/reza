import { useCallback, useEffect, useState } from "react";
import {
  Database,
  Eye,
  Loader2,
  RefreshCw,
  Table2,
  Trash2,
  View,
} from "lucide-react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { ConfirmDialog } from "./ui/dialog";

function columnSummary(item) {
  if (Array.isArray(item.columns)) {
    return item.columns
      .map((column) =>
        typeof column === "string"
          ? column
          : `${column.name}:${column.type}${column.primary_key ? " (PK)" : ""}`,
      )
      .join("، ");
  }
  return "";
}

export function CustomSchemaPanel({ notify = () => {} }) {
  const [data, setData] = useState({ tables: [], views: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.listCustomSchema();
      setData({
        tables: result.tables || [],
        views: result.views || [],
      });
    } catch (reason) {
      setError(reason.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function loadPreview(kind, name) {
    setPreviewLoading(true);
    setError("");
    try {
      const result = await api.customSchemaRows(kind, name);
      setPreview({
        kind,
        name,
        rows: result.rows || [],
        count: result.count || 0,
      });
    } catch (reason) {
      setError(reason.message);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteCustomSchema(deleteTarget.kind, deleteTarget.name);
      setDeleteTarget(null);
      setPreview(null);
      await load();
      notify("شیء گزارش سفارشی حذف شد", "success");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setDeleting(false);
    }
  }

  const items = [
    ...data.tables.map((item) => ({ ...item, kind: "custom_table" })),
    ...data.views.map((item) => ({ ...item, kind: "custom_view" })),
  ];

  return (
    <Card data-testid="custom-schema-panel">
      <CardHeader>
        <div>
          <h2 className="font-semibold text-white">
            جدول‌ها و نماهای گزارش سفارشی
          </h2>
          <p className="mt-1 text-[11px] text-slate-600">
            ساخته‌شده با ابزار مدیریتی «همراه» (با تأیید) یا API مدیریتی. DDL
            فقط از Allowlist تولید می‌شود و هیچ SQL خامی پذیرفته نیست.
          </p>
        </div>
        <Database size={18} className="text-primary-soft" />
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[10px] text-slate-600">
            {items.length
              ? `${items.length} شیء ثبت‌شده`
              : "هنوز جدول یا نمای سفارشی‌ای نساخته‌اید"}
          </span>
          <Button variant="ghost" size="sm" onClick={load} loading={loading}>
            <RefreshCw size={13} /> تازه‌سازی
          </Button>
        </div>

        {error && (
          <p className="mb-3 rounded-lg border border-rose-400/15 bg-rose-400/[.05] p-2.5 text-[11px] text-rose-300">
            {error}
          </p>
        )}

        {items.length === 0 && !loading ? (
          <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-[11px] leading-6 text-slate-600">
            به همراه بگو: «یک جدول سفارشی با نام custom_leads و ستون‌های name و
            score بساز» یا «نمای گزارش report_active_salons را روی سالن‌ها آماده
            کن» — سپس در مرکز تأیید، همان را تأیید کن.
          </p>
        ) : (
          <div
            className="grid gap-2 sm:grid-cols-2"
            data-testid="custom-schema-list"
          >
            {items.map((item) => (
              <div
                key={`${item.kind}-${item.name}`}
                className="rounded-xl border border-line/70 bg-background/45 p-3"
              >
                <div className="flex items-center gap-2">
                  {item.kind === "custom_view" ? (
                    <View size={14} className="text-cyan-300" />
                  ) : (
                    <Table2 size={14} className="text-primary-soft" />
                  )}
                  <code
                    dir="ltr"
                    className="truncate text-[11px] text-slate-200"
                  >
                    {item.name}
                  </code>
                </div>
                <p className="mt-1.5 text-[10px] leading-5 text-slate-600">
                  {item.purpose || columnSummary(item)}
                </p>
                {item.purpose && (
                  <p className="text-[9px] text-slate-700">
                    {columnSummary(item)}
                  </p>
                )}
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadPreview(item.kind, item.name)}
                    loading={previewLoading && preview?.name === item.name}
                  >
                    <Eye size={12} /> پیش‌نمایش
                  </Button>
                  <button
                    type="button"
                    aria-label={`حذف ${item.name}`}
                    className="mr-auto text-slate-700 transition hover:text-rose-300"
                    onClick={() =>
                      setDeleteTarget({ kind: item.kind, name: item.name })
                    }
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {preview && (
          <div
            className="mt-4 overflow-hidden rounded-xl border border-line/70"
            data-testid="custom-schema-preview"
          >
            <div className="flex items-center justify-between border-b border-line/60 bg-elevated/40 px-3 py-2">
              <code dir="ltr" className="text-[10px] text-slate-400">
                {preview.name} — {preview.count} ردیف
              </code>
              <button
                type="button"
                className="text-[10px] text-slate-700 hover:text-slate-300"
                onClick={() => setPreview(null)}
              >
                بستن
              </button>
            </div>
            <div className="max-h-56 overflow-auto">
              {preview.rows.length === 0 ? (
                <p className="p-4 text-center text-[11px] text-slate-700">
                  ردیفی وجود ندارد.
                </p>
              ) : (
                <table className="w-full text-right text-[10px]">
                  <thead>
                    <tr className="border-b border-line/60 bg-black/20">
                      {Object.keys(preview.rows[0]).map((key) => (
                        <th
                          key={key}
                          className="px-3 py-2 font-medium text-slate-400"
                        >
                          {key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, index) => (
                      <tr
                        key={index}
                        className="border-b border-line/40 last:border-0"
                      >
                        {Object.values(row).map((value, cellIndex) => (
                          <td
                            key={cellIndex}
                            className="px-3 py-2 text-slate-300"
                          >
                            {value === null || value === undefined
                              ? "—"
                              : String(value)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {previewLoading && !preview && (
          <p className="mt-3 flex items-center gap-2 text-[11px] text-slate-600">
            <Loader2 size={13} className="animate-spin" /> در حال خواندن
            ردیف‌ها…
          </p>
        )}
      </CardContent>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        loading={deleting}
        title="حذف شیء گزارش سفارشی؟"
        description={`${deleteTarget?.kind === "custom_view" ? "نمای" : "جدول"} «${deleteTarget?.name || ""}» و تعریف آن حذف می‌شود. این عمل قابل بازگشت نیست.`}
        confirmLabel="حذف"
      />
    </Card>
  );
}
