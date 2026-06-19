import { UnreadCount } from "@/components/UnreadCount";

interface HeaderProps {
  unreadCount: number;
}

export function Header({ unreadCount }: HeaderProps) {
  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-6">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan">
            engineering intelligence
          </p>
          <h1 className="mt-1 font-mono text-2xl font-semibold tracking-tight sm:text-3xl">
            TECH<span className="text-cyan">[PULSE]</span>
          </h1>
          <p className="mt-1 max-w-md text-sm text-muted">
            Sinal técnico curado por IA local. Sem ruído, sem gamificação.
          </p>
        </div>
        <div className="flex items-baseline gap-2 font-mono text-sm">
          <UnreadCount initialCount={unreadCount} />
        </div>
      </div>
    </header>
  );
}
