"""
Test Suite for Requests Code Search
====================================
50 queries for Python Requests HTTP library
Compare with Axios (JS HTTP client)!
"""

REQUESTS_GROUND_TRUTH = [
    # ==========================================================================
    # 1. HTTP METHODS (10 queries)
    # ==========================================================================
    
    ("send get request", ["get", "request"], "http"),
    ("send post request", ["post", "request"], "http"),
    ("send put request", ["put", "request"], "http"),
    ("send delete request", ["delete", "request"], "http"),
    ("send patch request", ["patch", "request"], "http"),
    ("send head request", ["head", "request"], "http"),
    ("send options request", ["options", "request"], "http"),
    ("make http request", ["request", "send"], "http"),
    ("prepare request", ["prepare", "prepare_request", "PreparedRequest"], "http"),
    ("send prepared request", ["send", "request"], "http"),
    
    # ==========================================================================
    # 2. SESSION MANAGEMENT (8 queries)
    # ==========================================================================
    
    ("create session", ["Session", "session"], "session"),
    ("mount adapter", ["mount", "get_adapter"], "session"),
    ("get adapter for url", ["get_adapter", "mount"], "session"),
    ("close session", ["close"], "session"),
    ("merge environment settings", ["merge_environment_settings", "merge"], "session"),
    ("resolve redirects", ["resolve_redirects", "redirect"], "session"),
    ("prepare request in session", ["prepare_request", "prepare"], "session"),
    ("get request from session", ["request", "get"], "session"),
    
    # ==========================================================================
    # 3. RESPONSE HANDLING (8 queries)
    # ==========================================================================
    
    ("get response content", ["content", "text", "iter_content"], "response"),
    ("get response json", ["json"], "response"),
    ("iterate response content", ["iter_content", "iter_lines"], "response"),
    ("iterate response lines", ["iter_lines", "iter_content"], "response"),
    ("check response status", ["raise_for_status", "ok", "status_code"], "response"),
    ("raise for bad status", ["raise_for_status"], "response"),
    ("get response headers", ["headers"], "response"),
    ("get response encoding", ["encoding", "apparent_encoding"], "response"),
    
    # ==========================================================================
    # 4. COOKIES (6 queries)
    # ==========================================================================
    
    ("get cookies from response", ["extract_cookies_to_jar", "cookies"], "cookies"),
    ("set cookie value", ["set", "set_cookie"], "cookies"),
    ("get cookie value", ["get", "get_dict"], "cookies"),
    ("create cookie jar", ["cookiejar_from_dict", "RequestsCookieJar"], "cookies"),
    ("merge cookies", ["merge_cookies", "add_dict_to_cookiejar"], "cookies"),
    ("clear cookies", ["clear"], "cookies"),
    
    # ==========================================================================
    # 5. AUTHENTICATION (6 queries)
    # ==========================================================================
    
    ("http basic auth", ["HTTPBasicAuth", "_basic_auth_str"], "auth"),
    ("http digest auth", ["HTTPDigestAuth", "build_digest_header"], "auth"),
    ("http proxy auth", ["HTTPProxyAuth"], "auth"),
    ("build auth header", ["build_digest_header", "_basic_auth_str"], "auth"),
    ("handle auth challenge", ["handle_401", "handle_407"], "auth"),
    ("parse digest challenge", ["parse_dict_header"], "auth"),
    
    # ==========================================================================
    # 6. UTILITIES (8 queries)
    # ==========================================================================
    
    ("encode url parameters", ["urlencode", "encode_params"], "utils"),
    ("parse url", ["urlparse", "parse_url", "requote_uri"], "utils"),
    ("get encoding from headers", ["get_encoding_from_headers", "encoding"], "utils"),
    ("guess content type", ["guess_filename", "guess_json_utf"], "utils"),
    ("check if url is absolute", ["is_valid_cidr", "urlparse"], "utils"),
    ("prepare url", ["prepare_url", "requote_uri"], "utils"),
    ("stream decompress", ["stream_decode_response_unicode", "iter_slices"], "utils"),
    ("select proxy", ["select_proxy", "prepend_scheme_if_needed"], "utils"),
    
    # ==========================================================================
    # 7. ADAPTERS (4 queries)
    # ==========================================================================
    
    ("create http adapter", ["HTTPAdapter", "BaseAdapter"], "adapter"),
    ("send through adapter", ["send"], "adapter"),
    ("build response from urllib", ["build_response"], "adapter"),
    ("get connection from pool", ["get_connection", "poolmanager"], "adapter"),
]

def get_test_queries():
    return [(q, exp) for q, exp, _ in REQUESTS_GROUND_TRUTH]

if __name__ == "__main__":
    print(f"Total queries: {len(REQUESTS_GROUND_TRUTH)}")
    categories = {}
    for _, _, cat in REQUESTS_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    print("\n✅ Test suite ready for Requests (Python)")
