import type { FeedView, NewsItem } from "@/lib/types";

export const FEED_MUTATION_EVENT = "techpulse:feed-mutation";

export function shouldRemoveFromFeedView(item: NewsItem, view: FeedView): boolean {
  if (view === "queue") {
    return (
      item.is_read ||
      item.ai_relevance !== "RELEVANTE" ||
      item.obsidian_exported_at !== null
    );
  }
  if (view === "read") {
    return !item.is_read;
  }
  if (view === "saved") {
    return !item.is_bookmarked;
  }
  if (view === "obsidian") {
    return item.ai_relevance !== "RELEVANTE" || item.obsidian_exported_at === null;
  }
  if (view === "lixo") {
    return item.ai_relevance !== "LIXO";
  }
  return false;
}

export function dispatchFeedMutation(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(FEED_MUTATION_EVENT));
  }
}
