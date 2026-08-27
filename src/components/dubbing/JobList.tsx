"use client";

import { useEffect, useState } from "react";
import { History, Loader2, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { dubbingApi, type JobStatus } from "@/lib/dubbing-api";
import { toast } from "sonner";

interface Props {
  onSelect: (jobId: string, status: JobStatus) => void;
  refreshKey: number;
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "هم‌اکنون";
  if (diff < 3600) return `${Math.floor(diff / 60)} دقیقه پیش`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ساعت پیش`;
  return `${Math.floor(diff / 86400)} روز پیش`;
}

const STATUS_VARIANT: Record<string, "secondary" | "default" | "destructive"> = {
  completed: "default",
  queued: "secondary",
  failed: "destructive",
  cancelled: "secondary",
};

const STATUS_LABELS: Record<string, string> = {
  queued: "در صف",
  downloading: "دریافت",
  extracting_audio: "استخراج صدا",
  transcribing: "تبدیل گفتار",
  translating: "ترجمه",
  generating_voice: "تولید صدا",
  synchronizing: "هماهنگ‌سازی",
  rendering: "رندر",
  completed: "تکمیل",
  cancelled: "لغو",
  failed: "خطا",
};

export function JobList({ onSelect, refreshKey }: Props) {
  const [jobs, setJobs] = useState<JobStatus[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    dubbingApi
      .listJobs(30)
      .then((list) => {
        if (!cancelled) setJobs(list);
      })
      .catch((e) => {
        toast.error(`بارگذاری فهرست کارها ناموفق: ${e.message}`);
        if (!cancelled) setJobs([]);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const loading = jobs === null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4 text-primary" />
          کارهای اخیر
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[280px] scroll-pretty">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              بارگذاری...
            </div>
          ) : jobs && jobs.length === 0 ? (
            <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
              هنوز کاری ایجاد نشده است
            </div>
          ) : (
            <div className="divide-y">
              {(jobs || []).map((job) => (
                <button
                  key={job.job_id}
                  onClick={() => onSelect(job.job_id, job)}
                  className="flex w-full items-center gap-3 p-3 text-start transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <p className="truncate text-sm font-medium" dir="auto">
                      {job.title || job.job_id.slice(0, 8)}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant={STATUS_VARIANT[job.status] || "secondary"} className="text-[10px]">
                        {STATUS_LABELS[job.status] || job.status}
                      </Badge>
                      {job.progress > 0 && job.status !== "completed" && (
                        <span className="font-mono">{job.progress}%</span>
                      )}
                    </div>
                  </div>
                  <ChevronLeft className="h-4 w-4 text-muted-foreground/50 shrink-0" />
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
