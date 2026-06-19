"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[40vh] max-w-lg flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="font-mono text-sm uppercase tracking-wide text-crimson">
        Erro no feed
      </p>
      <p className="text-sm text-muted">
        {error.message || "Algo deu errado ao carregar o Tech-Pulse."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="btn-interactive rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan"
      >
        Tentar novamente
      </button>
    </div>
  );
}
