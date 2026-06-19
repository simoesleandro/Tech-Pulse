"use client";

import { useCallback, useState } from "react";

import { markAllDone, type ActivityStep } from "@/components/ActivityLog";
import type { PipelineStepDef } from "@/lib/pipeline-steps";

interface CancelOptions {
  label?: string;
  message?: string;
}

export function usePipelineStream() {
  const [isRunning, setIsRunning] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(
    null,
  );
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [logTitle, setLogTitle] = useState("");
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const begin = useCallback((title: string, initialSteps: PipelineStepDef[]) => {
    const controller = new AbortController();
    setAbortController(controller);
    setError(null);
    setIsRunning(true);
    setLogTitle(title);
    setStatusLine(null);
    setSteps(
      initialSteps.map((def, index) => ({
        ...def,
        status: index === 0 ? "active" : "pending",
      })),
    );
    return controller;
  }, []);

  const cancel = useCallback(
    (options?: CancelOptions) => {
      if (!abortController) {
        return;
      }
      abortController.abort();
      const label = options?.label ?? "Operação cancelada.";
      const message = options?.message ?? "Operação interrompida pelo usuário.";
      setSteps((prev) => {
        const withErrors = prev.map((step) =>
          step.status === "active"
            ? {
                ...step,
                status: "error" as const,
                detail: "Cancelado pelo usuário.",
              }
            : step,
        );
        return [
          ...withErrors,
          {
            id: "cancelled",
            label,
            status: "error" as const,
            detail: message,
          },
        ];
      });
      setError(message);
      setIsRunning(false);
      setAbortController(null);
    },
    [abortController],
  );

  const finish = useCallback(() => {
    setIsRunning(false);
    setAbortController(null);
  }, []);

  const completeSteps = useCallback((fallback: PipelineStepDef[]) => {
    setSteps((prev) =>
      markAllDone(
        prev.length > 0
          ? prev
          : fallback.map((def) => ({ ...def, status: "pending" as const })),
      ),
    );
  }, []);

  return {
    isRunning,
    steps,
    setSteps,
    logTitle,
    setLogTitle,
    statusLine,
    setStatusLine,
    error,
    setError,
    abortController,
    begin,
    cancel,
    finish,
    completeSteps,
  };
}
