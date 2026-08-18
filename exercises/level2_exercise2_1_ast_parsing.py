"""
Ejercicio 2.1: AST Parsing y Análisis
Objetivo: Sistema que analiza 100 archivos de código.
Tiempo: 3 horas
Habilidades: AST parsing, static analysis, dependency graph

Requisitos:
- Analiza 100 archivos Python
- Detecta dependencias
- Identifica funciones complejas
- Genera reporte
- < 10 segundos
"""
import ast
import time
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set
from collections import defaultdict
import statistics


@dataclass
class FunctionInfo:
    name: str
    file_path: str
    line_number: int
    complexity: int
    parameters: List[str]
    calls: List[str]
    docstring: str = ""


@dataclass
class FileAnalysis:
    file_path: str
    functions: List[FunctionInfo]
    imports: Set[str]
    classes: List[str]
    lines_of_code: int
    complexity_score: float


class CodeAnalyzer:
    def __init__(self):
        self.files_analyzed: List[FileAnalysis] = []
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.total_functions = 0
        self.complex_functions = 0
        self.analysis_time = 0.0
    
    def analyze_file(self, file_path: Path) -> FileAnalysis:
        """Analiza un archivo Python."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            functions = []
            imports = set()
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = self._analyze_function(node, str(file_path))
                    functions.append(func_info)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
            
            # Calcular complejidad
            complexity_score = self._calculate_complexity(functions)
            
            analysis = FileAnalysis(
                file_path=str(file_path),
                functions=functions,
                imports=imports,
                classes=classes,
                lines_of_code=len(content.splitlines()),
                complexity_score=complexity_score
            )
            
            return analysis
            
        except Exception as e:
            return FileAnalysis(
                file_path=str(file_path),
                functions=[],
                imports=set(),
                classes=[],
                lines_of_code=0,
                complexity_score=0.0
            )
    
    def _analyze_function(self, node: ast.FunctionDef, file_path: str) -> FunctionInfo:
        """Analiza una función."""
        # Calcular complejidad ciclomática
        complexity = 1  # Base complexity
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
        
        # Obtener parámetros
        parameters = [arg.arg for arg in node.args.args]
        
        # Obtener llamadas a funciones
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        
        # Obtener docstring
        docstring = ast.get_docstring(node) or ""
        
        return FunctionInfo(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            complexity=complexity,
            parameters=parameters,
            calls=calls,
            docstring=docstring
        )
    
    def _calculate_complexity(self, functions: List[FunctionInfo]) -> float:
        """Calcula el score de complejidad del archivo."""
        if not functions:
            return 0.0
        
        total_complexity = sum(f.complexity for f in functions)
        avg_complexity = total_complexity / len(functions)
        
        return avg_complexity
    
    def analyze_directory(self, directory: Path) -> Dict:
        """Analiza todos los archivos Python en un directorio."""
        start_time = time.time()
        
        python_files = list(directory.rglob("*.py"))
        
        for file_path in python_files:
            analysis = self.analyze_file(file_path)
            self.files_analyzed.append(analysis)
            
            # Actualizar grafo de dependencias
            for imp in analysis.imports:
                self.dependency_graph[str(file_path)].add(imp)
            
            # Actualizar estadísticas
            self.total_functions += len(analysis.functions)
            self.complex_functions += sum(1 for f in analysis.functions if f.complexity > 10)
        
        self.analysis_time = time.time() - start_time
        
        return self._generate_report()
    
    def _generate_report(self) -> Dict:
        """Genera reporte de análisis."""
        if not self.files_analyzed:
            return {}
        
        total_loc = sum(f.lines_of_code for f in self.files_analyzed)
        avg_complexity = statistics.mean(f.complexity_score for f in self.files_analyzed if f.complexity_score > 0)
        
        # Encontrar funciones más complejas
        all_functions = []
        for analysis in self.files_analyzed:
            all_functions.extend(analysis.functions)
        
        all_functions.sort(key=lambda x: x.complexity, reverse=True)
        top_complex = all_functions[:10]
        
        return {
            "files_analyzed": len(self.files_analyzed),
            "total_functions": self.total_functions,
            "complex_functions": self.complex_functions,
            "total_lines_of_code": total_loc,
            "average_complexity": avg_complexity,
            "analysis_time": self.analysis_time,
            "top_complex_functions": [
                {
                    "name": f.name,
                    "file": f.file_path,
                    "complexity": f.complexity,
                    "line": f.line_number
                }
                for f in top_complex
            ],
            "dependency_graph_size": len(self.dependency_graph)
        }


def generate_test_files(directory: Path, num_files: int = 100) -> None:
    """Genera archivos Python de prueba."""
    directory.mkdir(parents=True, exist_ok=True)
    
    for i in range(num_files):
        file_path = directory / f"test_file_{i}.py"
        
        # Generar código Python aleatorio
        code = f'''"""
