import type { FeedView } from "@/lib/types";

interface EmptyStateProps {
  view: FeedView;
}

const COPY: Record<FeedView, { title: string; body: string }> = {
  queue: {
    title: "Fila vazia",
    body: "Nenhum artigo relevante aguardando leitura. Clique em Atualizar feed para buscar novidades.",
  },
  read: {
    title: "Nada lido ainda",
    body: "Artigos marcados como lidos aparecem aqui depois que você consumir o conteúdo.",
  },
  saved: {
    title: "Nenhum salvamento",
    body: "Use o ícone de favorito em um artigo para guardá-lo nesta lista.",
  },
};

export function EmptyState({ view }: EmptyStateProps) {
  const content = COPY[view];

  return (
    <div className="rounded-lg border border-dashed border-border bg-surface/50 px-6 py-12 text-center">
      <p className="font-mono text-sm uppercase tracking-wide text-cyan">
        {content.title}
      </p>
      <p className="mx-auto mt-2 max-w-sm text-sm text-muted">{content.body}</p>
    </div>
  );
}
