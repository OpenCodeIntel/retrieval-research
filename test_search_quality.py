"""
CodeIntel Search Quality Research
=================================
Compare embedding approaches for semantic code search

Approaches tested:
1. RAW_CODE - Current approach, embed code directly
2. NL_DESCRIPTION - Generate natural language description, embed that
3. HYBRID - Description + code keywords + function name

Run: python test_search_quality.py
"""

import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass
import numpy as np
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# Initialize OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================================================================
# SAMPLE CODE FUNCTIONS (Real-world examples)
# =============================================================================

SAMPLE_FUNCTIONS = [
    {
        "name": "authenticate_user",
        "language": "python",
        "code": '''def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user'''
    },
    {
        "name": "calculate_total_price",
        "language": "python",
        "code": '''def calculate_total_price(cart_items: List[CartItem], discount_code: str = None) -> float:
    """Calculate total price with optional discount."""
    subtotal = sum(item.price * item.quantity for item in cart_items)
    if discount_code:
        discount = get_discount(discount_code)
        subtotal *= (1 - discount.percentage / 100)
    tax = subtotal * TAX_RATE
    return subtotal + tax'''
    },
    {
        "name": "send_notification",
        "language": "python", 
        "code": '''async def send_notification(user_id: str, message: str, channel: str = "email") -> bool:
    """Send notification to user via specified channel."""
    user = await get_user(user_id)
    if channel == "email":
        return await send_email(user.email, message)
    elif channel == "sms":
        return await send_sms(user.phone, message)
    elif channel == "push":
        return await send_push(user.device_token, message)
    return False'''
    },
    {
        "name": "parse_csv_file",
        "language": "python",
        "code": '''def parse_csv_file(file_path: str, delimiter: str = ",") -> List[Dict]:
    """Parse CSV file and return list of dictionaries."""
    results = []
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            results.append(dict(row))
    return results'''
    },
    {
        "name": "validate_email",
        "language": "python",
        "code": '''def validate_email(email: str) -> bool:
    """Validate email format using regex."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))'''
    },
    {
        "name": "cache_response",
        "language": "python",
        "code": '''def cache_response(key: str, data: Any, ttl: int = 3600) -> None:
    """Store data in Redis cache with TTL."""
    redis_client.setex(key, ttl, json.dumps(data))'''
    },
    {
        "name": "retry_with_backoff",
        "language": "python",
        "code": '''async def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)'''
    },
    {
        "name": "generate_jwt_token",
        "language": "python",
        "code": '''def generate_jwt_token(user_id: str, expires_in: int = 3600) -> str:
    """Generate JWT token for user authentication."""
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=expires_in)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")'''
    },
    {
        "name": "paginate_results",
        "language": "python",
        "code": '''def paginate_results(query, page: int = 1, per_page: int = 20) -> Dict:
    """Paginate database query results."""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page
    }'''
    },
    {
        "name": "upload_to_s3",
        "language": "python",
        "code": '''async def upload_to_s3(file_content: bytes, bucket: str, key: str) -> str:
    """Upload file to AWS S3 and return URL."""
    s3_client.put_object(Bucket=bucket, Key=key, Body=file_content)
    return f"https://{bucket}.s3.amazonaws.com/{key}"'''
    },
]

# =============================================================================
# TEST QUERIES (Natural language - what users would search)
# =============================================================================

# Format: (query, expected_best_match_function)
TEST_QUERIES = [
    ("user login authentication", "authenticate_user"),
    ("how to verify password", "authenticate_user"),
    ("calculate shopping cart total with discount", "calculate_total_price"),
    ("apply coupon code to order", "calculate_total_price"),
    ("send email or SMS to user", "send_notification"),
    ("push notification system", "send_notification"),
    ("read CSV data from file", "parse_csv_file"),
    ("import spreadsheet data", "parse_csv_file"),
    ("check if email is valid", "validate_email"),
    ("email format validation regex", "validate_email"),
    ("store data in redis", "cache_response"),
    ("caching with expiration", "cache_response"),
    ("retry failed requests with delay", "retry_with_backoff"),
    ("exponential backoff pattern", "retry_with_backoff"),
    ("create authentication token", "generate_jwt_token"),
    ("JWT token generation", "generate_jwt_token"),
    ("database pagination", "paginate_results"),
    ("limit and offset query results", "paginate_results"),
    ("upload file to AWS", "upload_to_s3"),
    ("S3 file storage", "upload_to_s3"),
]

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

