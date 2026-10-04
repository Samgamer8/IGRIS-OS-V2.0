"""Ediciones conjuntas: validar todo, respaldar y revertir errores detectados."""
from __future__ import annotations

import os
from uuid import uuid4

from .mission_workspace import digest, safe_relative, save_json


def write_many(files, items):
    if (not isinstance(items, list) or not 1 <= len(items) <= 12
            or any(not isinstance(row, dict) for row in items)):
        raise ValueError('Escribe entre 1 y 12 archivos por lote')
    prepared, names, size = [], set(), 0
    for row in items:
        name = safe_relative(row.get('path', ''))
        if name.casefold() in names or any(
                name.casefold().startswith(p + '/') or p.startswith(name.casefold() + '/') for p in names):
            raise ValueError('Rutas duplicadas o incompatibles en el lote')
        names.add(name.casefold())
        content = row.get('content')
        path, before = files._validate_write(name, content)
        data = content.encode('utf-8')
        size += len(data)
        if size > 200000:
            raise ValueError('El lote supera 200000 bytes')
        if before != data:
            prepared.append((name, path, before, data))
    if not prepared:
        return {'changed': False, 'files': []}
    transaction = files.workspace / 'transactions' / uuid4().hex
    transaction.mkdir(parents=True)
    record = {'state': 'prepared', 'files': [], 'rollback_errors': []}
    for i, (name, path, before, data) in enumerate(prepared):
        staged = transaction / f'{i}.new'
        staged.write_bytes(data)
        if before is not None:
            backup = transaction / f'{i}.before'
            backup.write_bytes(before)
            mode = path.stat().st_mode & 0o777
            os.chmod(staged, mode)
            os.chmod(backup, mode)
        record['files'].append({'path': name, 'before': digest(before) if before is not None else None,
                                'after': digest(data), 'applied': False})
    receipt = transaction / 'transaction.json'
    save_json(receipt, record)
    remembered, applied = dict(files.read_hashes), []
    try:
        for i, (name, path, before, data) in enumerate(prepared):
            files.path(name)
            if (path.read_bytes() if path.is_file() else None) != before:
                raise ValueError('El archivo cambio durante el lote: ' + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(transaction / f'{i}.new', path)
            applied.append(i)
            record['files'][i]['applied'] = True
            save_json(receipt, record)
        record['state'] = 'committed'
        save_json(receipt, record)
    except (OSError, ValueError) as exc:
        for i in reversed(applied):
            name, path, before, data = prepared[i]
            try:
                files.path(name)
                if path.read_bytes() != data:
                    raise ValueError('Cambio externo: se conserva la version actual de ' + name)
                if before is None:
                    path.unlink()
                else:
                    os.replace(transaction / f'{i}.before', path)
                record['files'][i]['applied'] = False
            except (OSError, ValueError) as rollback_error:
                record['rollback_errors'].append(str(rollback_error))
        files.read_hashes = remembered
        record['state'] = 'rollback_incomplete' if record['rollback_errors'] else 'rolled_back'
        try:
            save_json(receipt, record)
        except OSError as log_error:
            record['rollback_errors'].append(str(log_error))
        raise ValueError(f'Lote fallido: {exc}; {record["state"]}; respaldo: {transaction}; '
                         f'errores de recuperacion: {record["rollback_errors"]}') from exc
    for name, _, _, data in prepared:
        files.read_hashes[name] = digest(data)
    return {'changed': True, 'files': [p[0] for p in prepared], 'transaction': str(receipt)}
