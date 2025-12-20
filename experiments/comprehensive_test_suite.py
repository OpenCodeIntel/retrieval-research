"""
Comprehensive Test Suite for Code Search Evaluation
====================================================
50+ queries covering ALL major Zustand functionality

Categories:
1. State Management (Core)
2. Persistence & Storage
3. Middleware
4. React Integration
5. DevTools
6. Utilities & Comparison
7. Advanced Patterns
8. Error Handling
"""

# COMPREHENSIVE GROUND TRUTH - 55 queries
# Each tuple: (query, valid_answers, category)

COMPREHENSIVE_GROUND_TRUTH = [
    # ==========================================================================
    # 1. STATE MANAGEMENT - Core Operations (15 queries)
    # ==========================================================================
    
    # Basic CRUD
    ("update the store state", ["setState", "set", "savedSetState", "state"], "state"),
    ("get current state value", ["getState", "get", "state"], "state"),
    ("create a new zustand store", ["createStore", "create", "createStoreImpl", "createImpl"], "state"),
    ("initialize store with default values", ["initialState", "createStore", "create"], "state"),
    
    # Subscriptions
    ("listen for state changes", ["subscribe", "subscribeWithSelector", "listeners", "listener"], "state"),
    ("subscribe to store updates", ["subscribe", "origSubscribe", "listener"], "state"),
    ("notify all listeners of change", ["listeners", "listener", "subscribe"], "state"),
    ("unsubscribe from store", ["subscribe", "listeners"], "state"),
    
    # State Access
    ("get previous state before update", ["previousState", "prev", "previousSlice"], "state"),
    ("calculate next state value", ["nextState", "next", "nextSlice"], "state"),
    ("get a slice of state", ["slice", "currentSlice", "nextSlice"], "state"),
    ("select specific part of state", ["slice", "currentSlice", "useStore"], "state"),
    
    # State Updates
    ("merge new state with existing", ["setState", "nextState", "state", "combine"], "state"),
    ("replace entire state", ["setState", "state", "r"], "state"),
    ("partial state update", ["setState", "state", "nextState"], "state"),
    
    # ==========================================================================
    # 2. PERSISTENCE & STORAGE (12 queries)
    # ==========================================================================
    
    ("save state to localStorage", ["persist", "setItem", "persistImpl", "persistStorage"], "persist"),
    ("load saved state from storage", ["hydrate", "stateFromStorage", "getInitialState"], "persist"),
    ("persist store data across sessions", ["persist", "persistImpl", "persistStorage"], "persist"),
    ("create custom storage adapter", ["createJSONStorage", "storage", "persistStorage"], "persist"),
    ("configure storage options", ["storage", "options", "persistStorage"], "persist"),
    ("migrate old stored state version", ["migration", "migrationResult"], "persist"),
    ("handle state rehydration", ["hydrate", "hydrationListeners", "finishHydrationListeners"], "persist"),
    ("callback after rehydration completes", ["postRehydrationCallback", "finishHydrationListeners"], "persist"),
    ("parse stored JSON data", ["parse", "parseJsonThen", "parsed"], "persist"),
    ("serialize state to string", ["str", "parse", "setItem"], "persist"),
    ("get item from storage", ["str", "stateFromStorage", "storage"], "persist"),
    ("configure persistence settings", ["options", "configResult", "persistImpl"], "persist"),
    
    # ==========================================================================
    # 3. MIDDLEWARE (8 queries)
    # ==========================================================================
    
    ("combine multiple stores", ["combine"], "middleware"),
    ("use immer for immutable updates", ["immer", "immerImpl"], "middleware"),
    ("redux style state management", ["redux", "reduxImpl"], "middleware"),
    ("dispatch actions like redux", ["redux", "reduxImpl", "originalDispatch"], "middleware"),
    ("subscribe to specific state slice", ["subscribeWithSelector", "subscribeWithSelectorImpl", "slice"], "middleware"),
    ("middleware for state updates", ["immer", "redux", "subscribeWithSelector"], "middleware"),
    ("combine initial state with creator", ["combine", "initialState"], "middleware"),
    ("implement reducer pattern", ["redux", "reduxImpl", "originalDispatch"], "middleware"),
    
    # ==========================================================================
    # 4. REACT INTEGRATION (10 queries)
    # ==========================================================================
    
    ("use store in react component", ["useStore", "create", "useBoundStore", "useBoundStoreWithEqualityFn"], "react"),
    ("create react hook for store", ["useStore", "useBoundStore", "create"], "react"),
    ("bind store to react component", ["useBoundStore", "useBoundStoreWithEqualityFn", "useStore"], "react"),
    ("custom equality function for hooks", ["useStoreWithEqualityFn", "useBoundStoreWithEqualityFn", "createWithEqualityFn"], "react"),
    ("sync external store with react", ["useSyncExternalStoreExports", "useStore"], "react"),
    ("shallow comparison for selectors", ["shallow", "useShallow"], "react"),
    ("avoid unnecessary rerenders", ["shallow", "useShallow", "equalityFn"], "react"),
    ("optimize react performance", ["useShallow", "shallow", "equalityFn"], "react"),
    ("server side rendering safe", ["ssrSafe", "ssrSet"], "react"),
    ("prevent state modification during ssr", ["ssrSafe", "ssrSet"], "react"),
    
    # ==========================================================================
    # 5. DEVTOOLS INTEGRATION (8 queries)
    # ==========================================================================
    
    ("redux devtools integration", ["devtools", "extensionConnector", "devtoolsImpl"], "devtools"),
    ("connect to browser devtools", ["extensionConnector", "devtools", "newConnection"], "devtools"),
    ("configure devtools options", ["devtoolsOptions", "devtools", "devtoolsImpl"], "devtools"),
    ("track store connections", ["trackedConnections", "getTrackedConnectionState", "connectionInfo"], "devtools"),
    ("remove store from devtools", ["removeStoreFromTrackedConnections", "trackedConnections"], "devtools"),
    ("get state from devtools", ["stateFromDevtools", "setStateFromDevtools", "lastComputedState"], "devtools"),
    ("debug action names", ["action", "findCallerName", "callerLine"], "devtools"),
    ("extract connection info", ["extractConnectionInformation", "connectionInfo", "existingConnection"], "devtools"),
    
    # ==========================================================================
    # 6. UTILITIES & COMPARISON (8 queries)
    # ==========================================================================
    
    ("check if state objects are equal", ["shallow", "compareEntries", "compareIterables"], "utils"),
    ("shallow equality comparison", ["shallow", "compareEntries"], "utils"),
    ("deep compare iterables", ["compareIterables", "compareEntries", "isIterable"], "utils"),
    ("check if value is iterable", ["isIterable", "hasIterableEntries"], "utils"),
    ("identity function pass through", ["identity", "arg"], "utils"),
    ("convert to map structure", ["mapA", "mapB"], "utils"),
    ("get iterator from value", ["iteratorA", "iteratorB"], "utils"),
    ("define custom equality function", ["equalityFn", "createWithEqualityFn"], "utils"),
    
    # ==========================================================================
    # 7. ERROR HANDLING & ASYNC (4 queries)  
    # ==========================================================================
    
    ("handle storage not available", ["storage", "catch", "toThenable", "ssrSafe"], "error"),
    ("catch promise rejection", ["catch", "then", "toThenable"], "error"),
    ("convert to thenable promise", ["toThenable", "then", "catch"], "error"),
    ("handle async state updates", ["then", "toThenable", "catch"], "error"),
]

# Helper to get just queries and expected for quick testing
def get_test_queries():
    return [(q, exp) for q, exp, _ in COMPREHENSIVE_GROUND_TRUTH]

def get_queries_by_category(category):
    return [(q, exp) for q, exp, cat in COMPREHENSIVE_GROUND_TRUTH if cat == category]

# Stats
if __name__ == "__main__":
    print(f"Total queries: {len(COMPREHENSIVE_GROUND_TRUTH)}")
    
    categories = {}
    for _, _, cat in COMPREHENSIVE_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
