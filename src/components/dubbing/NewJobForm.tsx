"use client";

import { useState } from "react";
import {
  Search,
  Loader2,
  Youtube,
  Play,
  Volume2,
  AudioLines,
  Globe,
  Settings2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dubbingApi, type VideoInfo, type Language, type VoiceInfo } from "@/lib/dubbing-api";
import { toast } from "sonner";

interface Props {
  languages: { source: Language[]; target: Language[] };
  voices: VoiceInfo[];
  defaultVoice: string;
  onCreate: (params: {
    url: string;
    source_lang: string;
    target_lang: string;
    tts_provider: string;
    tts_voice: string;
    keep_original_audio: boolean;
    original_audio_volume: number;
    dub_audio_volume: number;
    output_format: string;
  }) => void;
  hasGeminiKey: boolean;
}

function fmtDuration(s: number): string {
  if (!s) return "—";
  const t = Math.round(s);
  const m = Math.floor(t / 60);
  const sec = t % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}:${String(m % 60).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export function NewJobForm({ languages, voices, defaultVoice, onCreate, hasGeminiKey }: Props) {
  const [url, setUrl] = useState("");
  const [inspecting, setInspecting] = useState(false);
  const [video, setVideo] = useState<VideoInfo | null>(null);
  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("fa");
  const [ttsVoice, setTtsVoice] = useState(defaultVoice || "fa-IR-DilaraNeural");
  const [keepOriginal, setKeepOriginal] = useState(false);
  const [originalVol, setOriginalVol] = useState(20);
  const [dubVol, setDubVol] = useState(100);
  const [outputFormat, setOutputFormat] = useState("mp4");
  const [creating, setCreating] = useState(false);

  async function inspect() {
    if (!url.trim()) {
      toast.error("لطفاً URL یوتیوب را وارد کنید");
      return;
    }
    setInspecting(true);
    setVideo(null);
    try {
      const info = await dubbingApi.inspect(url.trim());
      setVideo(info);
      toast.success("اطلاعات ویدیو دریافت شد");
    } catch (e) {
      toast.error(`دریافت اطلاعات ناموفق: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setInspecting(false);
    }
  }

  function start() {
    if (!video) {
      toast.error("ابتدا ویدیو را بررسی کنید");
      return;
    }
    if (!hasGeminiKey) {
      toast.error("برای ترجمه، ابتدا کلید Gemini را در تنظیمات وارد کنید");
      return;
    }
    setCreating(true);
    onCreate({
      url: video.url,
      source_lang: sourceLang,
      target_lang: targetLang,
      tts_provider: "edge",
      tts_voice: effectiveVoice,
      keep_original_audio: keepOriginal,
      original_audio_volume: originalVol / 100,
      dub_audio_volume: dubVol / 100,
      output_format: outputFormat,
    });
    setCreating(false);
  }

  const filteredVoices = voices.filter((v) =>
    v.language.toLowerCase().startsWith(targetLang.toLowerCase() + "-")
  );
  const voicesToShow = filteredVoices.length > 0 ? filteredVoices : voices.slice(0, 8);
  // Use the configured voice if it's a valid option; otherwise fall back to the
  // first available voice for the selected language.
  const effectiveVoice = voicesToShow.some((v) => v.id === ttsVoice)
    ? ttsVoice
    : voicesToShow[0]?.id || ttsVoice;

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-5 sm:p-6 space-y-5">
        {/* URL section */}
        <div className="space-y-2">
          <Label className="flex items-center gap-2 text-base font-semibold">
            <Youtube className="h-5 w-5 text-primary" />
            URL ویدیوی یوتیوب
          </Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              dir="ltr"
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") inspect();
              }}
              className="font-mono text-sm"
            />
            <Button onClick={inspect} disabled={inspecting} className="shrink-0">
              {inspecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  بررسی...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4" />
                  بررسی ویدیو
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Video preview */}
        {video && (
          <div className="grid gap-4 sm:grid-cols-[200px_1fr]">
            <div className="overflow-hidden rounded-lg border bg-muted">
              <img
                src={video.thumbnail}
                alt={video.title}
                className="aspect-video w-full object-cover"
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-base font-semibold leading-7" dir="auto">
                {video.title}
              </h3>
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                {video.channel && <span>{video.channel}</span>}
                <span>•</span>
                <span>{fmtDuration(video.duration)}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {video.available_qualities.slice(0, 6).map((q) => (
                  <Badge key={q} variant="secondary" className="text-[10px]">
                    {q}
                  </Badge>
                ))}
                {video.available_qualities.length === 0 && (
                  <span className="text-xs text-muted-foreground">کیفیت‌ها نامشخص</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Dubbing settings */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              زبان اصلی ویدیو
            </Label>
            <Select value={sourceLang} onValueChange={setSourceLang}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {languages.source.map((l) => (
                  <SelectItem key={l.code} value={l.code}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              زبان مقصد دوبله
            </Label>
            <Select value={targetLang} onValueChange={setTargetLang}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {languages.target.map((l) => (
                  <SelectItem key={l.code} value={l.code}>
                    {l.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2 sm:col-span-2">
            <Label className="flex items-center gap-2">
              <AudioLines className="h-4 w-4 text-muted-foreground" />
              صدای دوبله (TTS)
            </Label>
            <Select value={effectiveVoice} onValueChange={setTtsVoice}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {voicesToShow.map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    <span className="font-mono text-xs">{v.id}</span>
                    <span className="text-muted-foreground"> — {v.gender}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {filteredVoices.length} صدا برای این زبان • {voices.length} صدا در مجموع
            </p>
          </div>
        </div>

        {/* Advanced */}
        <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Settings2 className="h-4 w-4 text-primary" />
            تنظیمات پیشرفته
          </div>

          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Volume2 className="h-4 w-4" />
                حفظ صدای اصلی
              </div>
              <p className="text-xs text-muted-foreground">
                صدای اصلی ویدیو را در پس‌زمینه همراه با دوبله پخش کن
              </p>
            </div>
            <Switch checked={keepOriginal} onCheckedChange={setKeepOriginal} />
          </div>

          {keepOriginal && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span>شدت صدای اصلی</span>
                  <span className="font-mono">{originalVol}%</span>
                </div>
                <Slider
                  value={[originalVol]}
                  onValueChange={(v) => setOriginalVol(v[0])}
                  min={0}
                  max={100}
                  step={5}
                />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span>شدت صدای دوبله</span>
                  <span className="font-mono">{dubVol}%</span>
                </div>
                <Slider
                  value={[dubVol]}
                  onValueChange={(v) => setDubVol(v[0])}
                  min={0}
                  max={100}
                  step={5}
                />
              </div>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-xs">فرمت خروجی</Label>
              <Select value={outputFormat} onValueChange={setOutputFormat}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mp4">MP4 (H.264)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <Button
          onClick={start}
          disabled={!video || creating || !hasGeminiKey}
          size="lg"
          className="w-full"
        >
          <Play className="h-5 w-5" />
          شروع دوبله
        </Button>
        {!hasGeminiKey && (
          <p className="text-center text-xs text-destructive">
            برای شروع دوبله ابتدا کلید Gemini را در تنظیمات وارد کنید
          </p>
        )}
      </CardContent>
    </Card>
  );
}
