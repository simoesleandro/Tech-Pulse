"use client";

import { useCallback, useState } from "react";

import type { ActivityStep, StepStatus } from "@/components/ActivityLog";
import type { PipelineStepEvent } from "@/lib/types";

export interface ParallelItemState {
  title: string;
  step_id: string;
  status: string;
  detail?: string;
  timestamp: number;
}

export function syncParallelSteps(
  prev: ActivityStep[],
  itemsMap: Record<number, ParallelItemState>,
  totalItems: number,
  stepOrder: string[],
  onlyStepIds?: Set<string>,
): ActivityStep[] {
  if (totalItems === 0) {
    return prev;
  }

  return prev.map((step) => {
    if (onlyStepIds && !onlyStepIds.has(step.id)) {
      return step;
    }

    const stepIdx = stepOrder.indexOf(step.id);
    if (stepIdx === -1) {
      return step;
    }

    let completedCount = 0;
    const activeItems: number[] = [];

    for (const [idxStr, info] of Object.entries(itemsMap)) {
      const idx = parseInt(idxStr, 10);
      const currentStepIdx = stepOrder.indexOf(info.step_id);

      if (
        currentStepIdx > stepIdx ||
        (currentStepIdx === stepIdx && info.status === "done")
      ) {
        completedCount++;
      } else if (currentStepIdx === stepIdx && info.status === "active") {
        activeItems.push(idx);
      }
    }

    let status: StepStatus = "pending";
    let detail = "";

    if (completedCount === totalItems) {
      status = "done";
      detail = `Todos os ${totalItems} itens processados.`;
    } else if (
      activeItems.length > 0 ||
      (completedCount > 0 && completedCount < totalItems)
    ) {
      status = "active";
      detail = `Processando: ${
        activeItems.length > 0
          ? `Item(s) ${activeItems.join(", ")}`
          : "aguardando"
      } · ${completedCount}/${totalItems} concluídos`;
    } else {
      status = "pending";
      detail = "Aguardando itens...";
    }

    return { ...step, status, detail };
  });
}

export function useParallelPipelineProgress(
  stepOrder: string[],
  onlyStepIds?: Set<string>,
) {
  const [itemsMap, setItemsMap] = useState<Record<number, ParallelItemState>>({});
  const [totalItems, setTotalItems] = useState(0);

  const reset = useCallback(() => {
    setItemsMap({});
    setTotalItems(0);
  }, []);

  const recordParallelEvent = useCallback((event: PipelineStepEvent): boolean => {
    if (event.type !== "step" || !event.article_index) {
      return false;
    }

    if (event.article_total) {
      setTotalItems(event.article_total);
    }

    const idx = event.article_index;
    setItemsMap((prev) => ({
      ...prev,
      [idx]: {
        title: event.title || prev[idx]?.title || "",
        step_id: event.step_id,
        status: event.status,
        detail: event.detail,
        timestamp: Date.now(),
      },
    }));
    return true;
  }, []);

  const syncSteps = useCallback(
    (prev: ActivityStep[]) =>
      syncParallelSteps(prev, itemsMap, totalItems, stepOrder, onlyStepIds),
    [itemsMap, totalItems, stepOrder, onlyStepIds],
  );

  return {
    itemsMap,
    totalItems,
    reset,
    recordParallelEvent,
    syncSteps,
  };
}
