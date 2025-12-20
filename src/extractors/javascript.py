"""
JavaScript/TypeScript Extractor
================================

Extracts functions, methods, and classes from JavaScript and TypeScript codebases.
Uses tree-sitter for reliable parsing.

Handles:
- Function declarations
- Arrow functions
- Class methods
- Variable declarations with function values
- Exported functions
- TypeScript-specific syntax
"""

import re
from pathlib import Path
from typing import List, Optional, Set, Iterator
from dataclasses import dataclass
import tree_sitter_javascript as ts_js
import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Parser

from .base import ExtractedFunction, BaseExtractor


class JavaScriptExtractor(BaseExtractor):
    """
    Extract functions from JavaScript/TypeScript codebases.
    """
    
    LANGUAGE = "typescript"
    EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs']
    
    def __init__(self, repo_path: str, language: str = "typescript"):
        """
        Args:
            repo_path: Path to repository root
            language: "javascript" or "typescript"
        """
        super().__init__(repo_path)
        self.language = language
        self.LANGUAGE = language
        
        # Initialize parser
        if language == "typescript":
            self.ts_language = Language(ts_ts.language_typescript())
            self.EXTENSIONS = ['.ts', '.tsx']
        else:
            self.ts_language = Language(ts_js.language())
            self.EXTENSIONS = ['.js', '.jsx', '.mjs']
        
        self.parser = Parser(self.ts_language)
        
        # Track current class context
        self._current_class: Optional[str] = None
        self._current_class_docstring: Optional[str] = None
    
    def get_file_extensions(self) -> Set[str]:
        return set(self.EXTENSIONS)
    
    def get_default_excludes(self) -> Set[str]:
        return {
            'node_modules', 'dist', 'build', '.git', '__pycache__',
            'coverage', '.next', '.nuxt', 'vendor', 'test', 'tests',
            '__tests__', 'spec', '__mocks__', '.cache'
        }
    
    def extract_file(self, file_path: Path) -> List[ExtractedFunction]:
        """Extract all functions from a JS/TS file."""
        try:
            code = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
        
        # Parse the file
        tree = self.parser.parse(bytes(code, 'utf8'))
        
        # Get module-level docstring (first comment)
        module_docstring = self._get_leading_comment(tree.root_node, code)
        
        # Extract functions
        results = list(self._extract_from_node(
            tree.root_node, 
            code, 
            file_path,
            module_docstring
        ))
        return results
    
    def _extract_from_node(
        self, 
        node, 
        code: str, 
        file_path: Path,
        module_docstring: Optional[str],
        class_name: Optional[str] = None,
        class_docstring: Optional[str] = None,
    ) -> Iterator[ExtractedFunction]:
        """Recursively extract functions from AST node."""
        
        # Handle class declarations
        if node.type in ['class_declaration', 'class']:
            class_name = self._get_identifier(node, code)
            class_docstring = self._get_leading_comment(node, code)
            
            # Process class body
            body = self._find_child(node, 'class_body')
            if body:
                for child in body.children:
                    yield from self._extract_from_node(
                        child, code, file_path, module_docstring,
                        class_name, class_docstring
                    )
            return
        
        # Handle method definitions
        if node.type in ['method_definition', 'public_field_definition']:
            func = self._extract_method(
                node, code, file_path, module_docstring,
                class_name, class_docstring
            )
            if func:
                yield func
            return
        
        # Handle function declarations
        if node.type == 'function_declaration':
            func = self._extract_function_declaration(
                node, code, file_path, module_docstring
            )
            if func:
                yield func
            return
        
        # Handle variable declarations (arrow functions, const fn = ...)
        if node.type == 'lexical_declaration':
            for child in node.children:
                if child.type == 'variable_declarator':
                    func = self._extract_variable_function(
                        child, code, file_path, module_docstring
                    )
                    if func:
                        yield func
            return
        
        # Handle export statements
        if node.type in ['export_statement', 'export_default_declaration']:
            for child in node.children:
                yield from self._extract_from_node(
                    child, code, file_path, module_docstring,
                    class_name, class_docstring
                )
            return
        
        # Recurse into other nodes
        for child in node.children:
            yield from self._extract_from_node(
                child, code, file_path, module_docstring,
                class_name, class_docstring
            )
    
    def _extract_function_declaration(
        self, 
        node, 
        code: str, 
        file_path: Path,
        module_docstring: Optional[str]
    ) -> Optional[ExtractedFunction]:
        """Extract a function declaration."""
        name = self._get_identifier(node, code)
        if not name or name.startswith('_'):
            return None
        
        func_code = code[node.start_byte:node.end_byte]
        if len(func_code) < 20:
            return None
        
        signature = self._extract_signature(node, code)
        docstring = self._get_leading_comment(node, code)
        decorators = self._get_decorators(node, code)
        
        return ExtractedFunction(
            name=name,
            qualified_name=name,
            file_path=str(file_path.relative_to(self.repo_path)),
            code=func_code,
            signature=signature,
            docstring=docstring,
            module_docstring=module_docstring,
            decorators=decorators,
            is_method=False,
            language=self.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )
    
    def _extract_method(
        self, 
        node, 
        code: str, 
        file_path: Path,
        module_docstring: Optional[str],
        class_name: Optional[str],
        class_docstring: Optional[str],
    ) -> Optional[ExtractedFunction]:
        """Extract a class method."""
        name = self._get_method_name(node, code)
        if not name:
            return None
        
        # Skip constructor and private methods for search
        if name.startswith('#'):  # Private field
            return None
        
        func_code = code[node.start_byte:node.end_byte]
        if len(func_code) < 10:
            return None
        
        signature = self._extract_signature(node, code)
        docstring = self._get_leading_comment(node, code)
        decorators = self._get_decorators(node, code)
        
        # Build qualified name
        qualified_name = f"{class_name}.{name}" if class_name else name
        
        # Check for static/getter/setter
        is_static = self._is_static(node)
        is_getter = self._is_getter(node)
        is_setter = self._is_setter(node)
        
        return ExtractedFunction(
            name=name,
            qualified_name=qualified_name,
            file_path=str(file_path.relative_to(self.repo_path)),
            code=func_code,
            signature=signature,
            class_name=class_name,
            class_docstring=class_docstring,
            docstring=docstring,
            module_docstring=module_docstring,
            decorators=decorators,
            is_method=True,
            is_static=is_static,
            is_property=is_getter or is_setter,
            language=self.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            metadata={'is_getter': is_getter, 'is_setter': is_setter}
        )
    
    def _extract_variable_function(
        self, 
        node, 
        code: str, 
        file_path: Path,
        module_docstring: Optional[str]
    ) -> Optional[ExtractedFunction]:
        """Extract arrow function or function expression from variable."""
        name = self._get_identifier(node, code)
        if not name or name.startswith('_'):
            return None
        
        # Check if value is a function
        value = self._find_child(node, 'arrow_function') or \
                self._find_child(node, 'function_expression') or \
                self._find_child(node, 'function')
        
        if not value:
            return None
        
        func_code = code[node.start_byte:node.end_byte]
        if len(func_code) < 20:
            return None
        
        signature = self._extract_arrow_signature(node, value, code)
        docstring = self._get_leading_comment(node.parent, code) if node.parent else None
        
        return ExtractedFunction(
            name=name,
            qualified_name=name,
            file_path=str(file_path.relative_to(self.repo_path)),
            code=func_code,
            signature=signature,
            docstring=docstring,
            module_docstring=module_docstring,
            decorators=[],
            is_method=False,
            language=self.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )
    
    def _get_identifier(self, node, code: str) -> Optional[str]:
        """Get identifier name from node."""
        for child in node.children:
            if child.type in ['identifier', 'property_identifier', 'type_identifier']:
                return code[child.start_byte:child.end_byte]
        return None
    
    def _get_method_name(self, node, code: str) -> Optional[str]:
        """Get method name."""
        for child in node.children:
            if child.type in ['property_identifier', 'private_property_identifier']:
                return code[child.start_byte:child.end_byte]
            if child.type == 'computed_property_name':
                return code[child.start_byte:child.end_byte]
        return None
    
    def _extract_signature(self, node, code: str) -> str:
        """Extract function signature."""
        # Find the parameters
        params = self._find_child(node, 'formal_parameters')
        name = self._get_identifier(node, code) or self._get_method_name(node, code)
        
        if params:
            params_str = code[params.start_byte:params.end_byte]
            return f"function {name}{params_str}"
        
        # Fallback: first line
        func_code = code[node.start_byte:node.end_byte]
        first_line = func_code.split('\n')[0].strip()
        return first_line[:200]
    
    def _extract_arrow_signature(self, var_node, func_node, code: str) -> str:
        """Extract signature for arrow function."""
        name = self._get_identifier(var_node, code)
        params = self._find_child(func_node, 'formal_parameters')
        
        if params:
            params_str = code[params.start_byte:params.end_byte]
            return f"const {name} = {params_str} =>"
        
        # Single param arrow function
        for child in func_node.children:
            if child.type == 'identifier':
                param = code[child.start_byte:child.end_byte]
                return f"const {name} = ({param}) =>"
        
        return f"const {name} = () =>"
    
    def _get_leading_comment(self, node, code: str) -> Optional[str]:
        """Get JSDoc or comment before node."""
        if not node.prev_sibling:
            return None
        
        prev = node.prev_sibling
        if prev.type == 'comment':
            comment = code[prev.start_byte:prev.end_byte]
            # Clean up comment markers
            comment = re.sub(r'^/\*\*?|\*/$', '', comment)
            comment = re.sub(r'^\s*\*\s?', '', comment, flags=re.MULTILINE)
            return comment.strip() or None
        
        return None
    
    def _get_decorators(self, node, code: str) -> List[str]:
        """Get decorators (for TypeScript)."""
        decorators = []
        prev = node.prev_sibling
        while prev and prev.type == 'decorator':
            decorators.append(code[prev.start_byte:prev.end_byte])
            prev = prev.prev_sibling
        return list(reversed(decorators))
    
    def _find_child(self, node, child_type: str):
        """Find first child of given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None
    
    def _is_static(self, node) -> bool:
        """Check if method is static."""
        for child in node.children:
            if child.type == 'static':
                return True
        return False
    
    def _is_getter(self, node) -> bool:
        """Check if method is a getter."""
        for child in node.children:
            if child.type == 'get':
                return True
        return False
    
    def _is_setter(self, node) -> bool:
        """Check if method is a setter."""
        for child in node.children:
            if child.type == 'set':
                return True
        return False


# Convenience function
def extract_javascript(repo_path: str, language: str = "typescript") -> List[ExtractedFunction]:
    """Extract all functions from a JavaScript/TypeScript repository."""
    extractor = JavaScriptExtractor(repo_path, language)
    return extractor.extract_all()
