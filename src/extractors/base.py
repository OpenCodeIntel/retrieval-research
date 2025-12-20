"""
Base Extractor - Abstract interface for all language extractors.

All language-specific extractors must inherit from this class
and implement the required methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class ExtractedFunction:
    """
    Unified representation of a function/method across all languages.
    
    This is the core data structure that all extractors produce.
    It contains enough context for effective semantic search.
    """
    # Core identification
    name: str                           # Simple name: "get"
    qualified_name: str                 # Full path: "Session.get" or "module.Session.get"
    file_path: str                      # Relative path: "src/sessions.py"
    
    # Code content
    code: str                           # Full function/method code
    signature: str                      # Just the signature: "def get(self, url, **kwargs)"
    
    # Context (critical for Python classes)
    class_name: Optional[str] = None    # Parent class: "Session"
    class_docstring: Optional[str] = None  # Class-level documentation
    module_docstring: Optional[str] = None # Module-level documentation
    
    # Documentation
    docstring: Optional[str] = None     # Function's own docstring
    inherited_docstring: Optional[str] = None  # From parent class (Python)
    
    # Metadata
    decorators: List[str] = field(default_factory=list)  # ["@app.route('/')"]
    is_method: bool = False             # True if inside a class
    is_static: bool = False             # @staticmethod
    is_classmethod: bool = False        # @classmethod
    is_property: bool = False           # @property
    is_private: bool = False            # _private or __dunder__
    is_dunder: bool = False             # __init__, __str__, etc.
    
    # Language info
    language: str = "unknown"           # "python", "javascript", etc.
    
    # Position
    start_line: int = 0
    end_line: int = 0
    
    # For search optimization
    summary: Optional[str] = None       # LLM-generated description
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and set derived fields."""
        # Auto-detect private/dunder
        if self.name.startswith('__') and self.name.endswith('__'):
            self.is_dunder = True
        elif self.name.startswith('_'):
            self.is_private = True
    
    @property
    def search_name(self) -> str:
        """Name optimized for search - includes class context."""
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name
    
    @property
    def full_context(self) -> str:
        """
        Full searchable context including class info.
        Used for generating embeddings.
        """
        parts = []
        
        # Add class context for methods
        if self.class_name and self.class_docstring:
            parts.append(f"Class {self.class_name}: {self.class_docstring}")
        
        # Add decorators
        if self.decorators:
            parts.append(" ".join(self.decorators))
        
        # Add signature and docstring
        parts.append(self.signature)
        if self.docstring:
            parts.append(self.docstring)
        elif self.inherited_docstring:
            parts.append(self.inherited_docstring)
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "code": self.code,
            "signature": self.signature,
            "class_name": self.class_name,
            "class_docstring": self.class_docstring,
            "docstring": self.docstring,
            "inherited_docstring": self.inherited_docstring,
            "decorators": self.decorators,
            "is_method": self.is_method,
            "is_static": self.is_static,
            "is_classmethod": self.is_classmethod,
            "is_property": self.is_property,
            "is_private": self.is_private,
            "is_dunder": self.is_dunder,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "summary": self.summary,
            "search_name": self.search_name,
        }


class BaseExtractor(ABC):
    """
    Abstract base class for all language extractors.
    
    Each language (Python, JavaScript, etc.) implements this interface
    with language-specific parsing logic.
    """
    
    # File extensions this extractor handles
    EXTENSIONS: List[str] = []
    
    # Language name
    LANGUAGE: str = "unknown"
    
    def __init__(self, repo_path: str):
        """
        Initialize extractor for a repository.
        
        Args:
            repo_path: Path to the repository root
        """
        self.repo_path = Path(repo_path)
        self.functions: List[ExtractedFunction] = []
    
    @abstractmethod
    def extract_file(self, file_path: Path) -> List[ExtractedFunction]:
        """
        Extract functions/methods from a single file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            List of extracted functions
        """
        pass
    
    def extract_all(self, exclude_patterns: List[str] = None) -> List[ExtractedFunction]:
        """
        Extract from all relevant files in the repository.
        
        Args:
            exclude_patterns: Glob patterns to exclude (e.g., ["**/test_*", "**/vendor/**"])
            
        Returns:
            All extracted functions
        """
        exclude_patterns = exclude_patterns or [
            "**/node_modules/**",
            "**/vendor/**",
            "**/.git/**",
            "**/test_*",
            "**/*_test.py",
            "**/tests/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/build/**",
        ]
        
        self.functions = []
        
        for ext in self.EXTENSIONS:
            for file_path in self.repo_path.rglob(f"*{ext}"):
                # Check exclusions
                rel_path = str(file_path.relative_to(self.repo_path))
                if any(file_path.match(pattern) for pattern in exclude_patterns):
                    continue
                
                try:
                    extracted = self.extract_file(file_path)
                    self.functions.extend(extracted)
                except Exception as e:
                    print(f"Warning: Failed to extract {file_path}: {e}")
        
        return self.functions
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            "total": len(self.functions),
            "methods": sum(1 for f in self.functions if f.is_method),
            "functions": sum(1 for f in self.functions if not f.is_method),
            "private": sum(1 for f in self.functions if f.is_private),
            "dunder": sum(1 for f in self.functions if f.is_dunder),
            "with_docstring": sum(1 for f in self.functions if f.docstring),
            "with_decorators": sum(1 for f in self.functions if f.decorators),
            "language": self.LANGUAGE,
        }
