import { formatNewsForObsidian } from "@/lib/api";
import type { NewsItem } from "@/lib/types";

function escapeYaml(value: string): string {
  return value.replace(/"/g, '\\"');
}

function fallbackMarkdown(items: NewsItem[]): string {
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

> [!abstract] Visão geral
> ${item.description.trim()}

${reasoning ? `> [!info] Avaliação Tech-Pulse\n> ${reasoning}\n` : ""}
[Fonte original](${item.url})
`;
    })
    .join("\n---\n\n");
}

export async function newsItemsToObsidianMarkdown(items: NewsItem[]): Promise<string> {
  if (items.length === 0) {
    return "";
  }

  try {
    const result = await formatNewsForObsidian(items.map((item) => item.id));
    return result.markdown;
  } catch {
    return fallbackMarkdown(items);
  }
}

export async function downloadObsidianMarkdown(items: NewsItem[], filename?: string): Promise<void> {
  const markdown = await newsItemsToObsidianMarkdown(items);
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
  const markdown = await newsItemsToObsidianMarkdown(items);
  await navigator.clipboard.writeText(markdown);
}
