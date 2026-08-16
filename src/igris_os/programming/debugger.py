import ast
import json
import re
import textwrap
from typing import Any

from igris_os.ai import OllamaClient, ModelReply


class AutoDebugger:
    def __init__(self, client: OllamaClient | None = None, model: str = 'llama3') -> None:
        self.client = client or OllamaClient()
        self.model = model

    def diagnose(self, code: str, error: str, language: str = 'python') -> dict[str, Any]:
        prompt = textwrap.dedent(f'''
            Analyze the following {language} code and error. Return ONLY valid JSON with keys:
            fix (str), explanation (str), confidence (float 0-1).
            Code:
            {code[:3000]}
            Error:
            {error}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok:
            try:
                result = self._parse_json(reply.text[:4000])
                result.setdefault('fix', '')
                result.setdefault('explanation', '')
                result.setdefault('confidence', 0.0)
                return result
            except Exception:
                pass
        return self._heuristic_diagnose(code, error, language)

    def auto_fix(self, code: str, error: str, language: str = 'python') -> str:
        prompt = textwrap.dedent(f'''
            Fix the following {language} code based on the error. Return ONLY the corrected code, no explanations.
            Code:
            {code[:3000]}
            Error:
            {error}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok and reply.text.strip():
            return self._extract_code(reply.text[:4000], language)
        return self._heuristic_auto_fix(code, error, language)

    def generate_tests(self, code: str, language: str = 'python', framework: str = 'pytest') -> str:
        targets = self._extract_targets(code, language)
        targets_text = chr(10).join(targets) if targets else '- module-level logic'
        prompt = textwrap.dedent(f'''
            Generate comprehensive unit tests using {framework} for the following {language} code.
            Cover these targets:
            {targets_text}
            Code:
            {code[:3000]}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok:
            return reply.text[:4000]
        return self._heuristic_tests(code, language, framework, targets)

    def profile(self, code: str, language: str = 'python') -> dict[str, Any]:
        if language == 'python':
            return self._heuristic_profile(code, language)
        prompt = textwrap.dedent(f'''
            Perform static analysis on the following {language} code.
            Return ONLY valid JSON with keys:
            complexity (int), issues (list of str), suggestions (list of str).
            Code:
            {code[:3000]}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok:
            try:
                result = self._parse_json(reply.text[:4000])
                result.setdefault('complexity', 1)
                result.setdefault('issues', [])
                result.setdefault('suggestions', [])
                return result
            except Exception:
                pass
        return self._heuristic_profile(code, language)

    def _extract_targets(self, code: str, language: str) -> list[str]:
        if language == 'python':
            try:
                tree = ast.parse(code)
                return [f'- {node.name}' for node in ast.walk(tree)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            except SyntaxError:
                return []
        patterns = {
            'javascript': r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\())',
            'gdscript': r'(?:func\s+(\w+)|class\s+(\w+)\s+extends)',
        }
        pattern = patterns.get(language, r'(?:function|def|class)\s+(\w+)')
        matches = re.findall(pattern, code)
        return [f'- {name}' for group in matches for name in group if name][:10]

    def _parse_json(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith(('```json', '```')):
            text = chr(10).join(text.split(chr(10))[1:])
        if text.endswith('```'):
            text = chr(10).join(text.split(chr(10))[:-1])
        return json.loads(text)

    def _extract_code(self, text: str, language: str) -> str:
        match = re.search(r'```(?:\w+)?' + chr(10) + r'(.*?)```', text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    def _heuristic_diagnose(self, code: str, error: str, language: str) -> dict[str, Any]:
        lang_errors = {
            'python': {'NameError': 'Variable not defined.', 'TypeError': 'Type mismatch.',
                       'IndentationError': 'Indentation issue.', 'SyntaxError': 'Syntax error.'},
            'javascript': {'ReferenceError': 'Variable not defined.', 'TypeError': 'Type mismatch.',
                           'SyntaxError': 'Syntax error.'},
            'gdscript': {'Identifier': 'Invalid identifier.', 'Syntax': 'Syntax error.'},
        }
        explanation = 'Heuristic analysis: '
        for err_type, msg in lang_errors.get(language, {}).items():
            if err_type in error:
                explanation += msg
                break
        else:
            explanation += 'General error detected.'
        return {'fix': '', 'explanation': explanation, 'confidence': 0.4}

    def _heuristic_auto_fix(self, code: str, error: str, language: str) -> str:
        fixes = {
            'python': [(r'print\s+\w+', 'print(...)'), (r'==\s*None', 'is None')],
            'javascript': [(r'==\s*null', '=== null'), (r'var\s+', 'let ')],
            'gdscript': [(r'=\s*null', '= null')],
        }
        for pattern, replacement in fixes.get(language, []):
            code = re.sub(pattern, replacement, code)
        return code

    def _heuristic_tests(self, code: str, language: str, framework: str, targets: list[str]) -> str:
        headers = {
            'python': ('pytest', 'import pytest' + chr(10) * 2),
            'javascript': ('jest', "const { test, expect } = require('jest');" + chr(10) * 2),
            'gdscript': ('gdunit', 'extends GdUnitTestSuite' + chr(10) * 2),
        }
        fw, header = headers.get(language, ('pytest', 'import pytest' + chr(10) * 2))
        if framework != fw and framework:
            header = f'# Framework: {framework}' + chr(10)
        body = chr(10).join(f'def test_{t.replace(chr(45)+' ', '-')}():' + chr(10) + '    pass' + chr(10) for t in targets)
        return header + body

    def _heuristic_profile(self, code: str, language: str) -> dict[str, Any]:
        issues: list[str] = []
        suggestions: list[str] = []
        complexity = 1
        if language == 'python':
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.For, ast.While, ast.If)):
                        complexity += 1
                    if isinstance(node, ast.ListComp):
                        complexity += 1
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Name) and func.id in ('eval', 'exec'):
                            issues.append(f'Use of {func.id}() detected')
                            suggestions.append(f'Replace {func.id}() with a safer alternative')
                if complexity > 10:
                    issues.append(f'High cyclomatic complexity: {complexity}')
                    suggestions.append('Refactor into smaller functions')
            except SyntaxError as exc:
                issues.append(f'Syntax error: {exc.msg}')
        else:
            complexity = code.count('if ') + code.count('for ') + code.count('while ') + 1
            if 'eval(' in code or 'exec(' in code:
                issues.append('Use of eval/exec detected')
                suggestions.append('Replace with safer alternative')
        return {'complexity': complexity, 'issues': issues, 'suggestions': suggestions}


class IntelligentTestGenerator:
    def __init__(self, client: OllamaClient | None = None, model: str = 'llama3') -> None:
        self.client = client or OllamaClient()
        self.model = model

    def generate_from_spec(self, spec: str, language: str = 'python') -> str:
        prompt = textwrap.dedent(f'''
            Generate test cases in {language} from the following specification.
            Include setup, execution, and assertions. Use idiomatic patterns for {language}.
            Specification:
            {spec[:3000]}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok:
            return reply.text[:4000]
        return self._heuristic_spec_tests(spec, language)

    def generate_edge_cases(self, code: str, language: str = 'python') -> str:
        prompt = textwrap.dedent(f'''
            Generate edge case tests in {language} for the following code.
            Cover null/None, empty inputs, boundary values, type mismatches, and error paths.
            Code:
            {code[:3000]}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok:
            return reply.text[:4000]
        return self._heuristic_edge_cases(code, language)

    def suggest_test_improvements(self, code: str, existing_tests: str) -> list[str]:
        prompt = textwrap.dedent(f'''
            Analyze the following code and existing tests.
            Suggest missing test cases, uncovered branches, and edge cases.
            Return a JSON list of strings.
            Code:
            {code[:2000]}
            Existing tests:
            {existing_tests[:2000]}
        ''').strip()[:3500]
        reply = self.client.generate(prompt, self.model)
        if reply.ok:
            try:
                return json.loads(reply.text[:2000])
            except Exception:
                pass
        return self._heuristic_suggestions(code, existing_tests)

    def _heuristic_spec_tests(self, spec: str, language: str) -> str:
        return f'# Generated from spec for {language}' + chr(10) + f'# Spec: {spec[:200]}' + chr(10) * 2 + 'def test_spec():' + chr(10) + '    assert True' + chr(10)

    def _heuristic_edge_cases(self, code: str, language: str) -> str:
        return (
            f'# Edge case tests for {language}' + chr(10) +
            'def test_none_input():' + chr(10) + '    pass' + chr(10) * 2 +
            'def test_empty_input():' + chr(10) + '    pass' + chr(10) * 2 +
            'def test_boundary_values():' + chr(10) + '    pass' + chr(10) * 2 +
            'def test_type_mismatch():' + chr(10) + '    pass' + chr(10)
        )

    def _heuristic_suggestions(self, code: str, existing_tests: str) -> list[str]:
        suggestions = ['Add tests for error handling paths', 'Add tests for boundary conditions']
        if 'class ' in code:
            suggestions.append('Add tests for class initialization and methods')
        if 'async' in code:
            suggestions.append('Add tests for async/await error cases')
        return suggestions
