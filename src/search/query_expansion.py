"""
Query Expansion for Code Search
================================

Expands vague user queries with synonyms and related terms
to improve search recall.

Example:
  "get headers" → ["get headers", "headers property", "Response.headers", "default_headers"]
"""

import re
from typing import List, Dict, Set

# Domain-specific expansions for HTTP/web programming
EXPANSIONS = {
    # Properties that users ask for as if they were methods
    "headers": ["headers", "get_headers", "default_headers", "Headers", "response.headers"],
    "cookies": ["cookies", "get_cookies", "extract_cookies", "RequestsCookieJar", "cookiejar"],
    "content": ["content", "text", "body", "response.content", "response.text"],
    "encoding": ["encoding", "apparent_encoding", "get_encoding", "charset"],
    "status": ["status_code", "status", "response.status_code", "ok"],
    "url": ["url", "request.url", "response.url", "prepare_url"],
    
    # Actions
    "get": ["get", "request", "fetch", "retrieve"],
    "post": ["post", "send", "submit"],
    "send": ["send", "request", "dispatch", "transmit"],
    "parse": ["parse", "extract", "decode", "process"],
    "create": ["create", "make", "build", "new", "init", "__init__"],
    "clear": ["clear", "remove", "delete", "reset", "empty"],
    "set": ["set", "update", "modify", "change"],
    
    # HTTP concepts
    "auth": ["auth", "authentication", "HTTPBasicAuth", "HTTPDigestAuth", "HTTPProxyAuth"],
    "session": ["session", "Session", "persistent"],
    "request": ["request", "Request", "PreparedRequest"],
    "response": ["response", "Response"],
    "adapter": ["adapter", "HTTPAdapter", "BaseAdapter", "mount"],
    "proxy": ["proxy", "proxies", "HTTPProxyAuth"],
    "timeout": ["timeout", "Timeout", "connect_timeout", "read_timeout"],
    "redirect": ["redirect", "allow_redirects", "follow", "resolve_redirects"],
    "ssl": ["ssl", "verify", "cert", "certificate"],
    "cookie": ["cookie", "cookies", "cookiejar", "RequestsCookieJar"],
}

# Compound query patterns
COMPOUND_PATTERNS = [
    # "X from Y" patterns
    (r"get (\w+) from (\w+)", lambda m: [f"{m.group(2)}.{m.group(1)}", f"get_{m.group(1)}", m.group(1)]),
    # "create X" patterns  
    (r"create (\w+)", lambda m: [f"{m.group(1)}.__init__", f"create_{m.group(1)}", f"make_{m.group(1)}", m.group(1)]),
    # "X Y" where X is verb, Y is noun
    (r"(get|set|clear|parse|send|create) (\w+)", lambda m: [f"{m.group(1)}_{m.group(2)}", m.group(2), f"{m.group(2)}.{m.group(1)}"]),
]


def expand_query(query: str) -> List[str]:
    """
    Expand a query into multiple search terms.
    
    Args:
        query: Original user query
        
    Returns:
        List of expanded queries to search for
    """
    expanded = [query]  # Always include original
    query_lower = query.lower()
    words = set(re.findall(r'\b\w+\b', query_lower))
    
    # Add word-level expansions
    for word in words:
        if word in EXPANSIONS:
            for exp in EXPANSIONS[word]:
                if exp.lower() not in query_lower:
                    expanded.append(f"{query} {exp}")
    
    # Apply compound patterns
    for pattern, generator in COMPOUND_PATTERNS:
        match = re.search(pattern, query_lower)
        if match:
            new_terms = generator(match)
            expanded.extend(new_terms)
    
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for q in expanded:
        q_lower = q.lower()
        if q_lower not in seen:
            seen.add(q_lower)
            result.append(q)
    
    return result[:5]  # Limit to 5 expansions


def get_expanded_search_terms(query: str) -> Dict[str, float]:
    """
    Get search terms with weights.
    Original query gets weight 1.0, expansions get 0.5.
    """
    terms = expand_query(query)
    weights = {}
    for i, term in enumerate(terms):
        weights[term] = 1.0 if i == 0 else 0.5
    return weights


# Test
if __name__ == "__main__":
    test_queries = [
        "get response headers",
        "clear cookies",
        "send options request",
        "create http adapter",
        "parse url",
        "http basic auth",
        "get cookies from response",
        "prepare request in session",
    ]
    
    print("🔄 QUERY EXPANSION TEST")
    print("=" * 60)
    
    for q in test_queries:
        expanded = expand_query(q)
        print(f"\n📌 \"{q}\"")
        for i, exp in enumerate(expanded):
            marker = "→" if i == 0 else "+"
            print(f"   {marker} {exp}")
