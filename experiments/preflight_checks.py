"""
Pre-flight Checks for Code Search Pipeline
==========================================

These checks should run BEFORE evaluation to catch data quality issues.

Lessons learned from Lodash:
1. Incomplete summaries killed accuracy (35% coverage = 62% Hit@1)
2. Wrong ground truth caused false failures
3. Build-time vs source-time function names differ
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter


class PreFlightChecker:
    """
    Run quality checks before evaluation.
    Catches issues that would silently hurt accuracy.
    """
    
    def __init__(self, functions: List[Dict], ground_truth: List[Tuple]):
        self.functions = functions
        self.ground_truth = ground_truth
        self.all_names = {f['name'].lower() for f in functions}
        self.all_names_original = {f['name'] for f in functions}
        self.issues = []
        self.warnings = []
    
    def check_summary_coverage(self, min_coverage: float = 0.95) -> bool:
        """
        Check that enough functions have summaries.
        
        Lodash lesson: 35% coverage = 62% accuracy
                       100% coverage = 74% accuracy
        Summaries add ~12% accuracy!
        """
        total = len(self.functions)
        with_summary = sum(1 for f in self.functions if f.get('summary'))
        coverage = with_summary / total if total > 0 else 0
        
        if coverage < min_coverage:
            self.issues.append({
                'type': 'LOW_SUMMARY_COVERAGE',
                'severity': 'CRITICAL',
                'message': f'Only {coverage*100:.1f}% summary coverage (need {min_coverage*100}%)',
                'details': f'{with_summary}/{total} functions have summaries',
                'fix': 'Generate summaries for remaining functions before evaluation'
            })
            return False
        
        if coverage < 1.0:
            self.warnings.append({
                'type': 'INCOMPLETE_SUMMARIES',
                'message': f'{total - with_summary} functions missing summaries'
            })
        
        return True
    
    def check_ground_truth_exists(self) -> bool:
        """
        Check that expected functions actually exist in codebase.
        
        Lodash lesson: Expected 'camelCase' but actual was 'createCompounder'
        """
        missing = []
        partial_matches = []
        
        for query, expected, category in self.ground_truth:
            found_any = False
            for exp in expected:
                exp_lower = exp.lower()
                
                # Exact match
                if exp_lower in self.all_names:
                    found_any = True
                    break
                
                # Partial match (exp in name or name in exp)
                for name in self.all_names:
                    if exp_lower in name or name in exp_lower:
                        partial_matches.append((exp, name))
                        found_any = True
                        break
            
            if not found_any:
                missing.append({
                    'query': query,
                    'expected': expected,
                    'category': category
                })
        
        if missing:
            self.issues.append({
                'type': 'MISSING_GROUND_TRUTH_FUNCTIONS',
                'severity': 'HIGH',
                'message': f'{len(missing)} expected functions not found',
                'details': missing[:5],  # Show first 5
                'fix': 'Update ground truth to match actual function names'
            })
            return False
        
        if partial_matches:
            self.warnings.append({
                'type': 'PARTIAL_MATCHES',
                'message': f'{len(partial_matches)} functions matched partially',
                'examples': partial_matches[:5]
            })
        
        return True
    
    def check_duplicate_names(self) -> bool:
        """
        Check for duplicate function names (common in Python).
        
        Click lesson: 'name' appeared 20+ times, polluting results
        """
        name_counts = Counter(f['name'].lower() for f in self.functions)
        duplicates = [(name, count) for name, count in name_counts.items() if count > 3]
        
        if duplicates:
            self.warnings.append({
                'type': 'DUPLICATE_FUNCTION_NAMES',
                'message': f'{len(duplicates)} function names appear 4+ times',
                'examples': sorted(duplicates, key=lambda x: -x[1])[:10]
            })
        
        return True  # Warning only, not blocking
    
    def check_vendor_code(self) -> bool:
        """
        Check for vendor/third-party code pollution.
        
        Lodash lesson: 830 functions from vendor/firebug-lite polluted results
        """
        vendor_patterns = ['vendor/', 'node_modules/', 'third_party/', 'external/']
        vendor_funcs = []
        
        for f in self.functions:
            file_path = f.get('file', '').lower()
            for pattern in vendor_patterns:
                if pattern in file_path:
                    vendor_funcs.append(f)
                    break
        
        if vendor_funcs:
            pct = len(vendor_funcs) / len(self.functions) * 100
            self.issues.append({
                'type': 'VENDOR_CODE_INCLUDED',
                'severity': 'HIGH' if pct > 20 else 'MEDIUM',
                'message': f'{len(vendor_funcs)} functions ({pct:.1f}%) from vendor directories',
                'fix': 'Filter out vendor code before indexing'
            })
            return False
        
        return True
    
    def check_private_function_ratio(self) -> bool:
        """
        Check ratio of private (_) and dunder (__) functions.
        
        Python codebases often have many internal functions.
        """
        private = sum(1 for f in self.functions if f['name'].startswith('_') and not f['name'].startswith('__'))
        dunder = sum(1 for f in self.functions if f['name'].startswith('__'))
        public = len(self.functions) - private - dunder
        
        private_ratio = (private + dunder) / len(self.functions) if self.functions else 0
        
        if private_ratio > 0.5:
            self.warnings.append({
                'type': 'HIGH_PRIVATE_RATIO',
                'message': f'{private_ratio*100:.0f}% functions are private/dunder',
                'details': f'Public: {public}, Private: {private}, Dunder: {dunder}',
                'suggestion': 'Consider boosting public functions in ranking'
            })
        
        return True
    
    def run_all_checks(self) -> Dict:
        """Run all pre-flight checks and return report."""
        
        checks = {
            'summary_coverage': self.check_summary_coverage(),
            'ground_truth_exists': self.check_ground_truth_exists(),
            'no_vendor_code': self.check_vendor_code(),
            'duplicate_names': self.check_duplicate_names(),
            'private_ratio': self.check_private_function_ratio(),
        }
        
        passed = all(checks.values())
        
        return {
            'passed': passed,
            'checks': checks,
            'issues': self.issues,
            'warnings': self.warnings,
            'summary': {
                'total_functions': len(self.functions),
                'critical_issues': len([i for i in self.issues if i.get('severity') == 'CRITICAL']),
                'warnings': len(self.warnings)
            }
        }


def run_preflight(summaries_file: str, ground_truth: List[Tuple]) -> Dict:
    """
    Convenience function to run pre-flight checks.
    
    Usage:
        from preflight_checks import run_preflight
        from my_test_suite import GROUND_TRUTH
        
        report = run_preflight('results/my_summaries.json', GROUND_TRUTH)
        if not report['passed']:
            print("Fix issues before evaluation!")
            for issue in report['issues']:
                print(f"  - {issue['type']}: {issue['message']}")
    """
    with open(summaries_file) as f:
        data = json.load(f)
    
    functions = data.get('functions', data)  # Handle both formats
    checker = PreFlightChecker(functions, ground_truth)
    return checker.run_all_checks()


# Demo
if __name__ == "__main__":
    import os
    os.chdir('.')
    
    print("=" * 70)
    print("🛫 PRE-FLIGHT CHECK DEMO")
    print("=" * 70)
    
    # Test on all codebases
    codebases = [
        ('results/lodash_filtered.json', 'Lodash'),
        ('results/click_summaries.json', 'Click'),
        ('results/requests_summaries.json', 'Requests'),
    ]
    
    # Dummy ground truth for demo
    dummy_gt = [("test query", ["test_func"], "test")]
    
    for file, name in codebases:
        print(f"\n📦 {name}")
        try:
            with open(file) as f:
                data = json.load(f)
            funcs = data.get('functions', [])
            
            checker = PreFlightChecker(funcs, dummy_gt)
            checker.check_summary_coverage()
            checker.check_duplicate_names()
            checker.check_private_function_ratio()
            
            print(f"   Functions: {len(funcs)}")
            with_sum = sum(1 for f in funcs if f.get('summary'))
            print(f"   Summaries: {with_sum}/{len(funcs)} ({with_sum/len(funcs)*100:.0f}%)")
            
            if checker.warnings:
                for w in checker.warnings:
                    print(f"   ⚠️ {w['type']}: {w['message']}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n✅ Pre-flight module ready!")