async def get_embedding(text: str) -> List[float]:
    """Get embedding from OpenAI."""
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000]
    )
    return response.data[0].embedding


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def generate_description(func_name: str, code: str) -> str:
    """Generate natural language description of code using LLM."""
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""Describe this function in 1-2 sentences. Focus on WHAT it does and WHY someone would use it. Be specific about the functionality.

Function: {func_name}
```python
{code}
```

Description:"""
        }],
        max_tokens=100,
        temperature=0
    )
    return response.choices[0].message.content.strip()

# =============================================================================
# EMBEDDING APPROACHES TO TEST
# =============================================================================

async def approach_raw_code(func: Dict) -> str:
    """CURRENT APPROACH: Embed raw code with function name."""
    return f"Function: {func['name']}\nType: function_definition\n\n{func['code']}"


async def approach_nl_description(func: Dict, description: str) -> str:
    """NEW APPROACH: Embed natural language description."""
    return description


async def approach_hybrid(func: Dict, description: str) -> str:
    """HYBRID APPROACH: Description + keywords + name."""
    # Extract keywords from code (simple approach)
    keywords = set()
    for word in func['code'].split():
        # Clean and filter
        word = word.strip('():,."\'[]{}')
        if len(word) > 2 and word.isalpha() and word.islower():
            keywords.add(word)
    
    return f"""{description}

Function name: {func['name']}
Keywords: {', '.join(list(keywords)[:15])}
Language: {func['language']}"""


async def approach_enhanced_hybrid(func: Dict, description: str) -> str:
    """ENHANCED HYBRID: Description + structured metadata."""
    return f"""{description}

