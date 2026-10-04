"""Seleccion del verificador sin perder la descripcion tecnica del encargo."""
from __future__ import annotations

import re
import unicodedata


ADAPTERS = {
    'python': r'\b(?:python(?:[23](?:\.\d+)*)?|cpython|py)\b',
    'godot': r'\b(?:godot(?:[34](?:\.\d+)*)?|gdscript)\b',
    'javascript': r'\b(?:javascript|js|node(?:\.js|js)?)(?:\b)',
}
# These runtimes need their own build/verification flow. In particular, a
# Python backend does not make a TypeScript frontend verified by pytest.
OTHER_RUNTIMES = re.compile(
    r'(?<!\w)(?:typescript|tsx|jsx|c\#|c\+\+|csharp|c-sharp|\.net|dotnet|'
    r'rust|ruby|lua|golang|go|java|kotlin|swift|dart|php|powershell|bash|'
    r'electron|deno|bun|react|angular|vue|svelte|unity|unreal)(?!\w)')


def verification_technology(declaration: str) -> str:
    if not isinstance(declaration, str) or not declaration.strip() or len(declaration) > 600:
        raise ValueError('El plan necesita una tecnologia concreta en texto')
    text = unicodedata.normalize('NFKC', declaration).casefold().strip(' \t\r\n`*')
    text = re.sub(r'^(?:lenguaje|tecnologia|runtime|stack)\s*:\s*', '', text)
    detected = {name for name, pattern in ADAPTERS.items() if re.search(pattern, text)}
    primary = {name for name, pattern in ADAPTERS.items() if re.match(pattern, text)}
    if len(detected) == 1 and detected == primary and not OTHER_RUNTIMES.search(text):
        return next(iter(detected))
    raise ValueError('Falta integrar un verificador ejecutable para ' + declaration +
                     '; no se sustituira la tecnologia solicitada')


def python_probe_packages(declaration: str, *, executable=False) -> list[str]:
    """Common named dependencies; the programmer can inspect any other name."""
    packages = ['pytest']
    for name in ('PyInstaller', 'psutil', 'WMI', 'requests', 'PyQt6', 'PySide6',
                 'pywin32', 'numpy', 'Pillow', 'packaging'):
        if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', declaration, re.IGNORECASE):
            packages.append(name)
    if executable and 'PyInstaller' not in packages:
        packages.append('PyInstaller')
    return packages
