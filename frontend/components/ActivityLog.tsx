"use client";

export type StepStatus = "pending" | "active" | "done" | "error";

export interface ActivityStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

interface ActivityLogProps {
  title: string;
  steps: ActivityStep[];
  visible: boolean;
  statusLine?: string | null;
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done") {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald/20 text-emerald">
        <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 8l3.5 3.5L13 4" />
        </svg>
      </span>
    );
  }

  if (status === "error") {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-crimson/20 text-crimson">
        <span aria-hidden="true" className="text-xs font-bold">!</span>
      </span>
    );
  }

  if (status === "active") {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center">
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-cyan/30 border-t-cyan"
          role="status"
          aria-label="Em andamento"
        />
      </span>
    );
  }

  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border/80">
      <span className="h-1.5 w-1.5 rounded-full bg-muted/40" />
    </span>
  );
}

export function ActivityLog({ title, steps, visible, statusLine }: ActivityLogProps) {
  if (!visible) {
    return null;
  }

  if (steps.length === 0) {
    return (
      <div
        className="mt-4 rounded-md border border-cyan/30 bg-slate-dark/80 p-4"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <p className="font-mono text-[10px] uppercase tracking-widest text-cyan">
          {title || "Processando"}
        </p>
        <div className="mt-3 flex items-center gap-3">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-cyan/30 border-t-cyan" />
          <p className="text-sm text-foreground">
            {statusLine || "Iniciando operação com o Gemma4…"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="mt-4 rounded-md border border-cyan/20 bg-slate-dark/60 p-4"
      role="status"
      aria-live="polite"
      aria-busy={steps.some((s) => s.status === "active")}
    >
      <p className="font-mono text-[10px] uppercase tracking-widest text-cyan">
        {title}
      </p>

      {statusLine ? (
        <p className="mt-2 text-xs text-cyan/90">{statusLine}</p>
      ) : null}

      <ol className="mt-3 space-y-2.5">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`flex gap-3 ${
              step.status === "pending" ? "opacity-45" : "opacity-100"
            }`}
          >
            <div className="flex flex-col items-center">
              <StepIcon status={step.status} />
              {index < steps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={`mt-1 w-px flex-1 min-h-3 ${
                    step.status === "done" ? "bg-emerald/40" : "bg-border/60"
                  }`}
                />
              ) : null}
            </div>

            <div className="min-w-0 pb-1">
              <p
                className={`text-sm leading-snug ${
                  step.status === "active"
                    ? "text-foreground"
                    : step.status === "done"
                      ? "text-muted"
                      : "text-muted/80"
                }`}
              >
                {step.label}
              </p>
              {step.detail ? (
                <p className="mt-0.5 font-mono text-[10px] text-cyan/80">
                  {step.detail}
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function buildSteps(
  defs: Array<{ id: string; label: string }>,
  activeIndex: number,
  doneUntil = activeIndex,
): ActivityStep[] {
  return defs.map((def, index) => ({
    ...def,
    status:
      index < doneUntil
        ? "done"
        : index === activeIndex
          ? "active"
          : "pending",
  }));
}

export function markAllDone(
  steps: ActivityStep[],
  lastDetail?: string,
): ActivityStep[] {
  return steps.map((step, index) => ({
    ...step,
    status: "done" as const,
    detail:
      index === steps.length - 1 && lastDetail ? lastDetail : step.detail,
  }));
}
