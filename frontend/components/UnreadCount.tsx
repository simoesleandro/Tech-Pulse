"use client";

import { useEffect, useState } from "react";

import { fetchNewsCount } from "@/lib/api";
import { FEED_MUTATION_EVENT } from "@/lib/feed-mutations";

interface UnreadCountProps {
  initialCount: number;
}

export function UnreadCount({ initialCount }: UnreadCountProps) {
  const [count, setCount] = useState(initialCount);

  useEffect(() => {
    setCount(initialCount);
  }, [initialCount]);

  useEffect(() => {
    async function refreshCount() {
      try {
        const next = await fetchNewsCount({
          is_read: false,
          ai_relevance: "RELEVANTE",
        });
        setCount(next);
      } catch {
        /* mantém último valor conhecido */
      }
    }

    const handler = () => {
      void refreshCount();
    };

    window.addEventListener(FEED_MUTATION_EVENT, handler);
    return () => window.removeEventListener(FEED_MUTATION_EVENT, handler);
  }, []);

  return (
    <>
      <span className="text-3xl font-semibold tabular-nums text-cyan">{count}</span>
      <span className="text-muted">não lidas</span>
    </>
  );
}
