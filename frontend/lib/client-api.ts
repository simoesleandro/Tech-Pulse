function getApiBase(): string {
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    const hostname = window.location.hostname;

    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
      if (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1")) {
        return `http://${hostname}:8000`;
      }
    }

    if (envUrl) return envUrl;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export const API_BASE = getApiBase();

const MUTATING_METHODS = new Set(["POST", "PATCH", "PUT", "DELETE"]);

function getApiKey(): string | undefined {
  const key = process.env.NEXT_PUBLIC_TECHPULSE_API_KEY?.trim();
  return key || undefined;
}

function withApiKeyHeaders(init?: RequestInit): RequestInit {
  const method = (init?.method ?? "GET").toUpperCase();
  const apiKey = getApiKey();
  if (!apiKey || !MUTATING_METHODS.has(method)) {
    return init ?? {};
  }

  const headers = new Headers(init?.headers);
  if (!headers.has("X-API-Key")) {
    headers.set("X-API-Key", apiKey);
  }
  return { ...init, headers };
}

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
  const { timeoutMs = 30_000, signal, ...fetchInit } = init ?? {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  if (signal) {
    signal.addEventListener("abort", () => {
      controller.abort();
    });
    if (signal.aborted) {
      controller.abort();
    }
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, withApiKeyHeaders({
      ...fetchInit,
      signal: controller.signal,
    }));

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