This is a {func['language']} function named '{func['name']}' that can be found when searching for: {func['name'].replace('_', ' ')}"""

# =============================================================================
# TEST RUNNER
# =============================================================================

@dataclass
class TestResult:
    approach: str
    query: str
    expected_function: str
    top_match: str
    top_score: float
    expected_rank: int  # Where the expected function ranked (1 = top)
    all_scores: Dict[str, float]


async def run_experiment():
    """Run the full experiment comparing all approaches."""
    print("=" * 70)
    print("CODEINTEL SEARCH QUALITY RESEARCH")
    print("=" * 70)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Functions: {len(SAMPLE_FUNCTIONS)}")
    print(f"Queries: {len(TEST_QUERIES)}")
    
    # Step 1: Generate descriptions for all functions
    print("\n" + "-" * 70)
    print("PHASE 1: Generating NL descriptions...")
    print("-" * 70)
    
    descriptions = {}
    for func in SAMPLE_FUNCTIONS:
        desc = await generate_description(func['name'], func['code'])
        descriptions[func['name']] = desc
        print(f"\n✓ {func['name']}:")
        print(f"  → {desc}")
    
    # Step 2: Generate embeddings for each approach
    print("\n" + "-" * 70)
    print("PHASE 2: Generating embeddings for each approach...")
    print("-" * 70)
    
    approaches = {
        "RAW_CODE": approach_raw_code,
        "NL_DESCRIPTION": approach_nl_description,
        "HYBRID": approach_hybrid,
        "ENHANCED_HYBRID": approach_enhanced_hybrid,
    }
    
    # Store embeddings: approach -> func_name -> embedding
    embeddings = {approach: {} for approach in approaches}
    
    for approach_name, approach_func in approaches.items():
        print(f"\n📊 Generating {approach_name} embeddings...")
        for func in SAMPLE_FUNCTIONS:
            if approach_name == "RAW_CODE":
                text = await approach_func(func)
            else:
                text = await approach_func(func, descriptions[func['name']])
            
            embedding = await get_embedding(text)
            embeddings[approach_name][func['name']] = embedding
        print(f"   ✓ Done ({len(SAMPLE_FUNCTIONS)} embeddings)")
    
    # Step 3: Test queries against each approach
    print("\n" + "-" * 70)
    print("PHASE 3: Testing queries...")
    print("-" * 70)
    
    results = []
    
    for query, expected_func in TEST_QUERIES:
        # Get query embedding
        query_embedding = await get_embedding(query)
        
        for approach_name in approaches:
            # Calculate similarity with all functions
            scores = {}
            for func_name, func_embedding in embeddings[approach_name].items():
                score = cosine_similarity(query_embedding, func_embedding)
                scores[func_name] = score
            
            # Sort by score
            sorted_funcs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top_match = sorted_funcs[0][0]
            top_score = sorted_funcs[0][1]
            
            # Find rank of expected function
            expected_rank = next(
                i + 1 for i, (name, _) in enumerate(sorted_funcs) 
                if name == expected_func
            )
            
            results.append(TestResult(
                approach=approach_name,
                query=query,
                expected_function=expected_func,
                top_match=top_match,
                top_score=top_score,
                expected_rank=expected_rank,
                all_scores=scores
            ))
    
    # Step 4: Analyze and display results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    # Group by approach
    for approach_name in approaches:
        approach_results = [r for r in results if r.approach == approach_name]
        
        correct_top1 = sum(1 for r in approach_results if r.expected_rank == 1)
        correct_top3 = sum(1 for r in approach_results if r.expected_rank <= 3)
        avg_score = sum(r.top_score for r in approach_results) / len(approach_results)
        avg_rank = sum(r.expected_rank for r in approach_results) / len(approach_results)
        
        print(f"\n{'─' * 50}")
        print(f"📊 {approach_name}")
        print(f"{'─' * 50}")
        print(f"   Top-1 Accuracy: {correct_top1}/{len(approach_results)} ({correct_top1*100//len(approach_results)}%)")
        print(f"   Top-3 Accuracy: {correct_top3}/{len(approach_results)} ({correct_top3*100//len(approach_results)}%)")
        print(f"   Average Score:  {avg_score:.4f}")
        print(f"   Average Rank:   {avg_rank:.2f}")
        
        # Show failures
        failures = [r for r in approach_results if r.expected_rank > 1]
        if failures:
            print(f"\n   ❌ Failures:")
            for f in failures[:5]:  # Show first 5
                print(f"      Query: '{f.query}'")
                print(f"      Expected: {f.expected_function} (rank {f.expected_rank}, score {f.all_scores[f.expected_function]:.4f})")
                print(f"      Got: {f.top_match} (score {f.top_score:.4f})")
                print()
    
    # Step 5: Comparison table
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print(f"\n{'Approach':<20} {'Top-1 Acc':<12} {'Top-3 Acc':<12} {'Avg Score':<12} {'Avg Rank':<10}")
    print("-" * 70)
    
    for approach_name in approaches:
        approach_results = [r for r in results if r.approach == approach_name]
        correct_top1 = sum(1 for r in approach_results if r.expected_rank == 1)
        correct_top3 = sum(1 for r in approach_results if r.expected_rank <= 3)
        avg_score = sum(r.top_score for r in approach_results) / len(approach_results)
        avg_rank = sum(r.expected_rank for r in approach_results) / len(approach_results)
        
        print(f"{approach_name:<20} {correct_top1*100//len(approach_results):>3}%{'':<8} {correct_top3*100//len(approach_results):>3}%{'':<8} {avg_score:<12.4f} {avg_rank:<10.2f}")
    
    # Step 6: Save detailed results
    print("\n" + "-" * 70)
    print("Saving detailed results...")
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "embedding_model": "text-embedding-3-small",
            "description_model": "gpt-4o-mini",
            "num_functions": len(SAMPLE_FUNCTIONS),
            "num_queries": len(TEST_QUERIES),
        },
        "descriptions": descriptions,
        "results": [
            {
                "approach": r.approach,
                "query": r.query,
                "expected": r.expected_function,
                "top_match": r.top_match,
                "top_score": r.top_score,
                "expected_rank": r.expected_rank,
            }
            for r in results
        ]
    }
    
    # Create results directory
    os.makedirs("results", exist_ok=True)
    
    filename = f"results/experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Results saved to: {filename}")
    
    # Print recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    # Find best approach
    best_approach = None
    best_accuracy = 0
    
    for approach_name in approaches:
        approach_results = [r for r in results if r.approach == approach_name]
        accuracy = sum(1 for r in approach_results if r.expected_rank == 1) / len(approach_results)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_approach = approach_name
    
    print(f"\n🏆 Best performing approach: {best_approach}")
    print(f"   Top-1 Accuracy: {best_accuracy*100:.1f}%")
    
    if best_approach != "RAW_CODE":
        improvement = best_accuracy - sum(1 for r in results if r.approach == "RAW_CODE" and r.expected_rank == 1) / len([r for r in results if r.approach == "RAW_CODE"])
        print(f"   Improvement over RAW_CODE: +{improvement*100:.1f}%")
    
    print("\n✅ Experiment complete!")
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n🔬 Starting CodeIntel Search Quality Research...\n")
    asyncio.run(run_experiment())
