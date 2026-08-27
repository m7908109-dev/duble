"use client";

import { useEffect, useState } from "react";
import { Settings as SettingsIcon, KeyRound, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { dubbingApi, type SettingsView } from "@/lib/dubbing-api";
import { toast } from "sonner";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

export function SettingsDialog({ open, onOpenChange, onSaved }: Props) {
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [key, setKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    dubbingApi
      .getSettings()
      .then((s) => {
        setSettings(s);
        setKey("");
      })
      .finally(() => setLoading(false));
  }, [open]);

  async function save() {
    if (!key.trim()) {
      toast.error("لطفاً کلید API را وارد کنید");
      return;
    }
    setSaving(true);
    try {
      const res = await dubbingApi.updateSettings(key.trim());
      if (res.has_gemini_key) {
        toast.success("کلید Gemini با موفقیت ذخیره شد");
        onSaved();
        onOpenChange(false);
      } else {
        toast.error("ذخیره کلید ناموفق بود");
      }
    } catch (e) {
      toast.error(`خطا: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <SettingsIcon className="h-4 w-4" />
          تنظیمات
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-primary" />
            تنظیمات سامانه
          </DialogTitle>
          <DialogDescription>
            کلید API رایگان Gemini خود را وارد کنید. کلید فقط در حافظه‌ی پردازش نگه داشته می‌شود و
            هرگز در فایل، دیتابیس یا گزارش‌ها ذخیره نمی‌شود. برای ماندگاری، آن را در فایل
            <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">.env</code>
            قرار دهید.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            بارگذاری...
          </div>
        )}

        {settings && !loading && (
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border bg-muted/40 p-3">
              <span className="text-sm">وضعیت کلید Gemini</span>
              {settings.has_gemini_key ? (
                <Badge className="gap-1 bg-emerald-600 hover:bg-emerald-600">
                  <CheckCircle2 className="h-3 w-3" />
                  تنظیم شده
                </Badge>
              ) : (
                <Badge variant="destructive" className="gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  تنظیم نشده
                </Badge>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="gemini-key">کلید API Gemini</Label>
              <Input
                id="gemini-key"
                type="password"
                placeholder="AIza..."
                value={key}
                onChange={(e) => setKey(e.target.value)}
                autoComplete="off"
              />
              <p className="text-xs text-muted-foreground">
                کلید را از{" "}
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline"
                >
                  Google AI Studio
                </a>{" "}
                دریافت کنید.
              </p>
            </div>

            <div className="rounded-lg border p-3 text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">مدل Whisper</span>
                <span className="font-mono">{settings.whisper_model}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">موتور TTS</span>
                <span className="font-mono">{settings.tts_provider}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">CPU</span>
                <span className="font-mono">{settings.resources.cpu_count} هسته</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">RAM</span>
                <span className="font-mono">{settings.resources.ram_gb} GB</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">GPU</span>
                <span className="font-mono">
                  {settings.resources.has_cuda
                    ? settings.resources.cuda_device_name || "دارد"
                    : "ندارد (CPU-only)"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">FFmpeg</span>
                <span className="font-mono">
                  {settings.resources.ffmpeg_available ? "آماده" : "نصب نیست"}
                </span>
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            انصراف
          </Button>
          <Button onClick={save} disabled={saving || !key.trim()}>
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                در حال ذخیره...
              </>
            ) : (
              "ذخیره کلید"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
