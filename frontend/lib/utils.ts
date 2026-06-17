export interface ParsedReasoning {
  novelty?: number;
  practicality?: number;
  communitySignal?: number;
  explanation: string;
}

export function parseAiReasoning(text: string | null): ParsedReasoning | null {
  if (!text) return null;

  const noveltyMatch = text.match(/Novidade\s+(\d)/i);
  const utilityMatch = text.match(/Utilidade\s+(\d)/i);
  const communityMatch = text.match(/Comunidade\s+(\d)/i);

  const novelty = noveltyMatch ? parseInt(noveltyMatch[1], 10) : undefined;
  const practicality = utilityMatch ? parseInt(utilityMatch[1], 10) : undefined;
  const communitySignal = communityMatch ? parseInt(communityMatch[1], 10) : undefined;

  // Find where the explanation starts
  // Usually after " — " (em dash) or " - " (hyphen) or " – " (en dash)
  const separatorMatch = text.match(/\s*(?:—|–|-)\s*(.*)$/);
  let explanation = text;

  if (separatorMatch && separatorMatch[1].trim()) {
    explanation = separatorMatch[1].trim();
  } else {
    // If no separator was found, check if it contains the dimensions, if so we might need to strip them
    if (text.includes("Novidade") || text.includes("Utilidade") || text.includes("Comunidade")) {
      const cleaned = text
        .replace(/Novidade\s+\d/gi, "")
        .replace(/Utilidade\s+\d/gi, "")
        .replace(/Comunidade\s+\d/gi, "")
        .replace(/·/g, "")
        .replace(/^\s*—|^\s*-|^\s*–/, "")
        .trim();
      if (cleaned) {
        explanation = cleaned;
      }
    }
  }

  return {
    novelty,
    practicality,
    communitySignal,
    explanation,
  };
}
