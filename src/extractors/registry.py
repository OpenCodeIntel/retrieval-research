"""
Extractor Registry - Auto-detect language and route to appropriate extractor.

This is the unified entry point for extracting code from any repository.
It detects the primary language and delegates to the right extractor.
"""

from pathlib import Path
from typing import List, Dict, Type, Optional
from collections import Counter

from .base import BaseExtractor, ExtractedFunction
from .python import PythonExtractor


class ExtractorRegistry:
    """
    Registry of all language extractors.
    
    Handles language detection and routing to appropriate extractor.
    """
    
    # Map of extensions to extractor classes
    _extractors: Dict[str, Type[BaseExtractor]] = {
        ".py": PythonExtractor,
        # Future:
        # ".js": JavaScriptExtractor,
        # ".ts": TypeScriptExtractor,
        # ".jsx": JavaScriptExtractor,
        # ".tsx": TypeScriptExtractor,
        # ".c": CExtractor,
        # ".cpp": CppExtractor,
        # ".rs": RustExtractor,
        # ".go": GoExtractor,
        # ".java": JavaExtractor,
    }
    
    @classmethod
    def register(cls, extensions: List[str], extractor_class: Type[BaseExtractor]):
        """Register a new extractor for given extensions."""
        for ext in extensions:
            cls._extractors[ext] = extractor_class
    
    @classmethod
    def detect_language(cls, repo_path: str) -> str:
        """
        Detect primary language of a repository.
        
        Returns:
            Primary language name (e.g., "python", "javascript")
        """
        path = Path(repo_path)
        
        # Count files by extension
        extension_counts = Counter()
        for ext in cls._extractors.keys():
            count = len(list(path.rglob(f"*{ext}")))
            extension_counts[ext] = count
        
        if not extension_counts:
            return "unknown"
        
        # Get most common extension
        most_common = extension_counts.most_common(1)[0][0]
        extractor_class = cls._extractors.get(most_common)
        
        if extractor_class:
            return extractor_class.LANGUAGE
        return "unknown"
    
    @classmethod
    def get_extractor(cls, repo_path: str) -> Optional[BaseExtractor]:
        """
        Get the appropriate extractor for a repository.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Extractor instance or None if no suitable extractor found
        """
        language = cls.detect_language(repo_path)
        
        # Find extractor for this language
        for ext, extractor_class in cls._extractors.items():
            if extractor_class.LANGUAGE == language:
                return extractor_class(repo_path)
        
        return None
    
    @classmethod
    def extract_all_languages(cls, repo_path: str) -> List[ExtractedFunction]:
        """
        Extract from all supported languages in a repository.
        
        Useful for multi-language repos.
        """
        all_functions = []
        used_extractors = set()
        
        path = Path(repo_path)
        
        for ext, extractor_class in cls._extractors.items():
            # Skip if we already used this extractor
            if extractor_class in used_extractors:
                continue
            
            # Check if any files exist with this extension
            if list(path.rglob(f"*{ext}")):
                extractor = extractor_class(repo_path)
                functions = extractor.extract_all()
                all_functions.extend(functions)
                used_extractors.add(extractor_class)
        
        return all_functions


def extract_repo(
    repo_path: str, 
    language: Optional[str] = None,
    all_languages: bool = False
) -> List[ExtractedFunction]:
    """
    Extract code from a repository.
    
    This is the main entry point for extraction.
    
    Args:
        repo_path: Path to the repository
        language: Force a specific language (auto-detect if None)
        all_languages: Extract from all supported languages
        
    Returns:
        List of extracted functions
        
    Example:
        # Auto-detect language
        functions = extract_repo("/path/to/flask")
        
        # Force Python
        functions = extract_repo("/path/to/repo", language="python")
        
        # Multi-language repo
        functions = extract_repo("/path/to/repo", all_languages=True)
    """
    if all_languages:
        return ExtractorRegistry.extract_all_languages(repo_path)
    
    if language:
        # Find extractor for specified language
        for ext, extractor_class in ExtractorRegistry._extractors.items():
            if extractor_class.LANGUAGE == language:
                extractor = extractor_class(repo_path)
                return extractor.extract_all()
        raise ValueError(f"No extractor for language: {language}")
    
    # Auto-detect
    extractor = ExtractorRegistry.get_extractor(repo_path)
    if extractor:
        print(f"🔍 Detected language: {extractor.LANGUAGE}")
        return extractor.extract_all()
    
    print("⚠️ Could not detect language, trying all extractors...")
    return ExtractorRegistry.extract_all_languages(repo_path)


# Convenience aliases
def supported_languages() -> List[str]:
    """Get list of supported languages."""
    return list(set(
        ext.LANGUAGE for ext in ExtractorRegistry._extractors.values()
    ))


def supported_extensions() -> List[str]:
    """Get list of supported file extensions."""
    return list(ExtractorRegistry._extractors.keys())
