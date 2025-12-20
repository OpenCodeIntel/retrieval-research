"""
CORRECTED Test Suite for Flask Code Search
==========================================
Updated to match actual extracted functions
"""

FLASK_GROUND_TRUTH = [
    # ==========================================================================
    # 1. APPLICATION SETUP (10 queries)
    # ==========================================================================
    
    ("create flask app", ["create_jinja_environment", "app_context", "__init__"], "app"),
    ("run flask server", ["run", "ensure_sync", "async_to_sync"], "app"),
    ("register blueprint", ["blueprint", "blueprints", "register"], "app"),
    ("add url rule", ["url_for", "endpoint", "route"], "app"),
    ("create application context", ["app_context", "push", "pop"], "app"),
    ("create request context", ["request_context", "push", "copy_current_request_context"], "app"),
    ("handle before request", ["before_request", "try_trigger_before_first_request_functions"], "app"),
    ("handle after request", ["after_this_request", "finalize_request", "process_response"], "app"),
    ("register error handler", ["handle_http_exception", "handle_user_exception", "handle_exception"], "app"),
    ("teardown application", ["do_teardown_appcontext", "do_teardown_request", "teardown"], "app"),
    
    # ==========================================================================
    # 2. REQUEST HANDLING (8 queries)
    # ==========================================================================
    
    ("get request data", ["from_environ", "environ", "__init__"], "request"),
    ("get form values", ["from_environ", "environ"], "request"),
    ("get request headers", ["from_environ", "environ"], "request"),
    ("get query parameters", ["from_environ", "environ"], "request"),
    ("get uploaded file", ["from_environ", "stream"], "request"),
    ("get request method", ["from_environ", "environ"], "request"),
    ("get request url", ["url_for", "create_url_adapter"], "request"),
    ("check request type", ["from_environ", "stream"], "request"),
    
    # ==========================================================================
    # 3. RESPONSE BUILDING (8 queries)
    # ==========================================================================
    
    ("create response object", ["make_response", "response_class", "from_app"], "response"),
    ("return json response", ["jsonify", "dumps", "dump"], "response"),
    ("redirect to url", ["redirect"], "response"),
    ("send file to client", ["send_file", "send_from_directory"], "response"),
    ("set response headers", ["from_app", "make_response"], "response"),
    ("set response status", ["from_app", "make_response"], "response"),
    ("abort with error", ["abort"], "response"),
    ("render html template", ["render_template", "render_template_string", "render"], "response"),
    
    # ==========================================================================
    # 4. SESSION & COOKIES (6 queries)
    # ==========================================================================
    
    ("get session data", ["get", "open_session", "SecureCookieSession"], "session"),
    ("set session value", ["setdefault", "modified"], "session"),
    ("check session permanent", ["permanent"], "session"),
    ("create null session", ["make_null_session", "NullSession"], "session"),
    ("open session", ["open_session", "save_session"], "session"),
    ("save session data", ["save_session", "open_session"], "session"),
    
    # ==========================================================================
    # 5. ROUTING & VIEWS (6 queries)
    # ==========================================================================
    
    ("define route endpoint", ["endpoint", "url_for", "route"], "routing"),
    ("get url for endpoint", ["url_for", "create_url_adapter"], "routing"),
    ("dispatch request", ["dispatch_request", "full_dispatch_request", "wsgi_app"], "routing"),
    ("match url pattern", ["create_url_adapter", "url_for"], "routing"),
    ("handle view function", ["dispatch_request", "as_view"], "routing"),
    ("create class view", ["as_view", "View", "dispatch_request"], "routing"),
    
    # ==========================================================================
    # 6. CONFIGURATION (6 queries)
    # ==========================================================================
    
    ("load config from file", ["from_file", "from_pyfile", "from_object"], "config"),
    ("get config value", ["get", "get_namespace"], "config"),
    ("set default config", ["setdefault", "make_config"], "config"),
    ("load from environment", ["from_prefixed_env", "from_envvar"], "config"),
    ("update config", ["from_mapping", "from_object"], "config"),
    ("check debug mode", ["make_config", "get"], "config"),
    
    # ==========================================================================
    # 7. TESTING (6 queries)
    # ==========================================================================
    
    ("create test client", ["test_client", "test_cli_runner"], "testing"),
    ("create test request context", ["test_request_context", "request_context"], "testing"),
    ("run test command", ["test_cli_runner", "invoke"], "testing"),
    ("push test context", ["push", "pop", "ctx"], "testing"),
    ("make test response", ["make_response", "from_app"], "testing"),
    ("session transaction", ["session_transaction"], "testing"),
]

def get_test_queries():
    return [(q, exp) for q, exp, _ in FLASK_GROUND_TRUTH]

if __name__ == "__main__":
    print(f"Total queries: {len(FLASK_GROUND_TRUTH)}")
    categories = {}
    for _, _, cat in FLASK_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    print("\n✅ CORRECTED test suite for Flask")
