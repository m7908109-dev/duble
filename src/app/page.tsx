"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  Github,
  Languages,
  Mic2,
  Video,
  Clapperboard,
  Moon,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { NewJobForm } from "@/components/dubbing/NewJobForm";
import { JobDetail } from "@/components/dubbing/JobDetail";
import { JobList } from "@/components/dubbing/JobList";
import { SettingsDialog } from "@/components/dubbing/SettingsDialog";
import {
  dubbingApi,
  type Language,
  type VoiceInfo,
  type JobStatus,
} from "@/lib/dubbing-api";
import { toast } from "sonner";

export default function Home() {
  const { setTheme } = useTheme();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hasGeminiKey, setHasGeminiKey] = useState(false);
  const [languages, setLanguages] = useState<{ source: Language[]; target: Language[] }>({
    source: [],
    target: [],
  });
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [defaultVoice, setDefaultVoice] = useState("fa-IR-GhazalNeural");
  const [activeJob, setActiveJob] = useState<{ jobId: string; status?: JobStatus } | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([dubbingApi.getLanguages(), dubbingApi.getSettings()])
      .then(([langRes, setRes]) => {
        if (cancelled) return;
        setLanguages(langRes);
        setVoices(setRes.available_voices);
        setDefaultVoice(setRes.tts_default_voice);
        setHasGeminiKey(setRes.has_gemini_key);
      })
      .catch((e) => {
        if (cancelled) return;
        toast.error(`ارتباط با سرور برقرار نشد: ${e instanceof Error ? e.message : String(e)}`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function reloadSettings() {
    try {
      const setRes = await dubbingApi.getSettings();
      setVoices(setRes.available_voices);
      setDefaultVoice(setRes.tts_default_voice);
      setHasGeminiKey(setRes.has_gemini_key);
    } catch {
      // ignore
    }
  }

  async function handleCreate(params: {
    url: string;
    source_lang: string;
    target_lang: string;
    tts_provider: string;
    tts_voice: string;
    keep_original_audio: boolean;
    original_audio_volume: number;
    dub_audio_volume: number;
    output_format: string;
  }) {
    try {
      const res = await dubbingApi.createJob(params);
      toast.success("کار دوبله ایجاد شد");
      setActiveJob({ jobId: res.job_id, status: undefined });
      setRefreshKey((k) => k + 1);
    } catch (e) {
      toast.error(`ایجاد کار ناموفق بود: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  function selectJob(jobId: string, status: JobStatus) {
    setActiveJob({ jobId, status });
  }

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 p-3 sm:p-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Clapperboard className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <h1 className="text-sm font-bold sm:text-base">موتور دوبله خودکار ویدیو</h1>
              <p className="hidden text-[10px] text-muted-foreground sm:block">
                Whisper + Gemini + TTS رایگان
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(document.documentElement.classList.contains("dark") ? "light" : "dark")}
              aria-label="تغییر پوسته"
            >
              <Sun className="hidden h-4 w-4 dark:block" />
              <Moon className="block h-4 w-4 dark:hidden" />
            </Button>
            <SettingsDialog
              open={settingsOpen}
              onOpenChange={setSettingsOpen}
              onSaved={reloadSettings}
            />
            <Button variant="ghost" size="icon" asChild>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                aria-label="دریافت کلید Gemini"
              >
                <Github className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="hero-gradient border-b">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
          <div className="flex flex-col items-start gap-4">
            <div className="inline-flex items-center gap-2 rounded-full border bg-card/50 px-3 py-1 text-xs text-muted-foreground">
              <Sparkles className="h-3 w-3 text-primary" />
              کاملاً متن‌باز و رایگان • مناسب GitHub Codespaces
            </div>
            <h2 className="text-2xl font-bold leading-tight sm:text-3xl">
              ویدیوی یوتیوب را به صدا دلخواه خود دوبله کن
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground sm:text-base leading-7">
              یک URL یوتیوب وارد کنید. سامانه گفتار را با{" "}
              <span className="font-semibold text-foreground">Whisper</span> به متن تبدیل می‌کند،
              با <span className="font-semibold text-foreground">Gemini</span> ترجمه می‌کند، صدای
              دوبله را با موتور رایگان TTS می‌سازد، و ویدیوی نهایی را تحویل می‌دهد.
            </p>
            <div className="grid w-full grid-cols-2 gap-3 sm:grid-cols-4">
              <Feature icon={<Video className="h-4 w-4" />} label="یوتیوب" />
              <Feature icon={<Mic2 className="h-4 w-4" />} label="Whisper STT" />
              <Feature icon={<Languages className="h-4 w-4" />} label="Gemini ترجمه" />
              <Feature icon={<Clapperboard className="h-4 w-4" />} label="ویدیوی دوبله" />
            </div>
          </div>
        </div>
      </section>

      {/* Main content */}
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <NewJobForm
              languages={languages}
              voices={voices}
              defaultVoice={defaultVoice}
              onCreate={handleCreate}
              hasGeminiKey={hasGeminiKey}
            />
            {activeJob && (
              <JobDetail
                jobId={activeJob.jobId}
                initialStatus={activeJob.status}
                onClose={() => {
                  setActiveJob(null);
                  setRefreshKey((k) => k + 1);
                }}
              />
            )}
          </div>
          <aside className="space-y-6">
            <JobList onSelect={selectJob} refreshKey={refreshKey} />
            <Card className="p-4 text-xs leading-6 text-muted-foreground">
              <p className="font-semibold text-foreground mb-2">درباره‌ی سامانه</p>
              <p>
                این سامانه برای دریافت و پردازش محتوایی استفاده می‌شود که شما مجاز به دانلود
                و پردازش آن هستید. لطفاً حقوق صاحب محتوا و محدودیت‌های یوتیوب را رعایت کنید.
              </p>
              <p className="mt-2">
                پردازش‌ها روی CPU انجام می‌شود. برای ویدیوهای طولانی، زمان بیشتری لازم است.
              </p>
            </Card>
          </aside>
        </div>
      </main>

      {/* Sticky footer */}
      <footer className="mt-auto border-t bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 p-4 text-xs text-muted-foreground sm:flex-row">
          <p>موتور دوبله خودکار ویدیو — متن‌باز و رایگان</p>
          <p className="flex items-center gap-2">
            ساخته‌شده با FastAPI + Next.js + Whisper + Gemini
          </p>
        </div>
      </footer>
    </div>
  );
}

function Feature({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-card/50 px-3 py-2">
      <span className="text-primary">{icon}</span>
      <span className="text-xs font-medium">{label}</span>
    </div>
  );
}
