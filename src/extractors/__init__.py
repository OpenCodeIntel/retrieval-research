"""
Extractors - Language-specific code extraction.

Usage:
    from src.extractors import extract_repo
    
    functions = extract_repo("/path/to/repo")  # Auto-detects language
"""

from .base import BaseExtractor, ExtractedFunction
from .python import PythonExtractor, extract_python_repo
from .registry import ExtractorRegistry, extract_repo

__all__ = [
    "BaseExtractor",
    "ExtractedFunction", 
    "PythonExtractor",
    "extract_python_repo",
    "ExtractorRegistry",
    "extract_repo",
]
