import type { FeedView } from "@/lib/types";

interface EmptyStateProps {
  view: FeedView;
  hasActiveFilters?: boolean;
}

const COPY: Record<FeedView, { title: string; body: string; filteredBody: string }> = {
  queue: {
    title: "Fila vazia",
    body: "Nenhum artigo relevante aguardando leitura. Clique em Atualizar feed para buscar novidades.",
    filteredBody: "Nenhum artigo corresponde aos filtros ativos. Limpe a busca ou ajuste os filtros.",
  },
  read: {
    title: "Nada lido ainda",
    body: "Artigos marcados como lidos aparecem aqui depois que você consumir o conteúdo.",
    filteredBody: "Nenhum artigo lido corresponde aos filtros ativos.",
  },
  saved: {
    title: "Nenhum salvamento",
    body: "Use o ícone de favorito em um artigo para guardá-lo nesta lista.",
    filteredBody: "Nenhum artigo salvo corresponde aos filtros ativos.",
  },
  obsidian: {
    title: "Vault vazio",
    body: "Notas exportadas ao Obsidian aparecem aqui. Use Exportar no card ou no painel Sistema.",
    filteredBody: "Nenhuma nota exportada corresponde aos filtros ativos.",
  },
  lixo: {
    title: "Nada descartado",
    body: "Artigos classificados como LIXO pelo triador aparecem aqui para revisão.",
    filteredBody: "Nenhum artigo descartado corresponde aos filtros ativos.",
  },
};

export function EmptyState({ view, hasActiveFilters = false }: EmptyStateProps) {
  const content = COPY[view];

  return (
    <div className="rounded-lg border border-dashed border-border bg-surface/50 px-6 py-12 text-center">
      <p className="font-mono text-sm uppercase tracking-wide text-cyan">
        {hasActiveFilters ? "Sem resultados" : content.title}
      </p>
      <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
        {hasActiveFilters ? content.filteredBody : content.body}
      </p>
    </div>
  );
}
