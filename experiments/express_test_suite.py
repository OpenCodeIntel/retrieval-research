"""
Comprehensive Test Suite for Express.js Code Search
====================================================
40 queries covering all Express functionality

Categories:
1. Response Methods (sending data)
2. Request Methods (reading data)
3. Application Setup
4. Middleware & Routing
5. Cookies & Headers
6. File Operations
7. Views & Rendering
"""

# COMPREHENSIVE GROUND TRUTH - 40 queries for Express.js
# Each tuple: (query, valid_answers, category)

EXPRESS_GROUND_TRUTH = [
    # ==========================================================================
    # 1. RESPONSE - Sending Data (12 queries)
    # ==========================================================================
    
    ("send response to client", ["send", "json", "render"], "response"),
    ("return json data from api", ["json", "jsonp", "send"], "response"),
    ("send json with callback jsonp", ["jsonp", "json"], "response"),
    ("redirect user to another url", ["redirect", "location"], "response"),
    ("set http status code", ["status", "sendStatus"], "response"),
    ("send only status code no body", ["sendStatus", "status"], "response"),
    ("set response content type", ["contentType", "type", "header"], "response"),
    ("add header to response", ["header", "set", "append", "headers"], "response"),
    ("append value to existing header", ["append", "header", "vary"], "response"),
    ("set vary header for caching", ["vary", "append"], "response"),
    ("get response header value", ["get", "header"], "response"),
    ("format response based on accept header", ["format", "accepts"], "response"),
    
    # ==========================================================================
    # 2. REQUEST - Reading Data (10 queries)
    # ==========================================================================
    
    ("get request header value", ["header", "get"], "request"),
    ("check content type of request", ["is", "header", "accepts"], "request"),
    ("check accepted content types", ["accepts", "format"], "request"),
    ("check accepted encodings", ["acceptsEncodings", "accepts"], "request"),
    ("check accepted languages", ["acceptsLanguages", "accepts"], "request"),
    ("check accepted charsets", ["acceptsCharsets", "accepts"], "request"),
    ("get client ip address", ["ip", "ips"], "request"),
    ("get all client ip addresses proxy", ["ips", "ip"], "request"),
    ("check if request is secure https", ["secure", "protocol"], "request"),
    ("get request protocol http or https", ["protocol", "secure"], "request"),
    
    # ==========================================================================
    # 3. APPLICATION SETUP (8 queries)
    # ==========================================================================
    
    ("start server listen on port", ["listen", "createApplication"], "application"),
    ("create new express application", ["createApplication", "init"], "application"),
    ("initialize express app", ["init", "defaultConfiguration", "createApplication"], "application"),
    ("configure app settings", ["set", "enable", "disable"], "application"),
    ("enable app setting", ["enable", "enabled", "set"], "application"),
    ("disable app setting", ["disable", "disabled", "set"], "application"),
    ("check if setting is enabled", ["enabled", "disabled", "set"], "application"),
    ("get app setting value", ["set", "enabled", "disabled"], "application"),
    
    # ==========================================================================
    # 4. MIDDLEWARE & ROUTING (6 queries)
    # ==========================================================================
    
    ("add middleware to app", ["use", "handle", "param"], "middleware"),
    ("handle incoming requests", ["handle", "use", "route"], "middleware"),
    ("create route for path", ["route", "use", "all"], "middleware"),
    ("handle all http methods", ["all", "route", "use"], "middleware"),
    ("add route parameter handler", ["param", "route"], "middleware"),
    ("get current request path", ["path", "route"], "middleware"),
    
    # ==========================================================================
    # 5. COOKIES & HEADERS (4 queries)
    # ==========================================================================
    
    ("set cookie in response", ["cookie", "clearCookie"], "cookies"),
    ("clear delete cookie", ["clearCookie", "cookie"], "cookies"),
    ("set link header", ["links", "header", "append"], "cookies"),
    ("set location header", ["location", "redirect", "header"], "cookies"),
    
    # ==========================================================================
    # 6. FILE OPERATIONS (4 queries)
    # ==========================================================================
    
    ("send file to client", ["sendFile", "sendfile", "download"], "files"),
    ("download file attachment", ["download", "attachment", "sendFile"], "files"),
    ("set content disposition attachment", ["attachment", "download"], "files"),
    ("stream file response", ["sendFile", "sendfile", "onstream"], "files"),
    
    # ==========================================================================
    # 7. VIEWS & RENDERING (6 queries)
    # ==========================================================================
    
    ("render view template", ["render", "View"], "views"),
    ("set template engine", ["engine", "set", "render"], "views"),
    ("lookup view file path", ["lookup", "resolve", "View"], "views"),
    ("resolve view template path", ["resolve", "lookup", "View"], "views"),
    ("render html template response", ["render", "send", "View"], "views"),
    ("configure view settings", ["set", "engine", "View"], "views"),
]

# Helper functions
def get_test_queries():
    return [(q, exp) for q, exp, _ in EXPRESS_GROUND_TRUTH]

def get_queries_by_category(category):
    return [(q, exp) for q, exp, cat in EXPRESS_GROUND_TRUTH if cat == category]

# Stats
if __name__ == "__main__":
    print(f"Total queries: {len(EXPRESS_GROUND_TRUTH)}")
    
    categories = {}
    for _, _, cat in EXPRESS_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print("\n✅ Test suite ready for Express.js")
