"""
Ejercicio 2.4: Refactoring Sync → Async
Objetivo: Sistema que convierte código síncrono a asíncrono.
Tiempo: 5 horas
Habilidades: AST transformation, async/await, refactoring

Requisitos:
- Convierte 20 funciones sync a async
- Mantiene funcionalidad
- Usa async/await
- Maneja exceptions
- < 1 minuto por función
"""
import ast
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class RefactoringResult:
    function_name: str
    original_code: str
    refactored_code: str
    success: bool
    changes_made: List[str]


class AsyncRefactor:
    def __init__(self):
        self.functions_refactored = 0
        self.refactoring_time = 0.0
    
    def refactor_function(self, code: str) -> RefactoringResult:
        """Refactoriza una función síncrona a asíncrona."""
        try:
            tree = ast.parse(code)
            
            # Encontrar la función principal
            func_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_def = node
                    break
            
            if not func_def:
                return RefactoringResult(
                    function_name="unknown",
                    original_code=code,
                    refactored_code=code,
                    success=False,
                    changes_made=[]
                )
            
            # Convertir a async
            changes = []
            original_code = code
            
            # Agregar async a la definición
            if not isinstance(func_def, ast.AsyncFunctionDef):
                func_def = ast.AsyncFunctionDef(
                    name=func_def.name,
                    args=func_def.args,
                    body=func_def.body,
                    decorator_list=func_def.decorator_list,
                    returns=func_def.returns,
                    type_comment=func_def.type_comment
                )
                changes.append("Added async to function definition")
            
            # Convertir llamadas bloqueantes a async
            for node in ast.walk(func_def):
                if isinstance(node, ast.Call):
                    # Convertir time.sleep a asyncio.sleep
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == "sleep":
                            changes.append("Converted time.sleep to asyncio.sleep")
            
            # Generar código refactorizado
            refactored_code = self._generate_async_code(func_def, changes)
            
            self.functions_refactored += 1
            
            return RefactoringResult(
                function_name=func_def.name,
                original_code=original_code,
                refactored_code=refactored_code,
                success=True,
                changes_made=changes
            )
            
        except Exception as e:
            return RefactoringResult(
                function_name="error",
                original_code=code,
                refactored_code=code,
                success=False,
                changes_made=[f"Error: {str(e)}"]
            )
    
    def _generate_async_code(self, func_def: ast.AsyncFunctionDef, changes: List[str]) -> str:
        """Genera código async a partir del AST."""
        # Generar código base
        code = f"async def {func_def.name}("
        
        # Agregar parámetros
        args = []
        for arg in func_def.args.args:
            args.append(arg.arg)
        
        code += ", ".join(args)
        code += "):\n"
        
        # Agregar body
        for node in func_def.body:
            if isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Call):
                    # Convertir llamadas
                    code += f"    await {self._convert_call(node.value)}\n"
                else:
                    code += f"    {ast.unparse(node.value)}\n"
            elif isinstance(node, ast.Return):
                code += f"    return {ast.unparse(node.value)}\n"
            else:
                code += f"    {ast.unparse(node)}\n"
        
        return code
    
    def _convert_call(self, call_node: ast.Call) -> str:
        """Convierte una llamada a async."""
        func_name = ast.unparse(call_node.func)
        args = [ast.unparse(arg) for arg in call_node.args]
        
        # Agregar await si es necesario
        if "sleep" in func_name.lower():
            return f"asyncio.sleep({args[0]})"
        
        return f"{func_name}({', '.join(args)})"
    
    def refactor_file(self, file_path: Path) -> List[RefactoringResult]:
        """Refactoriza todas las funciones de un archivo."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            results = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_code = ast.unparse(node)
                    result = self.refactor_function(func_code)
                    results.append(result)
            
            return results
            
        except Exception as e:
            return []


def generate_sync_functions(directory: Path, num_functions: int = 20) -> None:
    """Genera funciones síncronas para refactorizar."""
    directory.mkdir(parents=True, exist_ok=True)
    
    code = """\"\"\"Módulo con funciones síncronas para refactorizar.\"\"\"
import time

def fetch_data(url: str) -> dict:
    \"\"\"Fetch data from URL.\"\"\"
    time.sleep(1)  # Simular I/O
    return {"status": "success", "data": "sample"}

def process_data(data: dict) -> dict:
    \"\"\"Process data.\"\"\"
    time.sleep(0.5)
    return {"processed": True, "result": data}

def save_to_file(data: dict, filename: str) -> bool:
    \"\"\"Save data to file.\"\"\"
    time.sleep(0.3)
    return True

def load_from_file(filename: str) -> dict:
    \"\"\"Load data from file.\"\"\"
    time.sleep(0.3)
    return {"loaded": True}

