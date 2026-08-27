"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Download,
  XCircle,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Video,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProgressSteps } from "./ProgressSteps";
import { TranscriptView } from "./TranscriptView";
import { dubbingApi, type JobStatus } from "@/lib/dubbing-api";
import { toast } from "sonner";

interface Props {
  jobId: string;
  initialStatus?: JobStatus;
  onClose: () => void;
}

const PIPELINE_STAGES = [
  { key: "downloading", label: "دریافت ویدیو" },
  { key: "extracting_audio", label: "استخراج صدا" },
  { key: "transcribing", label: "تبدیل گفتار به متن" },
  { key: "translating", label: "ترجمه با Gemini" },
  { key: "generating_voice", label: "تولید صدای دوبله" },
  { key: "synchronizing", label: "هماهنگ‌سازی زمان‌بندی" },
  { key: "rendering", label: "رندر نهایی ویدیو" },
  { key: "completed", label: "تکمیل شد" },
];

const STATUS_LABELS: Record<string, string> = {
  queued: "در صف",
  downloading: "دریافت ویدیو",
  extracting_audio: "استخراج صدا",
  transcribing: "تبدیل گفتار به متن",
  translating: "ترجمه با Gemini",
  generating_voice: "تولید صدای دوبله",
  synchronizing: "هماهنگ‌سازی",
  rendering: "رندر نهایی",
  completed: "تکمیل شد",
  cancelled: "لغو شد",
  failed: "خطا",
};

export function JobDetail({ jobId, initialStatus, onClose }: Props) {
  const [status, setStatus] = useState<JobStatus | null>(initialStatus || null);
  const [tab, setTab] = useState("progress");
  const closeRef = useRef<(() => void) | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!jobId) return;
    // Initial fetch in case we don't have status.
    if (!status) {
      dubbingApi.getJob(jobId).then(setStatus).catch(() => {});
    }
    const unsub = dubbingApi.subscribe(
      jobId,
      (data) => {
        setStatus((prev) => ({
          job_id: jobId,
          status: data.status,
          progress: data.progress,
          stage: data.stage ?? null,
          error: data.error ?? null,
          target_lang: prev?.target_lang ?? "fa",
          output_format: prev?.output_format ?? "mp4",
          title: prev?.title ?? null,
        }));
        if (data.status === "completed") {
          toast.success("دوبله با موفقیت تکمیل شد!");
        } else if (data.status === "failed") {
          toast.error("پردازش دوبله با خطا متوقف شد");
        }
      },
      () => {}
    );
    closeRef.current = unsub;
    return () => {
      if (closeRef.current) closeRef.current();
    };
  }, [jobId]);

  async function cancel() {
    try {
      await dubbingApi.cancelJob(jobId);
      toast.success("درخواست لغو ارسال شد");
    } catch (e) {
      toast.error(`لغو ناموفق: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  const isRunning = status && !["completed", "failed", "cancelled"].includes(status.status);
  const isDone = status?.status === "completed";
  const isFailed = status?.status === "failed";

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 border-b">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base">
            <Video className="h-5 w-5 text-primary" />
            {status?.title || "ویدیوی در حال پردازش"}
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono" dir="ltr">
              {jobId.slice(0, 8)}
            </span>
            <span>•</span>
            <span>زبان مقصد: {status?.target_lang || "fa"}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={status?.status || "queued"} />
          <Button variant="ghost" size="sm" onClick={onClose}>
            بستن
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-4 sm:p-6 space-y-4">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="progress">پیشرفت</TabsTrigger>
            <TabsTrigger value="transcript">متن و ترجمه</TabsTrigger>
            <TabsTrigger value="output">خروجی</TabsTrigger>
          </TabsList>

          <TabsContent value="progress" className="space-y-4 mt-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">
                  {STATUS_LABELS[status?.status || "queued"] || status?.status}
                </span>
                <span className="font-mono">{status?.progress || 0}%</span>
              </div>
              <Progress value={status?.progress || 0} className="h-2" />
            </div>

            <ProgressSteps
              stages={PIPELINE_STAGES}
              currentStage={status?.stage}
              status={status?.status || "queued"}
            />

            {isFailed && status?.error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                  خطا در پردازش
                </div>
                <p className="mt-2 text-xs text-destructive/90 leading-6" dir="auto">
                  {status.error}
                </p>
              </div>
            )}

            {isRunning && (
              <div className="flex gap-2 pt-2">
                <Button variant="outline" size="sm" onClick={cancel}>
                  <XCircle className="h-4 w-4" />
                  لغو پردازش
                </Button>
              </div>
            )}
          </TabsContent>

          <TabsContent value="transcript" className="mt-4">
            <TranscriptView
              jobId={jobId}
              status={status?.status || "queued"}
              stage={status?.stage}
            />
          </TabsContent>

          <TabsContent value="output" className="mt-4 space-y-3">
            {isDone ? (
              <>
                <div className="overflow-hidden rounded-lg border bg-black">
                  <video
                    controls
                    className="aspect-video w-full"
                    src={dubbingApi.videoUrl(jobId)}
                  >
                    مرورگر شما از پخش ویدیو پشتیبانی نمی‌کند.
                  </video>
                </div>
                <Button asChild>
                  <a href={dubbingApi.videoUrl(jobId)} download>
                    <Download className="h-4 w-4" />
                    دانلود ویدیوی دوبله‌شده
                  </a>
                </Button>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                {isRunning ? (
                  <>
                    <Loader2 className="h-10 w-10 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">
                      ویدیوی خروجی پس از تکمیل پردازش نمایش داده می‌شود
                    </p>
                  </>
                ) : isFailed ? (
                  <p className="text-sm text-destructive">پردازش ناموفق بود</p>
                ) : (
                  <p className="text-sm text-muted-foreground">پردازش لغو شد</p>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "completed")
    return (
      <Badge className="gap-1 bg-emerald-600 hover:bg-emerald-600">
        <CheckCircle2 className="h-3 w-3" />
        تکمیل
      </Badge>
    );
  if (status === "failed")
    return (
      <Badge variant="destructive" className="gap-1">
        <AlertTriangle className="h-3 w-3" />
        خطا
      </Badge>
    );
  if (status === "cancelled")
    return (
      <Badge variant="secondary" className="gap-1">
        <XCircle className="h-3 w-3" />
        لغو شد
      </Badge>
    );
  if (status === "queued")
    return (
      <Badge variant="secondary" className="gap-1">
        در صف
      </Badge>
    );
  return (
    <Badge variant="secondary" className="gap-1">
      <Loader2 className="h-3 w-3 animate-spin" />
      در حال پردازش
    </Badge>
  );
}