Test file {i}
"""
import random
import math
from typing import List

def simple_function(x: int) -> int:
    """Simple function."""
    return x * 2

def complex_function(data: List[int]) -> int:
    """Complex function with multiple branches."""
    result = 0
    for item in data:
        if item > 0:
            if item % 2 == 0:
                result += item
            else:
                result -= item
        elif item < 0:
            for i in range(abs(item)):
                if i % 3 == 0:
                    result += i
        else:
            while result < 100:
                result += 1
    return result

class TestClass:
    """Test class."""
    
    def __init__(self, value: int):
        self.value = value
    
    def process(self) -> int:
        """Process value."""
        if self.value > 10:
            return self.value * 2
        else:
            return self.value + 5

# Execute
if __name__ == "__main__":
    data = [random.randint(-10, 20) for _ in range(100)]
    result = complex_function(data)
    print(f"Result: {{result}}")
'''
        
        file_path.write_text(code, encoding='utf-8')


def test_ast_parsing():
    """Prueba el sistema de AST parsing."""
    print("Iniciando análisis de 100 archivos Python...")
    
    # Crear directorio temporal
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    
    # Generar archivos de prueba
    print("Generando 100 archivos de prueba...")
    generate_test_files(temp_dir, num_files=100)
    
    # Analizar directorio
    print("Analizando archivos...")
    analyzer = CodeAnalyzer()
    report = analyzer.analyze_directory(temp_dir)
    
    print("\n=== RESULTADOS ===")
    print(f"Archivos analizados: {report['files_analyzed']}")
    print(f"Funciones totales: {report['total_functions']}")
    print(f"Funciones complejas: {report['complex_functions']}")
    print(f"Líneas de código: {report['total_lines_of_code']}")
    print(f"Complejidad promedio: {report['average_complexity']:.2f}")
    print(f"Tiempo de análisis: {report['analysis_time']:.2f}s")
    print(f"Tamaño del grafo de dependencias: {report['dependency_graph_size']}")
    
    print("\n=== FUNCIONES MÁS COMPLEJAS ===")
    for func in report['top_complex_functions'][:5]:
        print(f"  {func['name']} (línea {func['line']}) - Complejidad: {func['complexity']}")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if report['files_analyzed'] < 100:
        print(f"❌ Archivos analizados < 100: {report['files_analyzed']}")
        success = False
    else:
        print(f"✅ 100 archivos analizados: {report['files_analyzed']}")
    
    if report['analysis_time'] >= 10:
        print(f"❌ Tiempo de análisis >= 10s: {report['analysis_time']:.2f}s")
        success = False
    else:
        print(f"✅ Tiempo de análisis < 10s: {report['analysis_time']:.2f}s")
    
    if report['total_functions'] == 0:
        print(f"❌ No se detectaron funciones")
        success = False
    else:
        print(f"✅ Funciones detectadas: {report['total_functions']}")
    
    if report['dependency_graph_size'] == 0:
        print(f"❌ No se detectaron dependencias")
        success = False
    else:
        print(f"✅ Dependencias detectadas: {report['dependency_graph_size']}")
    
    # Limpiar directorio temporal
    import shutil
    shutil.rmtree(temp_dir)
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 2.1: AST Parsing y Análisis")
    print("Requisitos: 100 archivos, dependencias, funciones complejas, reporte, < 10s")
    print()
    
    result = test_ast_parsing()
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 2.1")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
