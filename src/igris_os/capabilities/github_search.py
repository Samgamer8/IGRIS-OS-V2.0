"""Busqueda real de repositorios en GitHub mediante la API publica.

Veracidad: los resultados NO los inventa el LLM. Esta funcion consulta la API
de busqueda de GitHub, cuenta cuantos repositorios existen y los ordena por
relevancia (estrellas, proxy transparente y defendible), devolviendo URLs
comprobables. El LLM solo formatea; la fuente de la verdad es la API.

Limite honesto: sin token la API permite 10 peticiones/hora; con la variable
de entorno IGRIS_GITHUB_TOKEN se elevan a 5000/hora.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import unicodedata
from typing import Callable, List, Tuple
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


SEARCH_URL = "https://api.github.com/search/repositories"
USER_AGENT = "IGRIS-Repository-Search/1.0"
PER_PAGE = 30


@dataclass(frozen=True, slots=True)
class RepoHit:
    full_name: str
    stars: int
    url: str
    description: str
    language: str
    license: str


@dataclass(frozen=True, slots=True)
class RepoSearchResult:
    query: str
    total_count: int
    hits: Tuple[RepoHit, ...]
    rate_limited: bool = False
    error: str = ""


def _token() -> str:
    return os.environ.get("IGRIS_GITHUB_TOKEN", "").strip()


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _token()
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _get_json(url: str) -> dict:
    request = Request(url, headers=_headers())
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read(8_000_000).decode("utf-8"))


def _search_once(query: str, top_n: int) -> RepoSearchResult:
    """Una sola consulta a la API. No reintenta; ver search_repositories."""
    url = f"{SEARCH_URL}?q={quote(query)}&sort=stars&order=desc&per_page={PER_PAGE}"
    try:
        data = _get_json(url)
    except HTTPError as exc:
        if exc.code in (403, 429):
            return RepoSearchResult(
                query=query, total_count=0, hits=(), rate_limited=True,
                error="GitHub limito la busqueda (10 peticiones/hora sin token). "
                      "Configura la variable de entorno IGRIS_GITHUB_TOKEN para 5000/hora.")
        return RepoSearchResult(query=query, total_count=0, hits=(),
                                error=f"GitHub devolvio HTTP {exc.code}.")
    except Exception as exc:  # red caida, timeout, DNS...
        return RepoSearchResult(query=query, total_count=0, hits=(),
                                error=f"No se pudo contactar con GitHub: {exc}")
    total = int(data.get("total_count", 0) or 0)
    hits: List[RepoHit] = []
    for item in data.get("items", ())[:top_n]:
        lic = item.get("license") or {}
        license_name = ""
        if isinstance(lic, dict):
            license_name = str(lic.get("spdx_id") or lic.get("key") or "")
        hits.append(RepoHit(
            full_name=str(item.get("full_name", "")),
            stars=int(item.get("stargazers_count", 0) or 0),
            url=str(item.get("html_url", "")),
            description=str(item.get("description") or "").strip(),
            language=str(item.get("language") or ""),
            license=license_name,
        ))
    return RepoSearchResult(query=query, total_count=total, hits=tuple(hits))


def search_repositories(query: str, *, top_n: int = 5) -> RepoSearchResult:
    """Busqueda real con reduccion escalonada honesta.

    1) Intenta con todos los terminos (AND implicito de GitHub).
    2) Si da cero resultados (la frase trajo verbos o una palabra mal escrita
       que GitHub no indexa), recorta la consulta por la derecha --donde suelen
       quedar verbos y conectores-- y reintenta, hasta obtener resultados reales
       o quedarse con un solo termino.

    Usa AND (no OR): OR con muchos terminos da HTTP 422. Nunca inventa: solo
    prueba subconjuntos reales de lo que el usuario escribio.
    """
    query = query.strip()
    if not query:
        return RepoSearchResult(query="", total_count=0, hits=(),
                                error="Consulta vacia.")
    strict = _search_once(query, top_n)
    if strict.total_count > 0 or strict.error:
        return strict
    terms = [t for t in query.split() if t]
    # Recorte escalonado: quitar de a uno desde el final. Maximo 4 reintentos
    # para no agotar la cuota (10 peticiones/hora sin token).
    last = strict
    for cut in range(1, min(len(terms), 5)):
        candidate = " ".join(terms[:len(terms) - cut])
        if not candidate:
            break
        attempt = _search_once(candidate, top_n)
        if attempt.total_count > 0:
            return attempt
        if attempt.error:
            return attempt  # red caida, 422, etc.: no seguir gastando cuota
        last = attempt
    return last


def search_and_open(query: str, *, top_n: int = 5,
                    opener: Callable[[str], bool] | None = None
                    ) -> Tuple[RepoSearchResult, List[str]]:
    """Busca y abre los top_n mas relevantes, cada uno en ventana independiente.

    ``opener`` se inyecta para poder testear sin abrir ventanas reales; por
    defecto usa ``host.open_chrome_window``.
    """
    result = search_repositories(query, top_n=top_n)
    if opener is None:
        opener = _default_opener
    opened: List[str] = []
    for hit in result.hits:
        try:
            if opener(hit.url):
                opened.append(hit.url)
        except Exception:
            continue
    return result, opened


def _default_opener(url: str) -> bool:
    from igris_os.capabilities.host import open_chrome_window
    return bool(open_chrome_window({"url": url}).ok)


def format_report(result: RepoSearchResult, opened: List[str]) -> str:
    """Redacta la respuesta con datos reales: cuantos encontro y el top-N."""
    if result.error:
        return result.error
    if result.total_count == 0 or not result.hits:
        return (f"No encontre repositorios en GitHub para «{result.query}». "
                "Prueba con otras palabras clave.")
    lines = [
        f"Encontre {result.total_count} repositorios en GitHub para «{result.query}». "
        f"Estos son los {len(result.hits)} mas relevantes por estrellas:"
    ]
    for index, hit in enumerate(result.hits, 1):
        license_tag = f" [{hit.license}]" if hit.license else ""
        description = f" — {hit.description}" if hit.description else ""
        lines.append(f"{index}. {hit.full_name} ({hit.stars} estrellas){license_tag}{description}")
        lines.append(f"   {hit.url}")
    if opened:
        lines.append(f"He abierto los {len(opened)} primeros en ventanas independientes de Chrome.")
    else:
        lines.append("No pude abrir las ventanas de Chrome; usa los enlaces de arriba.")
    return "\n".join(lines)


# --- Extraccion de consulta desde lenguaje natural -------------------------

_FILLER = {
    "busca", "buscar", "buscame", "busqueda", "repositorio", "repositorios",
    "repo", "repos", "github", "github.com", "pagina", "paginas", "web",
    "de", "del", "en", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "para", "sobre", "que", "con", "y", "forma", "free", "gratis", "gratuito",
    "gratuita", "puedes", "podrias", "por", "favor", "dame", "muestrame",
    "muestra", "muestrame", "muestras", "mostrarme", "mostrame", "mostrar",
    "enseñame", "enseñar", "dime", "decir", "decirme", "encuentra",
    "encuentrame", "encuentrame", "encontrar", "lista", "listado", "listame",
    "listar", "proyecto", "proyectos", "codigo", "abierto", "abierta",
    "abiertos", "abiertas", "necesito", "quiero", "hay", "existen", "exista",
    "ok", "okay", "ola", "hola", "ey", "eh", "bueno", "buena", "vale",
    "mira", "oye", "ver", "quiero", "gustaria", "quisiera", "podria",
    # Cuantificadores / juicios de valor: no son terminos tecnicos.
    "mas", "menos", "muy", "relevantes", "relevante", "importantes",
    "importante", "principales", "principal", "mejores", "mejor", "buenos",
    "buena", "buenas", "tipo", "tipos", "estilo", "ejemplo", "ejemplos",
    "semejantes", "parecidos", "parecidas", "englovan", "envuelven",
    "engloben", "engloban", "contengan", "tengan", "incluyan", "incluyen",
    "utilicen", "usan", "usen", "relacionados", "relacionadas", "acerca",
}
_ES_EN = {
    "agentes": "agent", "agente": "agent", "multiples": "multi",
    "multiple": "multi", "ia": "AI", "inteligencia": "intelligence",
    "artificial": "artificial", "aprendizaje": "learning",
    "automatico": "automatic", "autonomo": "autonomous", "autonoma": "autonomous",
    "programacion": "programming", "juego": "game", "juegos": "games",
    "voz": "voice", "imagen": "image", "imagenes": "image", "video": "video",
    "marco": "framework", "marcos": "framework", "busqueda": "search",
    "modelos": "model", "modelo": "model", "lenguaje": "language",
    "aplicaciones": "application", "aplicacion": "application",
    "multimedia": "multimedia", "nube": "cloud", "seguridad": "security",
}


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def extract_github_query(text: str) -> str:
    """Convierte una peticion en lenguaje natural en terminos de busqueda.

    Elimina palabras de relleno y traduce terminos tecnicos frecuentes del
    espanol al ingles (la API de GitHub indexa mayoritariamente en ingles).
    No es perfecto, pero devuelve terminos reales que la API puede resolver.
    """
    normalized = _strip_accents(text.lower())
    words = re.findall(r"[a-z0-9][a-z0-9\.\-\+]*", normalized)
    seen = set()
    kept: List[str] = []
    for word in words:
        if word in _FILLER or len(word) < 2:
            continue
        translated = _ES_EN.get(word, word)
        if translated not in seen:
            seen.add(translated)
            kept.append(translated)
    return " ".join(kept)


# Terminos tecnicos fiables que GitHub indexa de forma consistente. Si la
# frase contiene al menos uno, buscamos SOLO con estos (en ingles), ignorando
# el ruido. Es lo unico que garantiza resultados reales con lenguaje natural.
_TECH_TERMS = {
    "agent", "agents", "multiagent", "multi", "ai", "llm", "llms", "nlp",
    "gpt", "transformer", "transformers", "rag", "chatbot", "copilot",
    "framework", "library", "sdk", "api", "cli", "tool", "tooling",
    "application", "applications", "programming", "coding", "code",
    "assistant", "ide", "editor", "extension", "plugin", "language",
    "server", "servers", "language-server", "autonomous", "autonomy",
    "selfhosted", "self-hosted", "openai", "anthropic", "claude", "qwen",
    "llama", "mistral", "ollama", "deepseek", "huggingface", "langchain",
    "crewai", "autogen", "browser", "desktop", "gui", "tui", "automation",
    "workflow", "orchestration", "agentic", "developer", "devtools",
    "video", "audio", "image", "vision", "speech", "voice", "tts", "stt",
    "security", "database", "cloud", "kubernetes", "docker", "python",
    "javascript", "typescript", "rust", "golang", "cpp", "scraper",
    "scraping", "crawler", "rag", "embeddings", "finetuning", "inference",
}


def refine_query(raw_query: str) -> str:
    """Prioriza terminos tecnicos fiables sobre el ruido residual.

    Si hay terminos conocidos, devuelve solo esos (maximo 5, para no ahogar el
    AND). Si no hay ninguno fiable, deja la consulta tal cual para que la
    reduccion escalonada de search_repositories intente resolverla.
    """
    words = raw_query.split()
    known = [w for w in words if w.lower() in _TECH_TERMS]
    if known:
        # Conserva el orden original, sin duplicados, maximo 5 terminos.
        unique = list(dict.fromkeys(known))
        return " ".join(unique[:5])
    return raw_query


def _default_opener(url: str) -> bool:
    from igris_os.capabilities.host import open_chrome_window
    return bool(open_chrome_window({"url": url}).ok)


def format_report(result: RepoSearchResult, opened: List[str]) -> str:
    """Redacta la respuesta con datos reales: cuantos encontro y el top-N."""
    if result.error:
        return result.error
    if result.total_count == 0 or not result.hits:
        return (f"No encontre repositorios en GitHub para «{result.query}». "
                "Prueba con otras palabras clave.")
    lines = [
        f"Encontre {result.total_count} repositorios en GitHub para «{result.query}». "
        f"Estos son los {len(result.hits)} mas relevantes por estrellas:"
    ]
    for index, hit in enumerate(result.hits, 1):
        license_tag = f" [{hit.license}]" if hit.license else ""
        description = f" — {hit.description}" if hit.description else ""
        lines.append(f"{index}. {hit.full_name} ({hit.stars} estrellas){license_tag}{description}")
        lines.append(f"   {hit.url}")
    if opened:
        lines.append(f"He abierto los {len(opened)} primeros en ventanas independientes de Chrome.")
    else:
        lines.append("No pude abrir las ventanas de Chrome; usa los enlaces de arriba.")
    return "\n".join(lines)
