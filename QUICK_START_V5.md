╔════════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║                  🚀 MIGRACIÓN A IGRIS OS V 5 - GUÍA PARA SAM                  ║
║                                                                                ║
║                          Empieza por AQUÍ                                     ║
║                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════╝


👋 RESUMEN EJECUTIVO
════════════════════════════════════════════════════════════════════════════════

Sam ha confirmado que a partir de AHORA:

1. ✅ Toda nueva codificación de IGRIS va a: IGRIS OS V 5
2. ✅ Se cogió lo necesario de carpetas viejas
3. ✅ Se REVISARÁ, TESTEARÁ y VERIFICARÁ integridad
4. ✅ Lo que NO sea viable: → PAPELERA (delete)

Este documento es tu GUÍA de acción paso a paso.


📋 ARCHIVOS DE REFERENCIA (Lee en orden)
════════════════════════════════════════════════════════════════════════════════

1. 📄 MIGRATION_MASTER_PLAN.md
   └─ Plan maestro: fases, timeline, criterios, objetivos
   └─ LECTURA: 10 min

2. 📄 AUDIT_DETAILED_MODULES.md ← EMPEZA AQUÍ AHORA
   └─ Clasificación detallada de 22 módulos
   └─ Qué copiar, qué revisar, qué eliminar
   └─ LECTURA: 10 min

3. 🎯 Este archivo (QUICK_START_V5.md)
   └─ Guía ejecutiva paso a paso
   └─ LECTURA: 5 min


🎯 ACCIÓN INMEDIATA: FASE 1 - COPIAR CORE
════════════════════════════════════════════════════════════════════════════════

Estos 5 módulos son 100% VERIFICADOS. Deben copiarse AHORA a IGRIS OS V 5:

PASO 1: Abre PowerShell
────────────────────────────────────────────────────────────────────────────────
```powershell
cd "C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0\src\igris_os"
```

PASO 2: Copia módulos CORE verificados
────────────────────────────────────────────────────────────────────────────────
```powershell
# COPIAR ESTOS 5 MÓDULOS:
Copy-Item "core" -Destination "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src\igris_os\" -Recurse -Force
Copy-Item "ai" -Destination "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src\igris_os\" -Recurse -Force
Copy-Item "application" -Destination "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src\igris_os\" -Recurse -Force
Copy-Item "security" -Destination "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src\igris_os\" -Recurse -Force
Copy-Item "memory" -Destination "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src\igris_os\" -Recurse -Force
```

PASO 3: Verifica copia
────────────────────────────────────────────────────────────────────────────────
```powershell
# Verifica que están en V 5
ls "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src\igris_os\" -Name
# Deberías ver: ai, application, core, memory, security
```

✅ LISTO - CORE copiado a V 5


⚠️  ACCIÓN FASE 2: REVISAR MÓDULOS GRANDES
════════════════════════════════════════════════════════════════════════════════

Estos 2 módulos son MÁS GRANDES y requieren revisión antes de copiar:

1️⃣  programming/ (617.7 KB, 19 archivos) - PROGRAMACIÓN
   Tamaño: GRANDE
   Acción REQUERIDA: CODE REVIEW + VERIFICAR IMPORTS
   
   Pasos:
   [ ] Abre: C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0\src\igris_os\programming\
   [ ] Lee archivos principales (*.py)
   [ ] Busca: import circular, experimental, roto
   [ ] Ejecuta: pytest tests/test_programming*.py -v
   [ ] Decide: ¿COPIAR o ELIMINAR?
   
   Si TODO OK → Copiar

2️⃣  ui/ (512.1 KB, 13 archivos) - INTERFAZ GRÁFICA
   Tamaño: GRANDE
   Acción REQUERIDA: REVISAR DEPS (PyQt6)
   
   Pasos:
   [ ] Abre: C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0\src\igris_os\ui\
   [ ] Lee archivos principales
   [ ] Verifica: ¿Está PyQt6 en requirements?
   [ ] Ejecuta: pytest tests/test_ui*.py -v
   [ ] Decide: ¿COPIAR o ELIMINAR?
   
   Si TODO OK → Copiar


📋 ACCIÓN FASE 3: REVISAR OTROS MÓDULOS
════════════════════════════════════════════════════════════════════════════════

Para CADA módulo en esta lista, hacer:

```
CHECKLIST RÁPIDO POR MÓDULO:

[ ] 1. ¿Código legible y documentado?
[ ] 2. ¿Imports validos? (No circular)
[ ] 3. ¿Tiene tests asociados?
[ ] 4. ¿Tests pasan?
[ ] 5. ¿Sin código deprecated?

Si TODOS ✓ → COPIAR
Si ALGUNO ✗ → REVISAR CUIDADOSAMENTE o ELIMINAR
```

Módulos a revisar (en orden de prioridad):

  ALTA:       [ ] capabilities/       [ ] tools/
  MEDIA:      [ ] evaluation/         [ ] multimedia/
  MEDIA:      [ ] games/              [ ] delegation/
  MEDIA:      [ ] voice/              [ ] files/
  MEDIA:      [ ] retrieval/          [ ] storage/
  BAJA:       [ ] evolution/          [ ] multi_agent/
  BAJA:       [ ] domain/             [ ] utils/
  ESPECIAL:   [ ] samadmin/           (Investigar contenido)


❌ ACCIÓN FASE 4: ELIMINAR A PAPELERA
════════════════════════════════════════════════════════════════════════════════

ESTOS se eliminan sin dudarlo:

