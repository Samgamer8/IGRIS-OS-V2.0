"""Destino y formato solicitados por el usuario, independientes del plan LLM."""
from __future__ import annotations

import os
from pathlib import Path
import re

from .mission_router import _normalize_intent
from igris_os.programming.mission_workspace import safe_relative


def _windows_desktop():
    import ctypes
    from uuid import UUID
    folder_id = (ctypes.c_ubyte * 16).from_buffer_copy(
        UUID('B4BFCC3A-DB2C-424C-B029-7FE99A87C641').bytes_le)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p()
    try:
        if shell.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(pointer)) == 0:
            return Path(ctypes.wstring_at(pointer))
    finally:
        if pointer:
            ole.CoTaskMemFree(pointer)
    return None


def desktop_directory():
    if os.name == 'nt':
        try:
            desktop = _windows_desktop()
            if desktop and desktop.is_dir():
                return desktop.resolve()
        except (OSError, AttributeError):
            pass
    candidates = []
    for variable in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        value = os.environ.get(variable)
        if value:
            candidates += [Path(value) / 'Escritorio', Path(value) / 'Desktop']
    candidates += [Path.home() / 'Desktop', Path.home() / 'Escritorio']
    return next((p.resolve() for p in candidates if p.is_dir()), None)


def _executable_requested(objective):
    target = r'(?:ejecutable|exe)\b'
    article = r'(?:(?:el|un|ningun)\s+)?'
    verbs = r'(?:quiero|necesito|necesita|requiere|requiero|hace falta|generes|crees|compiles|incluyas)'
    for clause in re.split(r'[.!?;](?:\s|$)|\n|\b(?:pero|sin embargo)\b', objective, flags=re.I):
        text = _normalize_intent(clause)
        if not re.search(r'\b' + target, text):
            continue
        negated = (re.search(r'\bsin\s+' + article + target, text)
            or re.search(r'\bno\s+' + verbs + r'\s+(?:a\s+)?' + article + target, text)
            or re.search(r'\bno\s+' + verbs + r'\b.{0,140}\bni\s+' + article + target, text))
        if not negated:
            return True
    return False


def requested_delivery(objective):
    normalized = _normalize_intent(objective)
    desktop = 'escritorio' in normalized.split()
    executable = _executable_requested(objective)
    match = re.search(r'\b(?:nombre(?:\s+de)?|llamad[oa])\s*[,;:\-]*\s*(.+)', objective, re.I)
    name = ''
    if match:
        tail = match[1].strip()
        quoted = re.match(r'["“]([^"”]+)["”]', tail)
        name = quoted[1] if quoted else re.split(
            r'[.!?;](?:\s|$)|\s+(?:en (?:la|el)|para (?:la|el)|y (?:el|la|que)|ahi\b|ahí\b)|[\r\n]',
            tail, maxsplit=1, flags=re.I)[0]
        name = name.strip(' .,;:!?"')
        if name.lower().endswith('.exe'):
            name = name[:-4]
        if not name or len(name) > 80 or '/' in name or '\\' in name:
            name = ''
        else:
            try:
                safe_relative(name)
            except ValueError:
                name = ''
    if not (desktop or executable or name):
        return {}
    contract = {'name': name, 'location': 'desktop' if desktop else '',
                'requires_executable': executable, 'executable_name': name + '.exe' if name and executable else ''}
    if desktop and name:
        parent = desktop_directory()
        contract['destination'] = str(parent / name) if parent else ''
    return contract
