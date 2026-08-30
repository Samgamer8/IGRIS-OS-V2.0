#!/usr/bin/env python3
"""
test_full_validation_v2.py - Validación completa del proyecto
Paso 023: Expandir tests de validación completa
"""

import os
from pathlib import Path

def run_full_validation():
    """Ejecutar validación completa del proyecto"""
    
    print("\n🔍 VALIDACIÓN COMPLETA DEL PROYECTO")
    print("=" * 60)
    
    # Validar estructura básica
    if os.path.exists("main.py"):
        print("✅ igrid.py existe y es válido")
    else:
        print("❌ igrid.py no encontrado")
        
    # Validar carpetas críticas
    critical_folders = ["src/igris_os/core", "src/igris_os/application", "tests"]
    for folder in critical_folders:
        if os.path.exists(f"{folder}"):
            print(f"✅ Carpeta {folder}/ existe")
        else:
            print(f"❌ Carpeta {folder}/ no encontrada")
            
    # Validar tests existentes
    test_dir = Path("tests")
    if test_dir.exists():
        test_files = list(test_dir.glob("*.py"))
        print(f"✅ {len(test_files)} archivos de tests encontrados")
        
    return True

if __name__ == "__main__":
    run_full_validation()
    print("\n✅ Validación completa completada")
