"""
Test Suite for Lodash Code Search
=================================
50 queries covering Lodash utility functions

Categories:
1. Array Operations
2. Collection Operations  
3. Object Operations
4. String Operations
5. Function Utilities
6. Type Checking
7. Math Operations
"""

# GROUND TRUTH - 50 queries for Lodash
LODASH_GROUND_TRUTH = [
    # ==========================================================================
    # 1. ARRAY OPERATIONS (12 queries)
    # ==========================================================================
    
    ("split array into chunks", ["chunk", "splitAt"], "array"),
    ("remove falsy values from array", ["compact", "filter"], "array"),
    ("flatten nested array", ["flatten", "flattenDeep", "flattenDepth"], "array"),
    ("get first element of array", ["head", "first", "nth"], "array"),
    ("get last element of array", ["last", "nth", "tail"], "array"),
    ("get unique values from array", ["uniq", "uniqBy", "uniqWith", "sortedUniq"], "array"),
    ("reverse array order", ["reverse"], "array"),
    ("slice array elements", ["slice", "take", "drop"], "array"),
    ("take first n elements", ["take", "takeWhile", "head"], "array"),
    ("drop first n elements", ["drop", "dropWhile", "tail"], "array"),
    ("fill array with value", ["fill"], "array"),
    ("zip multiple arrays together", ["zip", "zipWith", "zipObject"], "array"),
    
    # ==========================================================================
    # 2. COLLECTION OPERATIONS (10 queries)
    # ==========================================================================
    
    ("iterate over collection", ["forEach", "each", "forEachRight", "eachRight"], "collection"),
    ("filter collection elements", ["filter", "reject", "compact"], "collection"),
    ("transform collection elements", ["map", "flatMap", "transform"], "collection"),
    ("find element in collection", ["find", "findLast", "findIndex"], "collection"),
    ("check if all elements match", ["every", "some"], "collection"),
    ("check if any element matches", ["some", "every", "includes"], "collection"),
    ("reduce collection to value", ["reduce", "reduceRight", "transform"], "collection"),
    ("group elements by key", ["groupBy", "keyBy", "countBy"], "collection"),
    ("sort collection elements", ["sortBy", "orderBy"], "collection"),
    ("get random element", ["sample", "sampleSize", "shuffle"], "collection"),
    
    # ==========================================================================
    # 3. OBJECT OPERATIONS (10 queries)
    # ==========================================================================
    
    ("get nested object value", ["get", "result", "at"], "object"),
    ("set nested object value", ["set", "setWith", "update"], "object"),
    ("check if object has key", ["has", "hasIn"], "object"),
    ("get object keys", ["keys", "keysIn"], "object"),
    ("get object values", ["values", "valuesIn"], "object"),
    ("merge multiple objects", ["merge", "mergeWith", "assign", "defaults"], "object"),
    ("clone object deeply", ["cloneDeep", "cloneDeepWith", "clone"], "object"),
    ("pick specific keys", ["pick", "pickBy", "at"], "object"),
    ("omit specific keys", ["omit", "omitBy"], "object"),
    ("iterate over object", ["forIn", "forOwn", "forInRight"], "object"),
    
    # ==========================================================================
    # 4. STRING OPERATIONS (6 queries)
    # ==========================================================================
    
    ("convert to camel case", ["camelCase"], "string"),
    ("convert to snake case", ["snakeCase"], "string"),
    ("convert to kebab case", ["kebabCase"], "string"),
    ("capitalize first letter", ["capitalize", "upperFirst"], "string"),
    ("trim whitespace from string", ["trim", "trimStart", "trimEnd"], "string"),
    ("truncate long string", ["truncate", "slice"], "string"),
    
    # ==========================================================================
    # 5. FUNCTION UTILITIES (6 queries)
    # ==========================================================================
    
    ("debounce function calls", ["debounce", "throttle"], "function"),
    ("throttle function execution", ["throttle", "debounce"], "function"),
    ("memoize function results", ["memoize"], "function"),
    ("call function only once", ["once", "before", "after"], "function"),
    ("delay function execution", ["delay", "defer"], "function"),
    ("curry function arguments", ["curry", "curryRight", "partial"], "function"),
    
    # ==========================================================================
    # 6. TYPE CHECKING (6 queries)
    # ==========================================================================
    
    ("check if value is array", ["isArray", "isArrayLike", "isArrayLikeObject"], "type"),
    ("check if value is object", ["isObject", "isPlainObject", "isObjectLike"], "type"),
    ("check if value is string", ["isString"], "type"),
    ("check if value is number", ["isNumber", "isFinite", "isInteger"], "type"),
    ("check if value is empty", ["isEmpty", "isNil", "isNull"], "type"),
    ("check if values are equal", ["isEqual", "isEqualWith", "eq"], "type"),
]

def get_test_queries():
    return [(q, exp) for q, exp, _ in LODASH_GROUND_TRUTH]

def get_queries_by_category(category):
    return [(q, exp) for q, exp, cat in LODASH_GROUND_TRUTH if cat == category]

if __name__ == "__main__":
    print(f"Total queries: {len(LODASH_GROUND_TRUTH)}")
    
    categories = {}
    for _, _, cat in LODASH_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print("\n✅ Test suite ready for Lodash")
