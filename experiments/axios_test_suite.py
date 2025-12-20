"""
FINAL CORRECTED Test Suite for Axios Code Search
=================================================
Properly accounts for Axios's dynamic method generation pattern.

Key insight: In Axios:
- forEachMethodNoData creates: delete, get, head, options  
- forEachMethodWithData creates: post, put, patch
- httpMethod is the actual request sender
- All three are valid answers for "make X request"
"""

# FINAL GROUND TRUTH - 50 queries for Axios
AXIOS_GROUND_TRUTH = [
    # ==========================================================================
    # 1. HTTP REQUESTS (10 queries)
    # ==========================================================================
    
    ("make http get request", ["httpMethod", "forEachMethodNoData", "generateHTTPMethod", "dispatchRequest"], "requests"),
    ("send post request with data", ["httpMethod", "forEachMethodWithData", "generateHTTPMethod", "dispatchRequest"], "requests"),
    ("make put request to update", ["httpMethod", "forEachMethodWithData", "generateHTTPMethod", "dispatchRequest"], "requests"),
    ("make patch request", ["httpMethod", "forEachMethodWithData", "generateHTTPMethod", "dispatchRequest"], "requests"),
    ("delete http request", ["httpMethod", "forEachMethodNoData", "generateHTTPMethod", "dispatchRequest"], "requests"),
    ("create axios instance", ["createInstance", "create"], "requests"),
    ("dispatch http request", ["dispatchRequest", "dispatchHttpRequest", "dispatchXhrRequest"], "requests"),
    ("send xhr request", ["dispatchXhrRequest", "dispatchRequest", "setRequestHeader"], "requests"),
    ("send fetch request", ["getFetch", "globalFetchAPI", "getBodyLength", "factory"], "requests"),
    ("make multiple requests", ["all", "spread"], "requests"),
    
    # ==========================================================================
    # 2. RESPONSE HANDLING (8 queries)
    # ==========================================================================
    
    ("handle http response", ["handleResponse", "handleLoad", "onAdapterResolution"], "response"),
    ("get response headers", ["headersToObject", "AxiosHeaders", "normalizeHeader", "onloadend"], "response"),
    ("resolve or reject response", ["settle", "_resolve", "_reject"], "response"),
    ("handle response error", ["handleStreamError", "handleRequestError", "onAdapterRejection"], "response"),
    ("transform response data", ["transformResponse", "transformData", "transform"], "response"),
    ("validate response status", ["validateStatus", "settle"], "response"),
    ("handle load complete", ["handleLoad", "onloadend", "done"], "response"),
    ("stream response data", ["handleStreamData", "handleStreamEnd", "readStream", "trackStream"], "response"),
    
    # ==========================================================================
    # 3. INTERCEPTORS (6 queries)
    # ==========================================================================
    
    ("add request interceptor", ["unshiftRequestInterceptors", "forEachHandler"], "interceptors"),
    ("add response interceptor", ["pushResponseInterceptors", "forEachHandler"], "interceptors"),
    ("run interceptor handler", ["forEachHandler", "unshiftRequestInterceptors"], "interceptors"),
    ("use interceptor middleware", ["forEachHandler", "unshiftRequestInterceptors", "pushResponseInterceptors"], "interceptors"),
    ("chain request interceptors", ["unshiftRequestInterceptors", "dispatchRequest"], "interceptors"),
    ("chain response interceptors", ["pushResponseInterceptors", "dispatchRequest"], "interceptors"),
    
    # ==========================================================================
    # 4. CANCEL REQUESTS (5 queries)
    # ==========================================================================
    
    ("cancel http request", ["cancel", "abort", "CancelToken"], "cancel"),
    ("create cancel token", ["executor", "promiseExecutor", "cancel", "create"], "cancel"),
    ("check if cancelled", ["isCancel", "throwIfCancellationRequested"], "cancel"),
    ("abort request", ["abort", "cancel", "handleAbort"], "cancel"),
    ("handle request abort", ["handleAbort", "handlerStreamAborted", "abort"], "cancel"),
    
    # ==========================================================================
    # 5. CONFIG & DEFAULTS (6 queries)
    # ==========================================================================
    
    ("merge request config", ["mergeConfig", "getMergedValue", "computeConfigValue"], "config"),
    ("set default config", ["mergeConfig", "defaultToConfig2", "mergeDeepProperties", "setRequestHeader"], "config"),
    ("set base url", ["buildFullPath", "combineURLs", "isAbsoluteURL", "setProxy"], "config"),
    ("compute config value", ["computeConfigValue", "getMergedValue", "mergeConfig"], "config"),
    ("merge deep properties", ["mergeDeepProperties", "mergeConfig", "getMergedValue"], "config"),
    ("validate config options", ["assertOptions", "validator", "transitional"], "config"),
    
    # ==========================================================================
    # 6. URL HANDLING (6 queries)
    # ==========================================================================
    
    ("build request url", ["buildURL", "encode", "buildFullPath"], "url"),
    ("combine urls together", ["combineURLs", "buildFullPath"], "url"),
    ("check absolute url", ["isAbsoluteURL", "parseProtocol"], "url"),
    ("encode url parameters", ["encode", "buildURL", "AxiosURLSearchParams"], "url"),
    ("parse url protocol", ["parseProtocol", "isAbsoluteURL"], "url"),
    ("build full path url", ["buildFullPath", "combineURLs", "isAbsoluteURL"], "url"),
    
    # ==========================================================================
    # 7. TRANSFORM & SERIALIZE (5 queries)
    # ==========================================================================
    
    ("transform request data", ["transformRequest", "transformData", "transform"], "transform"),
    ("stringify request body", ["stringifySafely", "transformRequest", "getBodyLength"], "transform"),
    ("convert to form data", ["toFormData", "formDataToStream", "convertValue", "build"], "transform"),
    ("convert form data to json", ["formDataToJSON", "parsePropPath", "buildPath"], "transform"),
    ("serialize url params", ["toURLEncodedForm", "AxiosURLSearchParams", "encode"], "transform"),
    
    # ==========================================================================
    # 8. ERROR HANDLING (4 queries)
    # ==========================================================================
    
    ("handle request error", ["handleRequestError", "handleError", "_reject"], "error"),
    ("check axios error", ["isAxiosError"], "error"),
    ("handle timeout error", ["handleTimeout", "handleRequestTimeout"], "error"),
    ("reject with error", ["_reject", "reject", "onAdapterRejection"], "error"),
]

def get_test_queries():
    return [(q, exp) for q, exp, _ in AXIOS_GROUND_TRUTH]

def get_queries_by_category(category):
    return [(q, exp) for q, exp, cat in AXIOS_GROUND_TRUTH if cat == category]

if __name__ == "__main__":
    print(f"Total queries: {len(AXIOS_GROUND_TRUTH)}")
    
    categories = {}
    for _, _, cat in AXIOS_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print("\n✅ FINAL corrected test suite for Axios")
