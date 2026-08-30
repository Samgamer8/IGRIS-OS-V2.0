# Gestor de tareas

Aplicación CLI completa, sin dependencias externas. Guarda tareas en JSON.

```powershell
python -m task_manager --db tareas.json add "Preparar entrega"
python -m task_manager --db tareas.json list
python -m task_manager --db tareas.json complete 1
```

Validación: `python -m pytest -q`.
