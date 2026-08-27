"use client";

import { Check, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StageDef {
  key: string;
  label: string;
}

interface Props {
  stages: StageDef[];
  currentStage?: string | null;
  status: string;
}

/**
 * Renders the ordered pipeline stages with check / active / pending markers.
 *  ✓ done   ● active   ○ pending
 */
export function ProgressSteps({ stages, currentStage, status }: Props) {
  const currentIndex = stages.findIndex((s) => s.key === currentStage);
  const isTerminal = status === "completed" || status === "failed" || status === "cancelled";

  return (
    <ol className="flex flex-col gap-1.5">
      {stages.map((stage, idx) => {
        const done =
          status === "completed" ||
          currentIndex > idx ||
          (currentStage === stage.key && status === "completed");
        const active = currentStage === stage.key && !isTerminal;
        const pending = !done && !active;
        return (
          <li key={stage.key} className="flex items-center gap-3">
            <span
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full border-2 transition-colors shrink-0",
                done && "border-primary bg-primary text-primary-foreground",
                active && "border-primary text-primary pulse-ring",
                pending && "border-muted-foreground/30 text-muted-foreground/50"
              )}
            >
              {done ? (
                <Check className="h-4 w-4" />
              ) : active ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Circle className="h-3 w-3" />
              )}
            </span>
            <span
              className={cn(
                "text-sm",
                done && "text-foreground font-medium",
                active && "text-primary font-semibold",
                pending && "text-muted-foreground"
              )}
            >
              {stage.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