```powershell
# 1. Eliminar __pycache__ (compilados)
Remove-Item "C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0\src\igris_os\__pycache__" -Recurse -Force

# 2. Después de decisiones, eliminar lo que NO pase auditoria:
# [según lo que decidas en Fases 2 y 3]
```


✅ ACCIÓN FASE 5: VERIFICAR EN V 5
════════════════════════════════════════════════════════════════════════════════

DESPUÉS de copiar todos los módulos verificados:

```powershell
cd "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5"

# 1. Ejecutar tests
pytest tests/ -v --tb=short

# 2. Validar cobertura
pytest --cov=src --cov-report=term-missing

# 3. Verificar baseline
python tools/quality_gate.py

# 4. Resultado esperado:
#   ✓ 488/488 tests passing (100%)
#   ✓ Coverage ≥55% (preferible ≥60%)
#   ✓ 0 vulnerabilities
#   ✓ 0 circular imports
```

Si TODO ✓ → V 5 está LISTO para producción
Si ALGUNO ✗ → Investigar y corregir


🗑️  ACCIÓN FASE 6: LIMPIAR CARPETAS ANTIGUAS
════════════════════════════════════════════════════════════════════════════════

CUANDO V 5 ESTÉ VERIFICADO:

```powershell
# 1. Backup de git (por si acaso)
cd "C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0"
git log --oneline | head -20  # Guardar hash para referencia

# 2. Eliminar carpetas viejas (PAPELERA, NO DELETE permanente)
Remove-Item "C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0" -Recurse -Force
Remove-Item "C:\Users\samva\OneDrive\Escritorio\IGRIS OS v4.0.worktrees" -Recurse -Force

# 3. Considera: IGRIS_Archivo (2.1 GB)
#    [ ] Mantener para referencia histórica
#    [ ] Eliminar si no es necesario
```


📊 CHECKLIST FINAL
════════════════════════════════════════════════════════════════════════════════

Marcar con [X] según completes:

CORE (Fase 1):
  [X] core/ copiado
  [X] ai/ copiado
  [X] application/ copiado
  [X] security/ copiado
  [X] memory/ copiado

GRANDES (Fase 2):
  [ ] programming/ revisado y (copiado/eliminado)
  [ ] ui/ revisado y (copiado/eliminado)

OTROS (Fase 3):
  [ ] Todos otros módulos revisados
  [ ] Decisiones documentadas

LIMPIAR (Fase 4):
  [ ] __pycache__ eliminado
  [ ] Código roto eliminado

VERIFICAR (Fase 5):
  [ ] Tests 488/488 pasando
  [ ] Coverage ≥55%
  [ ] Quality gates OK

FINALIZAR (Fase 6):
  [ ] Carpetas antiguas a papelera
  [ ] Git history preservado
  [ ] V 5 es fuente de verdad


💡 CONSEJOS PRÁCTICOS
════════════════════════════════════════════════════════════════════════════════

1. ⚠️  NO BORRAR NADA HASTA ESTAR 100% SEGURO
   → Usa Papelera de Reciclaje (No delete permanente)
   → Puedes recuperar si cometiste error

2. 📝 DOCUMENTA CADA DECISIÓN
   → ¿Por qué copiaste este módulo?
   → ¿Por qué eliminaste ese?
   → Actualiza AUDIT_DETAILED_MODULES.md

3. 🧪 EJECUTA TESTS DESPUÉS DE CADA COPIA GRANDE
   → Verifica que nada se rompió
   → Identifica problemas rápido

4. 💾 GIT COMMIT CON FRECUENCIA
   → Después de cada fase
   → Mensajes descriptivos

5. ✅ VERIFICA ANTES DE LIMPIAR
   → Asegúrate que V 5 funciona
   → Confirma tests pasan
   → DESPUÉS borra carpetas viejas


🚨 PROBLEMAS COMUNES & SOLUCIONES
════════════════════════════════════════════════════════════════════════════════

Problema: "El código importa de carpeta vieja"
Solución: Actualizar imports antes de copiar
  find "C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5\src" -name "*.py" -type f
  Buscar: from ..v4 import (cambiar a importes locales)

Problema: "Tests fallan después de copiar"
Solución: Revisar conftest.py y paths
  pytest tests/ -v --tb=long (para ver detalles)

Problema: "Circular imports detectados"
Solución: Refactorizar imports o separar módulos
  python -m py_compile src/igris_os/module.py (verificar syntax)

Problema: "Dependencias faltantes (PyQt6, FFmpeg)"
Solución: Verificar requirements.txt y dockerfile
  pip install -r requirements.txt


📞 PRÓXIMOS PASOS
════════════════════════════════════════════════════════════════════════════════

1. ✅ Lee AUDIT_DETAILED_MODULES.md (ahora)
2. ⏳ Ejecuta FASE 1 (copiar CORE - 5 módulos)
3. ⏳ Ejecuta FASE 2 (revisar programming/, ui/)
4. ⏳ Ejecuta FASE 3 (revisar otros módulos)
5. ⏳ Ejecuta FASE 4 (eliminar a papelera)
6. ⏳ Ejecuta FASE 5 (verificar en V 5)
7. ⏳ Ejecuta FASE 6 (limpiar carpetas viejas)
8. ⏳ Commit final en git

Tiempo estimado: 7-13 horas (según revisión)

════════════════════════════════════════════════════════════════════════════════

Versión: 1.0
Fecha: 2026-08-30 10:25 UTC
Status: 🟢 LISTO PARA ACCIÓN

Próximo: Lee AUDIT_DETAILED_MODULES.md y comienza FASE 1

════════════════════════════════════════════════════════════════════════════════
