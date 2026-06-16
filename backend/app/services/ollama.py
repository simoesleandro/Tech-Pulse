import os

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

SYSTEM_PROMPT = (
    "Você é um classificador de conteúdo técnico de elite para engenheiros de software. "
    "Sua resposta deve conter estritamente uma única palavra em maiúsculo."
)

USER_PROMPT_TEMPLATE = (
    "Analise o título do artigo: '{title}'. "
    "Responda exclusivamente com 'RELEVANTE' se o assunto abordar Engenharia de Software, "
    "IA, Python, DevOps ou Bancos de Dados. "
    "Responda 'LIXO' se for clickbait comercial, vagas de emprego, memes ou notícias corporativas. "
    "Resposta:"
)


def classify_title(title: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": USER_PROMPT_TEMPLATE.format(title=title),
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    raw = response.json().get("response", "").strip().upper()
    if "RELEVANTE" in raw:
        return "RELEVANTE"
    return "LIXO"
