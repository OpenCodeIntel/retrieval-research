"""
Query-Aware RRF Reranking
=========================

Post-processes RRF results based on query intent:
1. Dunder filtering: Deprioritize __methods__ for user queries
2. Constructor boosting: Boost __init__ for "create/make/new" queries
3. Action-class matching: "X from Y" boosts Y.X methods
"""

import re
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


# Dunder methods that are rarely what users want
DEPRIORITIZE_DUNDERS = {
    '__nonzero__', '__bool__', '__repr__', '__str__', '__len__',
    '__iter__', '__next__', '__contains__', '__getitem__', '__setitem__',
    '__delitem__', '__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__',
    '__hash__', '__call__', '__enter__', '__exit__',
}

# Useful dunders that users might actually want
USEFUL_DUNDERS = {'__init__', '__new__', '__del__'}

# Patterns that indicate "create" intent
CREATE_PATTERNS = [
    r'\bcreate\b', r'\bmake\b', r'\bnew\b', r'\binitialize\b',
    r'\binstantiate\b', r'\bbuild\b', r'\bconstruct\b',
]

# Patterns for "get X from Y" 
GET_FROM_PATTERNS = [
    r'get (\w+) from (\w+)',
    r'(\w+) from (\w+)',
    r'(\w+)\.(\w+)',
]


def detect_query_intent(query: str) -> dict:
    """Detect user intent from query."""
    query_lower = query.lower()
    
    intent = {
        'is_create': False,
        'create_target': None,
        'is_get_from': False,
        'get_what': None,
        'get_from': None,
    }
    
    # Check for create intent
    for pattern in CREATE_PATTERNS:
        if re.search(pattern, query_lower):
            intent['is_create'] = True
            # Extract what they want to create
            match = re.search(r'(?:create|make|new|build)\s+(?:a\s+)?(\w+)', query_lower)
            if match:
                intent['create_target'] = match.group(1)
            break
    
    # Check for "get X from Y" pattern
    for pattern in GET_FROM_PATTERNS:
        match = re.search(pattern, query_lower)
        if match:
            intent['is_get_from'] = True
            intent['get_what'] = match.group(1)
            intent['get_from'] = match.group(2) if len(match.groups()) > 1 else None
            break
    
    return intent


def rerank_results(
    query: str,
    functions: List,
    rrf_scores: np.ndarray,
    dunder_penalty: float = 0.5,
    init_boost: float = 0.3,
) -> np.ndarray:
    """
    Rerank RRF results based on query intent.
    
    Args:
        query: User query
        functions: List of ExtractedFunction
        rrf_scores: Original RRF scores
        dunder_penalty: Penalty multiplier for unwanted dunders (0-1)
        init_boost: Boost for __init__ on create queries
        
    Returns:
        Adjusted scores
    """
    intent = detect_query_intent(query)
    adjusted = rrf_scores.copy()
    
    for i, func in enumerate(functions):
        name = func.name.lower()
        qualified = func.qualified_name.lower()
        
        # Dunder handling
        if func.is_dunder:
            if name in DEPRIORITIZE_DUNDERS:
                # Penalize unwanted dunders
                adjusted[i] *= dunder_penalty
            elif name == '__init__' and intent['is_create']:
                # Boost __init__ for create queries
                if intent['create_target']:
                    # Extra boost if class name matches
                    target = intent['create_target'].lower()
                    if target in qualified or target in (func.class_name or '').lower():
                        adjusted[i] *= (1 + init_boost * 2)
                    else:
                        adjusted[i] *= (1 + init_boost)
                else:
                    adjusted[i] *= (1 + init_boost)
        
        # "Get X from Y" handling
        if intent['is_get_from'] and intent['get_from']:
            class_name = (func.class_name or '').lower()
            if intent['get_from'].lower() in class_name:
                # Boost methods from the target class
                if intent['get_what'] and intent['get_what'].lower() in name:
                    adjusted[i] *= 1.5  # Strong boost
                else:
                    adjusted[i] *= 1.1  # Mild boost
    
    return adjusted


def test_reranking():
    """Test the reranking logic."""
    
    @dataclass
    class MockFunc:
        name: str
        qualified_name: str
        class_name: Optional[str]
        is_dunder: bool
    
    # Test cases
    test_cases = [
        {
            'query': 'check response status',
            'functions': [
                MockFunc('__nonzero__', 'Response.__nonzero__', 'Response', True),
                MockFunc('__bool__', 'Response.__bool__', 'Response', True),
                MockFunc('raise_for_status', 'Response.raise_for_status', 'Response', False),
            ],
            'original_ranks': [0, 1, 2],  # __nonzero__ was #1
            'expected_top': 'raise_for_status',
        },
        {
            'query': 'create http adapter',
            'functions': [
                MockFunc('get_adapter', 'Session.get_adapter', 'Session', False),
                MockFunc('mount', 'Session.mount', 'Session', False),
                MockFunc('__init__', 'HTTPAdapter.__init__', 'HTTPAdapter', True),
            ],
            'original_ranks': [0, 1, 2],  # get_adapter was #1
            'expected_top': '__init__',
        },
    ]
    
    print("🧪 RERANKING TEST")
    print("=" * 60)
    
    for tc in test_cases:
        query = tc['query']
        funcs = tc['functions']
        
        # Simulate original RRF scores (higher = better)
        original_scores = np.array([1.0 / (60 + r) for r in tc['original_ranks']])
        
        # Apply reranking
        adjusted = rerank_results(query, funcs, original_scores)
        
        # Find new top
        new_top_idx = np.argmax(adjusted)
        new_top = funcs[new_top_idx].name
        
        status = "✅" if new_top == tc['expected_top'] else "❌"
        
        print(f"\n{status} Query: \"{query}\"")
        print(f"   Original top: {funcs[0].name}")
        print(f"   New top: {new_top}")
        print(f"   Expected: {tc['expected_top']}")
        
        # Show score changes
        for i, f in enumerate(funcs):
            change = adjusted[i] / original_scores[i]
            print(f"   {f.name}: {original_scores[i]:.4f} → {adjusted[i]:.4f} ({change:.2f}x)")


if __name__ == "__main__":
    test_reranking()
