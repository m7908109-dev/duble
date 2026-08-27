"use client";

// API client for the Automatic Video Dubbing Engine backend.
// The backend runs on port 8000 behind the Caddy gateway, so all requests
// go through the XTransformPort query parameter.

const PORT = "8000";

function apiUrl(path: string): string {
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}XTransformPort=${PORT}`;
}

export interface VideoInfo {
  video_id: string;
  title: string;
  channel: string;
  duration: number;
  thumbnail: string;
  available_qualities: string[];
  url: string;
}

export interface CreateJobRequest {
  url: string;
  source_lang: string;
  target_lang: string;
  tts_provider: string;
  tts_voice: string;
  keep_original_audio: boolean;
  original_audio_volume: number;
  dub_audio_volume: number;
  output_format: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  stage?: string | null;
  error?: string | null;
  title?: string | null;
  target_lang: string;
  output_format: string;
}

export interface VoiceInfo {
  id: string;
  name: string;
  language: string;
  gender: string;
  provider?: string;
}

export interface SettingsView {
  has_gemini_key: boolean;
  whisper_model: string;
  tts_provider: string;
  tts_default_voice: string;
  available_voices: VoiceInfo[];
  resources: {
    cpu_count: number;
    ram_gb: number;
    has_cuda: boolean;
    cuda_device_name: string | null;
    ffmpeg_available: boolean;
    yt_dlp_available: boolean;
  };
}

export interface Language {
  code: string;
  name: string;
}

export interface TranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  language: string | null;
  duration: number | null;
  segments: TranscriptSegment[];
}

export interface TranslationSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  translation: string;
}

export interface Translation {
  source_language: string | null;
  target_language: string;
  segments: TranslationSegment[];
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const dubbingApi = {
  async inspect(url: string): Promise<VideoInfo> {
    const res = await fetch(apiUrl("/api/video/inspect"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    return handle<VideoInfo>(res);
  },

  async createJob(req: CreateJobRequest): Promise<{ job_id: string; status: string }> {
    const res = await fetch(apiUrl("/api/jobs"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    return handle(res);
  },

  async listJobs(limit = 50): Promise<JobStatus[]> {
    const res = await fetch(apiUrl(`/api/jobs?limit=${limit}`));
    return handle(res);
  },

  async getJob(jobId: string): Promise<JobStatus> {
    const res = await fetch(apiUrl(`/api/jobs/${jobId}`));
    return handle(res);
  },

  async cancelJob(jobId: string): Promise<{ ok: boolean; status: string }> {
    const res = await fetch(apiUrl(`/api/jobs/${jobId}/cancel`), { method: "POST" });
    return handle(res);
  },

  videoUrl(jobId: string): string {
    return apiUrl(`/api/jobs/${jobId}/video`);
  },

  async getTranscript(jobId: string): Promise<Transcript> {
    const res = await fetch(apiUrl(`/api/jobs/${jobId}/transcript`));
    return handle(res);
  },

  async getTranslation(jobId: string): Promise<Translation> {
    const res = await fetch(apiUrl(`/api/jobs/${jobId}/translation`));
    return handle(res);
  },

  async getSettings(): Promise<SettingsView> {
    const res = await fetch(apiUrl("/api/settings"));
    return handle(res);
  },

  async updateSettings(gemini_api_key: string): Promise<{ ok: boolean; has_gemini_key: boolean }> {
    const res = await fetch(apiUrl("/api/settings"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gemini_api_key }),
    });
    return handle(res);
  },

  async getLanguages(): Promise<{ source: Language[]; target: Language[] }> {
    const res = await fetch(apiUrl("/api/languages"));
    return handle(res);
  },

  async getTtsVoices(provider?: string, language?: string): Promise<{ voices: VoiceInfo[] }> {
    const params = new URLSearchParams();
    if (provider) params.set("provider", provider);
    if (language) params.set("language", language);
    const q = params.toString();
    const res = await fetch(apiUrl(`/api/tts/voices${q ? `?${q}` : ""}`));
    return handle(res);
  },

  // Subscribe to a job's SSE stream.
  // Returns a function to close the stream.
  subscribe(
    jobId: string,
    onStatus: (data: { status: string; progress: number; stage?: string | null; error?: string | null }) => void,
    onDone: () => void
  ): () => void {
    const es = new EventSource(apiUrl(`/api/jobs/${jobId}/events`));
    es.addEventListener("status", (e) => {
      try {
        onStatus(JSON.parse((e as MessageEvent).data));
      } catch {
        // ignore
      }
    });
    es.addEventListener("done", () => {
      onDone();
      es.close();
    });
    es.onerror = () => {
      // The browser will auto-reconnect; nothing extra to do.
    };
    return () => es.close();
  },
};
