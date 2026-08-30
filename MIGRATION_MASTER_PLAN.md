# 🚀 IGRIS OS V 5 — PLAN MAESTRO DE MIGRACIÓN Y LIMPIEZA

**Fecha:** 2026-08-30  
**Versión:** 1.0  
**Estado:** 🟡 EN PROGRESO  
**Objetivo:** Consolidar IGRIS en carpeta V 5 definitiva, verificando integridad, eliminando incompatibilidades

---

## 📋 RESUMEN EJECUTIVO

| Aspecto | Detalle |
|---------|---------|
| **Carpeta destino** | `C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5` |
| **Carpetas fuente** | `IGRIS OS v4.0`, `IGRIS OS v4.0.worktrees`, `IGRIS_Archivo` |
| **Tamaño fuente total** | ~2.4 GB |
| **Alcance** | Auditoría, verificación, migración selectiva, limpieza |
| **Criterio de inclusión** | ✅ Código core, tests, docs verificadas + sin incompatibilidades |
| **Criterio de exclusión** | ❌ Código experimental rotos, redundante, incompatible → PAPELERA |

---

## 🔍 FASE 1: DISCOVERY & AUDIT (HOY)

### 1.1 Carpetas Identificadas

```
C:\Users\samva\OneDrive\Escritorio\
├── IGRIS OS v4.0 (276.4 MB)                 ← PRINCIPAL
│   ├── src/                                  ← Código core + experimental
│   ├── tests/                                ← Suite de tests
│   ├── docs/                                 ← Documentación
│   ├── tools/                                ← Herramientas
│   └── [otros archivos]
│
├── IGRIS OS v4.0.worktrees (26.5 MB)        ← RAMA DE DESARROLLO
│   └── [contenido a revisar]
│
├── IGRIS_Archivo (2108 MB)                  ← ARCHIVO HISTÓRICO
│   └── [código antiguo/legacy - revisar selectivamente]
│
└── IGRIS OS V 5 (16.1 MB - NUEVA)           ← DESTINO DEFINITIVO
    └── [estructura en construcción]
```

### 1.2 Tareas de Auditoría (Asignadas a SQL)

- [ ] **T1:** Listar TODOS los módulos en `src/`
- [ ] **T2:** Clasificar: Core (necesario) vs Experimental (revisar)
- [ ] **T3:** Verificar integridad de imports (circular dependencies)
- [ ] **T4:** Ejecutar tests y validar cobertura
- [ ] **T5:** Revisar documentación (completitud, validez)
- [ ] **T6:** Identificar código redundante/muerto
- [ ] **T7:** Verificar compatibilidad de versiones (Python, deps)

---

## 📦 FASE 2: CATEGORIZACIÓN

### 2.1 Módulos CORE (A COPIAR A V5)

```
✅ INCLUIR EN V 5:
src/
├── igris_os/
│   ├── core/               ← Motor central OODA
│   ├── backend/            ← API + endpoints
│   ├── frontend/           ← UI components
│   ├── tools/              ← Herramientas verificadas
│   └── contracts/          ← Interfaces y tipos
│
tests/
├── test_core_*.py          ← Tests core
├── test_backend_*.py       ← Tests backend
└── conftest.py            ← Configuración de tests
│
docs/
├── README.md              ← Documentación principal
├── ARCHITECTURE.md        ← Arquitectura
├── API.md                 ← Especificación API
└── DEPLOYMENT.md          ← Despliegue
```

### 2.2 Módulos EXPERIMENTAL (REVISAR/ELIMINAR)

```
⚠️  REVISAR & DECIDIR:
src/
├── experimental/          ← Code review antes de incluir
├── legacy/               ← Deprecated - NO incluir
├── prototypes/           ← POC - analizar viabilidad
└── [módulos sin tests]   ← Verificar o eliminar
```

### 2.3 Criterios de Exclusión (→ PAPELERA)

```
❌ ELIMINAR COMPLETAMENTE:
• Código sin tests asociados (non-coverage)
• Módulos con imports circulares
• Código incompatible con Python 3.9+
• Dependencias missing/deprecated
• Documentación inconsistente
• Archivos temporales (.tmp, .cache, __pycache__)
• Archivos de build innecesarios
• Código muerto (unused imports, dead branches)
```

---

## 🔧 FASE 3: MIGRACIÓN VERIFICADA

### 3.1 Estructura Base IGRIS OS V 5

```
IGRIS OS V 5/
├── src/
│   └── igris_os/           ← CÓDIGO CORE VERIFICADO
│
├── tests/                  ← TESTS VERIFICADOS
│
├── docs/                   ← DOCUMENTACIÓN
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── MIGRATION_PLAN.md   ← Este archivo
│
├── tools/
│   └── quality_gate.py     ← Verificación de calidad
│
├── .gitignore
├── pyproject.toml         ← Config Python
├── conftest.py            ← Config tests
└── README.md              ← Punto de entrada
```

### 3.2 Checklist de Migración

