"use client";

interface HypeStarsProps {
  score: number;
}

export function HypeStars({ score }: HypeStarsProps) {
  const clamped = Math.min(5, Math.max(0, score));

  return (
    <div
      className="flex items-center gap-0.5"
      aria-label={`Hype da comunidade: ${clamped} de 5 estrelas`}
    >
      {Array.from({ length: 5 }).map((_, index) => {
        const filled = index < clamped;
        return (
          <span
            key={index}
            aria-hidden="true"
            className={`text-sm ${filled ? "text-cyan" : "text-border"}`}
          >
            ★
          </span>
        );
      })}
      <span className="ml-1 font-mono text-[10px] text-muted">{clamped}/5</span>
    </div>
  );
}
