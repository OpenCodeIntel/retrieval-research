"""
Python Extractor - Class-aware extraction for Python codebases.

Key Features:
1. Qualified names: Session.get, not just get
2. Class context: Includes class docstring with methods
3. Decorator awareness: Extracts @app.route, @click.command, etc.
4. Docstring inheritance: Walks MRO for inherited docs
5. Property support: Handles @property decorators
"""

from __future__ import annotations
import ast
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union
from .base import BaseExtractor, ExtractedFunction


class PythonExtractor(BaseExtractor):
    """
    AST-based Python extractor with full class awareness.
    
    Unlike simple regex-based extraction, this properly handles:
    - Nested classes
    - Method inheritance
    - Decorators
    - Properties
    - Static/class methods
    """
    
    EXTENSIONS = [".py"]
    LANGUAGE = "python"
    
    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        self._current_file: Optional[Path] = None
        self._current_source: str = ""
        self._module_docstring: Optional[str] = None
    
    def extract_file(self, file_path: Path) -> List[ExtractedFunction]:
        """Extract all functions and methods from a Python file."""
        try:
            source = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
        
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            print(f"Syntax error in {file_path}: {e}")
            return []
        
        self._current_file = file_path
        self._current_source = source
        self._source_lines = source.splitlines()
        
        # Get module docstring
        self._module_docstring = ast.get_docstring(tree)
        
        functions = []
        
        # Process top-level items
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Top-level function
                func = self._extract_function(node, class_context=None)
                if func:
                    functions.append(func)
            
            elif isinstance(node, ast.ClassDef):
                # Class with methods
                class_funcs = self._extract_class(node)
                functions.extend(class_funcs)
        
        return functions
    
    def _extract_class(self, node: ast.ClassDef) -> List[ExtractedFunction]:
        """Extract all methods from a class, with full class context."""
        functions = []
        
        class_name = node.name
        class_docstring = ast.get_docstring(node)
        class_decorators = self._get_decorators(node)
        
        # Build class context for methods
        class_context = {
            "name": class_name,
            "docstring": class_docstring,
            "decorators": class_decorators,
            "bases": [self._get_node_source(base) for base in node.bases],
            "init_signature": None,
        }
        
        # First pass: find __init__ signature
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "__init__":
                    class_context["init_signature"] = self._get_signature(item)
                    break
        
        # Second pass: extract all methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = self._extract_function(item, class_context)
                if func:
                    functions.append(func)
            
            # Handle nested classes
            elif isinstance(item, ast.ClassDef):
                nested_funcs = self._extract_nested_class(item, parent_class=class_name)
                functions.extend(nested_funcs)
        
        return functions
    
    def _extract_nested_class(self, node: ast.ClassDef, parent_class: str) -> List[ExtractedFunction]:
        """Handle nested classes with qualified names."""
        functions = []
        
        nested_class_name = f"{parent_class}.{node.name}"
        class_docstring = ast.get_docstring(node)
        
        class_context = {
            "name": nested_class_name,
            "docstring": class_docstring,
            "decorators": self._get_decorators(node),
            "bases": [self._get_node_source(base) for base in node.bases],
            "init_signature": None,
        }
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = self._extract_function(item, class_context)
                if func:
                    functions.append(func)
        
        return functions
    
    def _extract_function(
        self, 
        node,  # ast.FunctionDef or ast.AsyncFunctionDef
        class_context: Optional[Dict[str, Any]]
    ) -> Optional[ExtractedFunction]:
        """Extract a single function or method with full context."""
        
        name = node.name
        docstring = ast.get_docstring(node)
        decorators = self._get_decorators(node)
        
        # Build qualified name
        if class_context:
            qualified_name = f"{class_context['name']}.{name}"
            class_name = class_context['name']
            class_docstring = class_context.get('docstring')
        else:
            qualified_name = name
            class_name = None
            class_docstring = None
        
        # Detect method types from decorators
        is_static = any('@staticmethod' in d for d in decorators)
        is_classmethod = any('@classmethod' in d for d in decorators)
        is_property = any('@property' in d for d in decorators)
        
        # Get full code and signature
        code = self._get_node_source(node)
        signature = self._get_signature(node)
        
        # Relative file path
        try:
            rel_path = str(self._current_file.relative_to(self.repo_path))
        except ValueError:
            rel_path = str(self._current_file)
        
        return ExtractedFunction(
            name=name,
            qualified_name=qualified_name,
            file_path=rel_path,
            code=code,
            signature=signature,
            class_name=class_name,
            class_docstring=class_docstring,
            module_docstring=self._module_docstring,
            docstring=docstring,
            decorators=decorators,
            is_method=class_context is not None,
            is_static=is_static,
            is_classmethod=is_classmethod,
            is_property=is_property,
            language="python",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
        )
    
    def _get_decorators(self, node) -> List[str]:  # ast.FunctionDef or ast.ClassDef
        """Extract decorator strings."""
        decorators = []
        for dec in node.decorator_list:
            dec_str = self._get_node_source(dec)
            decorators.append(f"@{dec_str}")
        return decorators
    
    def _get_signature(self, node) -> str:  # ast.FunctionDef or ast.AsyncFunctionDef
        """Get just the function signature line."""
        # Build from AST for cleaner output
        args = []
        
        # Handle positional args
        for arg in node.args.posonlyargs:
            args.append(self._format_arg(arg))
        
        if node.args.posonlyargs:
            args.append("/")
        
        for arg in node.args.args:
            args.append(self._format_arg(arg))
        
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        elif node.args.kwonlyargs:
            args.append("*")
        
        for arg in node.args.kwonlyargs:
            args.append(self._format_arg(arg))
        
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)})"
    
    def _format_arg(self, arg: ast.arg) -> str:
        """Format a single argument with optional type annotation."""
        if arg.annotation:
            return f"{arg.arg}: {self._get_node_source(arg.annotation)}"
        return arg.arg
    
    def _get_node_source(self, node: ast.AST) -> str:
        """Get source code for an AST node."""
        try:
            return ast.get_source_segment(self._current_source, node) or ""
        except Exception:
            return ""


def extract_python_repo(repo_path: str, exclude_patterns: List[str] = None) -> List[ExtractedFunction]:
    """
    Convenience function to extract a Python repository.
    
    Args:
        repo_path: Path to the repository
        exclude_patterns: Patterns to exclude
        
    Returns:
        List of extracted functions with full context
    """
    extractor = PythonExtractor(repo_path)
    functions = extractor.extract_all(exclude_patterns)
    
    print(f"\n📊 Extraction Stats:")
    stats = extractor.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    return functions


# Test
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python python_extractor.py <repo_path>")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    functions = extract_python_repo(repo_path)
    
    print(f"\n📦 Extracted {len(functions)} functions")
    print("\n🔍 Sample (first 5):")
    for func in functions[:5]:
        print(f"\n  • {func.qualified_name}")
        print(f"    File: {func.file_path}")
        print(f"    Decorators: {func.decorators}")
        print(f"    Is method: {func.is_method}")
        if func.class_docstring:
            print(f"    Class doc: {func.class_docstring[:50]}...")
