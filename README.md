# CodeIntel Search Quality Research

## Goal
Test and validate the hypothesis: **Natural language descriptions improve semantic search quality**

## The Problem
Current approach embeds raw code:
```
"def authenticate_user(username, password): ..."
```

User searches with English:
```
"authentication logic"
```

**Result:** Low similarity scores because code ≠ English

## The Hypothesis
If we generate NL descriptions during indexing:
```
"This function validates user credentials by checking username and password against the database"
```

Then English queries will match English descriptions = **higher similarity scores**

## Test Plan

### Phase 1: Baseline Measurement
- Take 10 real code functions
- Take 10 natural language queries
- Measure similarity scores with CURRENT approach
- Record results

### Phase 2: NL Description Approach  
- Generate descriptions for same 10 functions
- Measure similarity scores with NEW approach
- Compare results

### Phase 3: Hybrid Approach
- Test combining: description + code keywords + function name
- Find optimal weighting

## Files
- `test_search_quality.py` - Main test script
- `sample_code.py` - Test code samples
- `results/` - Output data

## Run
```bash
cd .
pip install openai numpy python-dotenv
python test_search_quality.py
```
