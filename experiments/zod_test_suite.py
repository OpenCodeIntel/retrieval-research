"""
CORRECTED Test Suite for Zod Code Search
=========================================
Updated expected answers to match actual function names in codebase
"""

# CORRECTED GROUND TRUTH - 50 queries for Zod
ZOD_GROUND_TRUTH = [
    # ==========================================================================
    # 1. SCHEMA TYPES - Creating schemas (12 queries)
    # ==========================================================================
    
    ("create string schema", ["string", "ostring", "stringType"], "schema"),
    ("create number schema", ["number", "onumber", "numberType"], "schema"),
    ("create boolean schema", ["boolean", "oboolean", "booleanType"], "schema"),
    ("create object schema", ["object", "handleObjectResult", "strictObject"], "schema"),
    ("create array schema", ["array", "handleArrayResult"], "schema"),
    ("create enum schema", ["createZodEnum", "cleanEnum", "nativeEnum"], "schema"),
    ("create union type schema", ["union", "discriminatedUnion", "handleUnionResults"], "schema"),
    ("create optional field", ["optional", "nullable", "nullish"], "schema"),
    ("create date schema", ["date", "datetime", "datetimeRegex"], "schema"),
    ("create tuple schema", ["tuple", "handleTupleResult"], "schema"),
    ("create record schema", ["record", "handleRecordResult"], "schema"),
    ("create literal value schema", ["literal"], "schema"),
    
    # ==========================================================================
    # 2. VALIDATION - Parse and validate (10 queries)
    # ==========================================================================
    
    ("parse input data", ["parseStr", "handleResults"], "validation"),
    ("safely parse data", ["parseStr", "handleResults"], "validation"),
    ("validate input value", ["check", "assert", "handleCheckPropertyResult"], "validation"),
    ("check if value matches schema", ["check", "assert", "handleCheckPropertyResult"], "validation"),
    ("handle parse results", ["handleResults", "handlePipeResult"], "validation"),
    ("assert value type", ["assert", "assertEqual", "assertIs"], "validation"),
    ("check value equality", ["assertEqual", "assertNotEqual", "check"], "validation"),
    ("coerce number value", ["onumber", "oboolean", "ostring"], "validation"),
    ("validate with custom logic", ["custom", "refine", "handleRefineResult"], "validation"),
    ("check type assertion", ["assertIs", "assert", "check"], "validation"),
    
    # ==========================================================================
    # 3. TRANSFORMATIONS - Modify schemas (8 queries)
    # ==========================================================================
    
    ("transform parsed value", ["transform", "handleTransformResult", "isTransforming"], "transform"),
    ("add refinement to schema", ["refine", "handleRefineResult", "superRefine"], "transform"),
    ("chain schema transformations", ["pipe", "handlePipeResult", "transform"], "transform"),
    ("set default value result", ["handleDefaultResult", "handleCatchall"], "transform"),
    ("handle catchall schema", ["catchall", "handleCatchall"], "transform"),
    ("preprocess input before parse", ["preprocess"], "transform"),
    ("make schema partial", ["partial", "deepPartialify"], "transform"),
    ("extend object schema", ["extend", "safeExtend", "merge", "pick", "omit"], "transform"),
    
    # ==========================================================================
    # 4. ERROR HANDLING (6 queries)
    # ==========================================================================
    
    ("format validation error", ["formatError", "prettifyError", "treeifyError"], "error"),
    ("flatten error messages", ["flattenError"], "error"),
    ("create error tree", ["treeifyError"], "error"),
    ("add error to context", ["addIssueToContext", "processError"], "error"),
    ("process validation error", ["processError", "addIssueToContext"], "error"),
    ("prettify error output", ["prettifyError", "formatError"], "error"),
    
    # ==========================================================================
    # 5. STRING VALIDATIONS (8 queries)
    # ==========================================================================
    
    ("validate email address", ["email"], "string"),
    ("validate url string", ["url"], "string"),
    ("validate uuid format", ["uuid", "guid"], "string"),
    ("validate datetime string", ["datetime", "datetimeRegex"], "string"),
    ("validate base64 encoding", ["base64", "isValidBase64", "base64url", "base64ToUint8Array"], "string"),
    ("validate ip address", ["ip", "ipv4", "ipv6", "cidrv4", "cidrv6"], "string"),
    ("validate jwt token", ["jwt", "isValidJWT"], "string"),
    ("validate emoji string", ["emoji"], "string"),
    
    # ==========================================================================
    # 6. UTILITY FUNCTIONS (6 queries)
    # ==========================================================================
    
    ("clone schema definition", ["clone", "cloneDef"], "utility"),
    ("get schema description", ["describe"], "utility"),
    ("create lazy schema", ["lazy", "defineLazy"], "utility"),
    ("convert path to dot notation", ["toDotPath"], "utility"),
    ("create params", ["processCreateParams", "cleanParams"], "utility"),
    ("get config settings", ["config"], "utility"),
]

def get_test_queries():
    return [(q, exp) for q, exp, _ in ZOD_GROUND_TRUTH]

def get_queries_by_category(category):
    return [(q, exp) for q, exp, cat in ZOD_GROUND_TRUTH if cat == category]

if __name__ == "__main__":
    print(f"Total queries: {len(ZOD_GROUND_TRUTH)}")
    
    categories = {}
    for _, _, cat in ZOD_GROUND_TRUTH:
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nQueries by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print("\n✅ CORRECTED test suite for Zod")
