import type { NewsItem } from "@/lib/types";

function escapeYaml(value: string): string {
  return value.replace(/"/g, '\\"');
}

export function newsItemsToObsidianMarkdown(items: NewsItem[]): string {
  return items
    .map((item) => {
      const tags = ["tech-pulse", item.source.replace(/[^\w-]/g, "-")];
      const reasoning = item.ai_reasoning?.trim();

      return `---
title: "${escapeYaml(item.title)}"
source: ${item.source}
url: ${item.url}
hype: ${item.hype_score}
tags: [${tags.join(", ")}]
created: ${item.created_at}
---

# ${item.title}

${item.description.trim()}

${reasoning ? `> **Análise de hype:** ${reasoning}\n` : ""}
[Abrir original](${item.url})
`;
    })
    .join("\n---\n\n");
}

export function downloadObsidianMarkdown(items: NewsItem[], filename?: string): void {
  const markdown = newsItemsToObsidianMarkdown(items);
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download =
    filename ??
    `tech-pulse-${new Date().toISOString().slice(0, 10)}-${items.length}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function copyObsidianMarkdown(items: NewsItem[]): Promise<void> {
  await navigator.clipboard.writeText(newsItemsToObsidianMarkdown(items));
}
