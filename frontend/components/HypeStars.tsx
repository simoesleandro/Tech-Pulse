"use client";

interface HypeStarsProps {
  score: number;
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className={`h-4 w-4 ${filled ? "text-amber-400" : "text-muted/35"}`}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.25"
    >
      <path d="M10 2.5l2.2 4.45 4.92.72-3.56 3.47.84 4.9L10 13.9l-4.4 2.14.84-4.9-3.56-3.47 4.92-.72L10 2.5z" />
    </svg>
  );
}

export function HypeStars({ score }: HypeStarsProps) {
  const numeric = Number(score);
  const clamped = Number.isFinite(numeric)
    ? Math.min(5, Math.max(0, Math.round(numeric)))
    : 0;

  return (
    <div
      className="flex items-center gap-0.5"
      aria-label={`Hype da comunidade: ${clamped} de 5 estrelas`}
    >
      {Array.from({ length: 5 }).map((_, index) => (
        <StarIcon key={index} filled={index < clamped} />
      ))}
      <span className="ml-1.5 font-mono text-[10px] text-amber-400/90">
        {clamped}/5
      </span>
      {clamped === 0 ? (
        <span className="ml-1 text-[10px] text-muted">aguardando avaliação</span>
      ) : null}
    </div>
  );
}
