"""
Java Extractor
==============

Extracts methods and classes from Java codebases.
Uses tree-sitter for reliable parsing.

Handles:
- Class methods
- Static methods
- Constructors
- Interface methods
- Abstract methods
"""

import re
from pathlib import Path
from typing import List, Optional, Set, Iterator

try:
    import tree_sitter_java as ts_java
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("⚠️  tree-sitter-java not installed. Run: pip install tree-sitter-java")

from .base import ExtractedFunction, BaseExtractor


class JavaExtractor(BaseExtractor):
    """
    Extract methods from Java codebases.
    """
    
    LANGUAGE = "java"
    EXTENSIONS = ['.java']
    
    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter-java is required. Run: pip install tree-sitter-java")
        
        self.java_language = Language(ts_java.language())
        self.parser = Parser(self.java_language)
    
    def extract_file(self, file_path: Path) -> List[ExtractedFunction]:
        """Extract all methods from a Java file."""
        try:
            code = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
        
        tree = self.parser.parse(bytes(code, 'utf8'))
        
        # Get package name
        package_name = self._get_package_name(tree.root_node, code)
        
        results = []
        self._extract_from_node(tree.root_node, code, file_path, package_name, None, None, results)
        return results
    
    def _extract_from_node(
        self,
        node,
        code: str,
        file_path: Path,
        package_name: Optional[str],
        class_name: Optional[str],
        class_docstring: Optional[str],
        results: List[ExtractedFunction]
    ):
        """Recursively extract methods from AST."""
        
        # Handle class/interface/enum declarations
        if node.type in ['class_declaration', 'interface_declaration', 'enum_declaration']:
            name = self._get_identifier(node, code)
            docstring = self._get_javadoc(node, code)
            
            # Process class body
            body = self._find_child(node, 'class_body') or \
                   self._find_child(node, 'interface_body') or \
                   self._find_child(node, 'enum_body')
            
            if body:
                for child in body.children:
                    self._extract_from_node(
                        child, code, file_path, package_name,
                        name, docstring, results
                    )
            return
        
        # Handle method declarations
        if node.type in ['method_declaration', 'constructor_declaration']:
            func = self._extract_method(
                node, code, file_path, package_name,
                class_name, class_docstring
            )
            if func:
                results.append(func)
            return
        
        # Recurse into other nodes
        for child in node.children:
            self._extract_from_node(
                child, code, file_path, package_name,
                class_name, class_docstring, results
            )
    
    def _extract_method(
        self,
        node,
        code: str,
        file_path: Path,
        package_name: Optional[str],
        class_name: Optional[str],
        class_docstring: Optional[str],
    ) -> Optional[ExtractedFunction]:
        """Extract a method declaration."""
        
        # Get method name
        name = self._get_method_name(node, code)
        if not name:
            return None
        
        # Skip private methods for search (optional)
        # modifiers = self._get_modifiers(node, code)
        # if 'private' in modifiers:
        #     return None
        
        method_code = code[node.start_byte:node.end_byte]
        if len(method_code) < 10:
            return None
        
        signature = self._extract_signature(node, code)
        docstring = self._get_javadoc(node, code)
        modifiers = self._get_modifiers(node, code)
        
        # Build qualified name
        qualified_parts = []
        if package_name:
            qualified_parts.append(package_name)
        if class_name:
            qualified_parts.append(class_name)
        qualified_parts.append(name)
        qualified_name = ".".join(qualified_parts) if len(qualified_parts) > 1 else name
        
        # If no package, use class.method format
        if not package_name and class_name:
            qualified_name = f"{class_name}.{name}"
        
        is_static = 'static' in modifiers
        is_constructor = node.type == 'constructor_declaration'
        
        return ExtractedFunction(
            name=name,
            qualified_name=qualified_name,
            file_path=str(file_path.relative_to(self.repo_path)),
            code=method_code,
            signature=signature,
            class_name=class_name,
            class_docstring=class_docstring,
            docstring=docstring,
            decorators=modifiers,  # Using decorators field for modifiers
            is_method=True,
            is_static=is_static,
            language="java",
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            metadata={'is_constructor': is_constructor}
        )
    
    def _get_package_name(self, root_node, code: str) -> Optional[str]:
        """Get package declaration."""
        for child in root_node.children:
            if child.type == 'package_declaration':
                # Find scoped_identifier
                for sub in child.children:
                    if sub.type == 'scoped_identifier' or sub.type == 'identifier':
                        return code[sub.start_byte:sub.end_byte]
        return None
    
    def _get_identifier(self, node, code: str) -> Optional[str]:
        """Get identifier name from node."""
        for child in node.children:
            if child.type == 'identifier':
                return code[child.start_byte:child.end_byte]
        return None
    
    def _get_method_name(self, node, code: str) -> Optional[str]:
        """Get method name."""
        for child in node.children:
            if child.type == 'identifier':
                return code[child.start_byte:child.end_byte]
        return None
    
    def _extract_signature(self, node, code: str) -> str:
        """Extract method signature."""
        # Get everything up to the method body
        body = self._find_child(node, 'block') or self._find_child(node, 'constructor_body')
        
        if body:
            sig_end = body.start_byte
            signature = code[node.start_byte:sig_end].strip()
        else:
            # No body (abstract method)
            signature = code[node.start_byte:node.end_byte].strip()
        
        # Clean up - remove annotations from signature display
        lines = signature.split('\n')
        sig_lines = [l for l in lines if not l.strip().startswith('@')]
        return ' '.join(sig_lines).strip()[:300]
    
    def _get_javadoc(self, node, code: str) -> Optional[str]:
        """Get JavaDoc comment before node."""
        # Look for preceding comment
        if node.prev_sibling and node.prev_sibling.type == 'block_comment':
            comment = code[node.prev_sibling.start_byte:node.prev_sibling.end_byte]
            # Check if it's JavaDoc (starts with /**)
            if comment.startswith('/**'):
                # Clean up
                comment = re.sub(r'^/\*\*|\*/$', '', comment)
                comment = re.sub(r'^\s*\*\s?', '', comment, flags=re.MULTILINE)
                return comment.strip() or None
        return None
    
    def _get_modifiers(self, node, code: str) -> List[str]:
        """Get method modifiers (public, static, etc.)."""
        modifiers = []
        for child in node.children:
            if child.type == 'modifiers':
                for mod in child.children:
                    if mod.type in ['public', 'private', 'protected', 'static', 
                                   'final', 'abstract', 'synchronized', 'native']:
                        modifiers.append(code[mod.start_byte:mod.end_byte])
                    elif mod.type == 'marker_annotation' or mod.type == 'annotation':
                        modifiers.append(code[mod.start_byte:mod.end_byte])
        return modifiers
    
    def _find_child(self, node, child_type: str):
        """Find first child of given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None


def extract_java(repo_path: str) -> List[ExtractedFunction]:
    """Extract all methods from a Java repository."""
    extractor = JavaExtractor(repo_path)
    return extractor.extract_all()