```
PARA CADA MÓDULO A COPIAR:
[ ] 1. Leer código (review de arquitectura)
[ ] 2. Verificar imports (no circular deps)
[ ] 3. Ejecutar tests asociados
[ ] 4. Validar cobertura (≥55%)
[ ] 5. Revisar documentación (comentarios inline)
[ ] 6. Confirmar compatibilidad (Python 3.9+, deps)
[ ] 7. Copiar a V 5 si TODOS pasan
[ ] 8. Re-ejecutar tests en V 5
```

---

## ✅ FASE 4: VERIFICACIÓN EN V 5

### 4.1 Suite de Verificación

```bash
# Debe ejecutarse en IGRIS OS V 5 después de migración

# 1. Tests base
pytest tests/ -v --tb=short

# 2. Quality gate
python tools/quality_gate.py

# 3. Cobertura
pytest --cov=src --cov-report=term-missing

# 4. Linting (si aplica)
flake8 src/ tests/

# 5. Type checking
mypy src/ --ignore-missing-imports
```

### 4.2 Criterios de Aceptación

```
✅ PASAR antes de considerar migración completa:
• 488/488 tests passing (100%)
• Coverage ≥55% (preferible ≥60%)
• 0 security vulnerabilities
• 0 circular imports
• Documentación completa (README + API)
• Git historia limpia
```

---

## 🗑️ FASE 5: LIMPIEZA Y ELIMINACIÓN

### 5.1 Archivos/Carpetas a Eliminar

```
PAPELERA (delete, no archive):
❌ IGRIS OS v4.0/
   ├── experimental/      (no verificado)
   ├── .pytest_tmp/       (temporales)
   ├── __pycache__/       (compilados)
   └── [código roto]

❌ IGRIS OS v4.0.worktrees/
   └── (rama experimental - consolidar a V 5 primero)

❌ IGRIS_Archivo/
   └── (revisar selectivamente, después ELIMINAR)
```

### 5.2 Archivos a Preservar (Archive solo si necesario)

```
OPCIONAL - ARCHIVE EN GITHUB:
✓ Documentación histórica (docs/HISTORY/)
✓ Logs de auditoría completos
✓ Referencia de migraciones anteriores
  (pero NO en working directory principal)
```

---

## 📊 TIMELINE ESTIMADO

| Fase | Tareas | Tiempo | Status |
|------|--------|--------|--------|
| **DISCOVERY** | T1-T7 auditoría | 2-4 horas | 🟡 EN PROGRESO |
| **CATEGORIZACIÓN** | Clasificar módulos | 1-2 horas | ⏳ Pendiente |
| **MIGRACIÓN** | Copiar + verificar | 2-4 horas | ⏳ Pendiente |
| **VERIFICACIÓN** | Tests en V 5 | 1-2 horas | ⏳ Pendiente |
| **LIMPIEZA** | Delete carpetas viejas | 30 min | ⏳ Pendiente |
| **FINALIZATION** | Git commit + docs | 1 hora | ⏳ Pendiente |
| **TOTAL** | | **7-13 horas** | 🟡 |

---

## 🎯 OBJETIVOS FINALES

✅ **IGRIS OS V 5 será:**
- ✓ Fuente de verdad única para IGRIS
- ✓ 100% verificado y testeado
- ✓ Sin código redundante/muerto/roto
- ✓ Documentación completa
- ✓ Listo para producción inmediata
- ✓ Facilita futuros desarrollos (V 5.1+)

❌ **SERÁ ELIMINADO (papelera):**
- ✗ Código experimental no verificado
- ✗ Dependencias incompatibles
- ✗ Módulos sin tests
- ✗ Código duplicado/redundante
- ✗ Documentación desactualizada
- ✗ Archivos temporales/compilados

---

## 📞 PRÓXIMOS PASOS (ORDEN)

1. ✅ **Este documento:** Crear plan maestro → HECHO
2. ⏳ **Fase 1:** Ejecutar auditoría completa (T1-T7)
3. ⏳ **Fase 2:** Categorizar módulos (Core vs Experimental)
4. ⏳ **Fase 3:** Migración selectiva verificada
5. ⏳ **Fase 4:** Ejecutar suite completa en V 5
6. ⏳ **Fase 5:** Limpiar/eliminar carpetas viejas
7. ⏳ **Fase 6:** Commit final + actualizar docs

---

## 📝 NOTAS IMPORTANTES

```
🚨 CRITICAL:
- NO borrar nada sin verificar primero
- Mantener backup de cambios en git
- Documentar CADA decisión de exclusión
- Verificar tests después de CADA migración

⚠️  WARNING:
- IGRIS_Archivo tiene 2GB - revisar antes de eliminar
- Revisar experimental/ antes de descartar
- Validar que no hay código critical en carpetas antiguas
```

---

**Versión:** 1.0  
**Última actualización:** 2026-08-30 10:15 UTC  
**Responsable:** IA Copilot (bajo supervisión de Sam)  
**Status:** 🟡 PLAN CREADO - ESPERANDO AUTORIZACIÓN PARA FASE 1
