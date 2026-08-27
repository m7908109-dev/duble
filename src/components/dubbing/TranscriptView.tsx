"use client";

import { useEffect, useState } from "react";
import { dubbingApi, type Transcript, type Translation } from "@/lib/dubbing-api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  jobId: string;
  status: string;
  stage?: string | null;
}

function fmt(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00:00";
  const t = Math.floor(seconds);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TranscriptView({ jobId, status, stage }: Props) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [translation, setTranslation] = useState<Translation | null>(null);

  const transcriptReady =
    stage === "transcribing" ||
    [
      "translating",
      "generating_voice",
      "synchronizing",
      "rendering",
      "completed",
    ].includes(stage || "") ||
    status === "completed";

  const translationReady =
    ["generating_voice", "synchronizing", "rendering", "completed"].includes(stage || "") ||
    status === "completed";

  useEffect(() => {
    if (!transcriptReady) return;
    let mounted = true;
    dubbingApi
      .getTranscript(jobId)
      .then((t) => {
        if (mounted) setTranscript(t);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [jobId, transcriptReady]);

  useEffect(() => {
    if (!translationReady) return;
    let mounted = true;
    dubbingApi
      .getTranslation(jobId)
      .then((t) => {
        if (mounted) setTranslation(t);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [jobId, translationReady]);

  const segments = transcript?.segments ?? [];
  const transMap = new Map((translation?.segments ?? []).map((s) => [s.id, s.translation]));
  const loadingT = transcriptReady && !transcript;
  const loadingTr = translationReady && !translation;

  return (
    <div className="rounded-lg border bg-card/50">
      <div className="flex flex-wrap items-center gap-2 border-b p-3">
        <h3 className="text-sm font-semibold">متن و ترجمه</h3>
        {transcript?.language && <Badge variant="secondary">زبان مبدا: {transcript.language}</Badge>}
        {translation?.target_language && (
          <Badge variant="secondary">زبان مقصد: {translation.target_language}</Badge>
        )}
        <span className="ms-auto text-xs text-muted-foreground">
          {segments.length} بخش
        </span>
      </div>
      <ScrollArea className="h-[420px] scroll-pretty" dir="rtl">
        <div className="divide-y">
          {loadingT && segments.length === 0 && (
            <div className="space-y-3 p-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}
          {!loadingT && segments.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              {transcriptReady
                ? "هیچ بخش متنی استخراج نشد."
                : "متن پس از مرحله تبدیل گفتار به متن نمایش داده می‌شود."}
            </div>
          )}
          {segments.map((seg) => (
            <div key={seg.id} className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <span className="font-mono text-[10px] text-muted-foreground" dir="ltr">
                  {fmt(seg.start)} → {fmt(seg.end)}
                </span>
                <p className="text-sm leading-6" dir="auto">
                  {seg.text}
                </p>
              </div>
              <div className="flex flex-col gap-1 sm:ps-3 sm:border-s">
                <span className="font-mono text-[10px] text-muted-foreground">ترجمه</span>
                <p className="text-sm leading-6 text-primary-foreground/90" dir="auto">
                  {transMap.get(seg.id) || (loadingTr ? "…" : "")}
                </p>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
