"""
Go Extractor
============

Extracts functions and methods from Go codebases.
Uses tree-sitter for reliable parsing.

Handles:
- Package-level functions
- Methods (with receivers)
- Interface methods
- Exported vs unexported functions
"""

import re
from pathlib import Path
from typing import List, Optional

try:
    import tree_sitter_go as ts_go
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("⚠️  tree-sitter-go not installed. Run: pip install tree-sitter-go")

from .base import ExtractedFunction, BaseExtractor


class GoExtractor(BaseExtractor):
    """
    Extract functions and methods from Go codebases.
    """
    
    LANGUAGE = "go"
    EXTENSIONS = ['.go']
    
    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter-go is required. Run: pip install tree-sitter-go")
        
        self.go_language = Language(ts_go.language())
        self.parser = Parser(self.go_language)
    
    def extract_file(self, file_path: Path) -> List[ExtractedFunction]:
        """Extract all functions from a Go file."""
        # Skip test files
        if file_path.name.endswith('_test.go'):
            return []
        
        try:
            code = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
        
        tree = self.parser.parse(bytes(code, 'utf8'))
        
        # Get package name
        package_name = self._get_package_name(tree.root_node, code)
        
        results = []
        self._extract_from_node(tree.root_node, code, file_path, package_name, results)
        return results
    
    def _extract_from_node(
        self,
        node,
        code: str,
        file_path: Path,
        package_name: Optional[str],
        results: List[ExtractedFunction]
    ):
        """Recursively extract functions from AST."""
        
        # Handle function declarations
        if node.type == 'function_declaration':
            func = self._extract_function(node, code, file_path, package_name)
            if func:
                results.append(func)
            return
        
        # Handle method declarations
        if node.type == 'method_declaration':
            func = self._extract_method(node, code, file_path, package_name)
            if func:
                results.append(func)
            return
        
        # Recurse into children
        for child in node.children:
            self._extract_from_node(child, code, file_path, package_name, results)
    
    def _extract_function(
        self,
        node,
        code: str,
        file_path: Path,
        package_name: Optional[str],
    ) -> Optional[ExtractedFunction]:
        """Extract a function declaration."""
        
        name = self._get_function_name(node, code)
        if not name:
            return None
        
        func_code = code[node.start_byte:node.end_byte]
        if len(func_code) < 10:
            return None
        
        signature = self._extract_signature(node, code)
        docstring = self._get_comment(node, code)
        
        # Build qualified name
        qualified_name = f"{package_name}.{name}" if package_name else name
        
        # Check if exported (starts with uppercase)
        is_exported = name[0].isupper() if name else False
        
        return ExtractedFunction(
            name=name,
            qualified_name=qualified_name,
            file_path=str(file_path.relative_to(self.repo_path)),
            code=func_code,
            signature=signature,
            class_name=None,
            class_docstring=None,
            docstring=docstring,
            decorators=[],
            is_method=False,
            is_static=True,  # All Go package functions are "static"
            language="go",
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            metadata={'is_exported': is_exported, 'package': package_name}
        )
    
    def _extract_method(
        self,
        node,
        code: str,
        file_path: Path,
        package_name: Optional[str],
    ) -> Optional[ExtractedFunction]:
        """Extract a method declaration (function with receiver)."""
        
        name = self._get_function_name(node, code)
        if not name:
            return None
        
        # Get receiver type
        receiver_type = self._get_receiver_type(node, code)
        
        method_code = code[node.start_byte:node.end_byte]
        if len(method_code) < 10:
            return None
        
        signature = self._extract_signature(node, code)
        docstring = self._get_comment(node, code)
        
        # Build qualified name: package.Type.Method
        if receiver_type:
            qualified_name = f"{package_name}.{receiver_type}.{name}" if package_name else f"{receiver_type}.{name}"
        else:
            qualified_name = f"{package_name}.{name}" if package_name else name
        
        is_exported = name[0].isupper() if name else False
        
        return ExtractedFunction(
            name=name,
            qualified_name=qualified_name,
            file_path=str(file_path.relative_to(self.repo_path)),
            code=method_code,
            signature=signature,
            class_name=receiver_type,  # Receiver type as "class"
            class_docstring=None,
            docstring=docstring,
            decorators=[],
            is_method=True,
            is_static=False,
            language="go",
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            metadata={'is_exported': is_exported, 'package': package_name, 'receiver': receiver_type}
        )
    
    def _get_package_name(self, root_node, code: str) -> Optional[str]:
        """Get package declaration."""
        for child in root_node.children:
            if child.type == 'package_clause':
                for sub in child.children:
                    if sub.type == 'package_identifier':
                        return code[sub.start_byte:sub.end_byte]
        return None
    
    def _get_function_name(self, node, code: str) -> Optional[str]:
        """Get function/method name."""
        for child in node.children:
            if child.type == 'identifier':
                return code[child.start_byte:child.end_byte]
        return None
    
    def _get_receiver_type(self, node, code: str) -> Optional[str]:
        """Get receiver type for methods."""
        for child in node.children:
            if child.type == 'parameter_list':
                # First parameter list is the receiver
                for param in child.children:
                    if param.type == 'parameter_declaration':
                        # Get the type
                        for sub in param.children:
                            if sub.type == 'pointer_type':
                                # *Type -> Type
                                for t in sub.children:
                                    if t.type == 'type_identifier':
                                        return code[t.start_byte:t.end_byte]
                            elif sub.type == 'type_identifier':
                                return code[sub.start_byte:sub.end_byte]
                break  # Only first parameter_list is receiver
        return None
    
    def _extract_signature(self, node, code: str) -> str:
        """Extract function signature."""
        # Get everything up to the function body
        body = self._find_child(node, 'block')
        
        if body:
            sig_end = body.start_byte
            signature = code[node.start_byte:sig_end].strip()
        else:
            signature = code[node.start_byte:node.end_byte].strip()
        
        # Clean up - single line
        signature = ' '.join(signature.split())
        return signature[:300]
    
    def _get_comment(self, node, code: str) -> Optional[str]:
        """Get comment before function."""
        # Look for preceding comment
        if node.prev_sibling:
            if node.prev_sibling.type == 'comment':
                comment = code[node.prev_sibling.start_byte:node.prev_sibling.end_byte]
                # Clean up // prefix
                comment = re.sub(r'^//\s*', '', comment)
                return comment.strip() or None
        return None
    
    def _find_child(self, node, child_type: str):
        """Find first child of given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None


def extract_go(repo_path: str) -> List[ExtractedFunction]:
    """Extract all functions from a Go repository."""
    extractor = GoExtractor(repo_path)
    return extractor.extract_all()
