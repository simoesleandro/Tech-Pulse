"""Formatação de títulos para notas Obsidian (sem dependências de outros módulos)."""

import re

_KEBAB_SLUG_TITLE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def prettify_note_title(title: str) -> str:
    """Converte slugs de repo (awesome-selfhosted) em título legível (Awesome Selfhosted)."""
    stripped = title.strip()
    if not stripped:
        return "Nota"
    if re.search(r"[A-ZÁÉÍÓÚÃÕÂÊÔÀÇ]", stripped[1:]) and " " in stripped:
        return stripped
    if _KEBAB_SLUG_TITLE.match(stripped) or (
        re.search(r"[-_]", stripped) and stripped == stripped.lower()
    ):
        words = re.split(r"[-_]+", stripped)
        return " ".join(word.capitalize() for word in words if word)
    if stripped.islower():
        return stripped.capitalize()
    return stripped


def prettify_github_title(title: str) -> str:
    """Prepara títulos do GitHub no padrão 'Dono - Nome Repo' ou qualquer título contendo /."""
    stripped = title.strip()
    if "/" in stripped:
        parts = stripped.split("/", 1)
        owner = prettify_note_title(parts[0])
        repo = prettify_note_title(parts[1])
        return f"{owner} - {repo}"
    return prettify_note_title(stripped)


def humanize_filename(title: str, max_len: int = 80) -> str:
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("", prettify_github_title(title))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:max_len] or "Nota"