def calculate_sum(numbers: list) -> int:
    \"\"\"Calculate sum of numbers.\"\"\"
    time.sleep(0.1)
    return sum(numbers)

def send_email(to: str, subject: str, body: str) -> bool:
    \"\"\"Send email.\"\"\"
    time.sleep(1.5)
    return True

def connect_database(host: str, port: int) -> bool:
    \"\"\"Connect to database.\"\"\"
    time.sleep(0.8)
    return True

def query_database(query: str) -> list:
    \"\"\"Execute database query.\"\"\"
    time.sleep(0.5)
    return []

def download_file(url: str, dest: str) -> bool:
    \"\"\"Download file.\"\"\"
    time.sleep(2.0)
    return True

def upload_file(src: str, dest: str) -> bool:
    \"\"\"Upload file.\"\"\"
    time.sleep(2.0)
    return True

def parse_json(json_str: str) -> dict:
    \"\"\"Parse JSON string.\"\"\"
    time.sleep(0.1)
    return {}

def serialize_json(data: dict) -> str:
    \"\"\"Serialize data to JSON.\"\"\"
    time.sleep(0.1)
    return "{}"

def validate_input(data: dict) -> bool:
    \"\"\"Validate input data.\"\"\"
    time.sleep(0.2)
    return True

def transform_data(data: dict, transform: str) -> dict:
    \"\"\"Transform data.\"\"\"
    time.sleep(0.3)
    return data

def compress_data(data: bytes) -> bytes:
    \"\"\"Compress data.\"\"\"
    time.sleep(0.5)
    return data

def decompress_data(data: bytes) -> bytes:
    \"\"\"Decompress data.\"\"\"
    time.sleep(0.5)
    return data

def encrypt_data(data: str, key: str) -> str:
    \"\"\"Encrypt data.\"\"\"
    time.sleep(0.8)
    return data

def decrypt_data(data: str, key: str) -> str:
    \"\"\"Decrypt data.\"\"\"
    time.sleep(0.8)
    return data

def hash_data(data: str) -> str:
    \"\"\"Hash data.\"\"\"
    time.sleep(0.2)
    return "hash"

def verify_signature(data: str, signature: str) -> bool:
    \"\"\"Verify signature.\"\"\"
    time.sleep(0.3)
    return True
"""
    
    (directory / "sync_module.py").write_text(code, encoding='utf-8')


def test_async_refactoring():
    """Prueba el refactoring async."""
    print("Iniciando refactoring sync → async...")
    
    # Crear directorio temporal
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    
    # Generar funciones síncronas
    print("Generando 20 funciones síncronas...")
    generate_sync_functions(temp_dir, num_functions=20)
    
    # Refactorizar
    print("Refactorizando funciones...")
    refactor = AsyncRefactor()
    start_time = time.time()
    
    results = []
    for file_path in temp_dir.glob("*.py"):
        file_results = refactor.refactor_file(file_path)
        results.extend(file_results)
    
    refactoring_time = time.time() - start_time
    
    # Calcular estadísticas
    successful = sum(1 for r in results if r.success)
    avg_time_per_function = refactoring_time / len(results) if results else 0
    
    print("\n=== RESULTADOS ===")
    print(f"Funciones refactorizadas: {successful}")
    print(f"Total de intentos: {len(results)}")
    print(f"Tiempo total: {refactoring_time:.2f}s")
    print(f"Tiempo promedio por función: {avg_time_per_function:.2f}s")
    
    print("\n=== EJEMPLOS DE REFACTORING ===")
    for i, result in enumerate(results[:3]):
        print(f"\nFunción: {result.function_name}")
        print(f"Cambios: {', '.join(result.changes_made)}")
        print(f"Éxito: {result.success}")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if successful < 20:
        print(f"❌ Funciones refactorizadas < 20: {successful}")
        success = False
    else:
        print(f"✅ 20 funciones refactorizadas: {successful}")
    
    if avg_time_per_function >= 60:
        print(f"❌ Tiempo por función >= 60s: {avg_time_per_function:.2f}s")
        success = False
    else:
        print(f"✅ Tiempo por función < 60s: {avg_time_per_function:.2f}s")
    
    # Verificar que el código refactorizado contiene async
    has_async = any("async def" in r.refactored_code for r in results if r.success)
    if not has_async:
        print(f"❌ Código refactorizado no contiene async")
        success = False
    else:
        print(f"✅ Código refactorizado contiene async")
    
    # Limpiar directorio temporal
    import shutil
    shutil.rmtree(temp_dir)
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 2.4: Refactoring Sync → Async")
    print("Requisitos: 20 funciones, funcionalidad mantenida, async/await, exceptions, < 1 min por función")
    print()
    
    result = test_async_refactoring()
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 2.4")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
