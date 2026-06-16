export type NewsSource = "dev.to" | "reddit" | "github_trends" | string;

export interface SourceTheme {
  label: string;
  shortLabel: string;
  cardClass: string;
  badgeClass: string;
  linkClass: string;
  fieldLabelClass: string;
}

const THEMES: Record<string, SourceTheme> = {
  "dev.to": {
    label: "dev.to",
    shortLabel: "DEV",
    cardClass: "card-source-devto",
    badgeClass: "badge-source-devto",
    linkClass: "link-source-devto",
    fieldLabelClass: "field-label-devto",
  },
  reddit: {
    label: "Reddit",
    shortLabel: "RDDT",
    cardClass: "card-source-reddit",
    badgeClass: "badge-source-reddit",
    linkClass: "link-source-reddit",
    fieldLabelClass: "field-label-reddit",
  },
  github_trends: {
    label: "GitHub",
    shortLabel: "GH",
    cardClass: "card-source-github",
    badgeClass: "badge-source-github",
    linkClass: "link-source-github",
    fieldLabelClass: "field-label-github",
  },
};

const FALLBACK: SourceTheme = {
  label: "Outra fonte",
  shortLabel: "SRC",
  cardClass: "card-source-default",
  badgeClass: "badge-source-default",
  linkClass: "link-source-default",
  fieldLabelClass: "field-label-default",
};

export function getSourceTheme(source: NewsSource): SourceTheme {
  return THEMES[source] ?? { ...FALLBACK, label: source };
}
