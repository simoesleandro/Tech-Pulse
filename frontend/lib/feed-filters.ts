export const PAGE_SIZE = 20;

export const SOURCE_FILTERS = [
  { id: "dev.to", label: "dev.to" },
  { id: "reddit", label: "Reddit" },
  { id: "hacker_news", label: "Hacker News" },
  { id: "github_trends", label: "GitHub" },
  { id: "rss", label: "RSS" },
] as const;

export const MIN_HYPE_FILTERS = [
  { id: "", label: "Qualquer hype" },
  { id: "3", label: "≥ 3★" },
  { id: "4", label: "≥ 4★" },
  { id: "5", label: "≥ 5★" },
] as const;

export const HYPE_FILTERS = [
  { id: "", label: "Hype exato: qualquer" },
  { id: "5", label: "5★" },
  { id: "4", label: "4★" },
  { id: "3", label: "3★" },
  { id: "2", label: "2★" },
  { id: "1", label: "1★" },
  { id: "0", label: "0★" },
] as const;

export const OBSIDIAN_FILTERS = [
  { id: "", label: "Obsidian: todos" },
  { id: "pending", label: "Pendente export" },
  { id: "exported", label: "Já exportado" },
] as const;

/** Chips de assunto/stack — buscam em título e descrição via parâmetro `q`. */
export const TOPIC_FILTERS = [
  { id: "python", label: "Python" },
  { id: "javascript", label: "JavaScript" },
  { id: "typescript", label: "TypeScript" },
  { id: "react", label: "React" },
  { id: "ai", label: "IA" },
  { id: "llm", label: "LLM" },
  { id: "rust", label: "Rust" },
  { id: "go", label: "Go" },
  { id: "docker", label: "Docker" },
  { id: "kubernetes", label: "Kubernetes" },
  { id: "security", label: "Segurança" },
  { id: "database", label: "Banco de dados" },
] as const;
