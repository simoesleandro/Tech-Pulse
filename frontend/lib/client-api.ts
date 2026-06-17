function getApiBase(): string {
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl) return envUrl;

    const hostname = window.location.hostname;
    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `http://${hostname}:8000`;
    }
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export const API_BASE = getApiBase();

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const { timeoutMs = 30_000, ...fetchInit } = init ?? {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...fetchInit,
      signal: controller.signal,
    });

    if (!response.ok) {
      let message = `Erro HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (typeof body.detail === "string") {
          message = body.detail;
        } else if (Array.isArray(body.detail)) {
          message = body.detail.map((item: { msg?: string }) => item.msg).join(", ");
        }
      } catch {
        /* ignore parse errors */
      }
      throw new ApiError(message, response.status);
    }

    return response;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        `Tempo esgotado. Verifique se o backend (${API_BASE}) e o Ollama estão ativos.`,
      );
    }
    if (error instanceof TypeError) {
      throw new ApiError(
        `Não foi possível conectar ao backend em ${API_BASE}. Inicie a API e tente novamente.`,
      );
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiJson<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const response = await apiFetch(path, init);
  return response.json() as Promise<T>;
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    await apiFetch("/api/health", { timeoutMs: 5_000 });
    return true;
  } catch {
    return false;
  }
}
