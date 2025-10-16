#!/usr/bin/env python3
"""
Quality Gates Validation Script
Validates test results against defined quality gates for database testing.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml
import argparse
import re


class QualityGateValidator:
    def __init__(self, config_path: str):
        """Initialize validator with quality gates configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': [],
            'summary': {}
        }

    def validate_coverage(self, service: str, coverage_file: str) -> bool:
        """Validate code coverage against thresholds."""
        try:
            coverage_data = self._parse_coverage_file(coverage_file)
            thresholds = self.config['quality_gates']['coverage'][service]
            
            line_coverage = coverage_data.get('line_coverage', 0)
            branch_coverage = coverage_data.get('branch_coverage', 0)
            
            # Check line coverage
            if line_coverage >= thresholds['line_coverage']:
                self.results['passed'].append(
                    f"✅ {service}: Line coverage {line_coverage}% meets threshold {thresholds['line_coverage']}%"
                )
            else:
                self.results['failed'].append(
                    f"❌ {service}: Line coverage {line_coverage}% below threshold {thresholds['line_coverage']}%"
                )
                return False
            
            # Check branch coverage
            if branch_coverage >= thresholds['branch_coverage']:
                self.results['passed'].append(
                    f"✅ {service}: Branch coverage {branch_coverage}% meets threshold {thresholds['branch_coverage']}%"
                )
            else:
                self.results['failed'].append(
                    f"❌ {service}: Branch coverage {branch_coverage}% below threshold {thresholds['branch_coverage']}%"
                )
                return False
            
            return True
            
        except Exception as e:
            self.results['failed'].append(f"❌ {service}: Failed to validate coverage - {str(e)}")
            return False

    def validate_test_results(self, service: str, test_results_dir: str) -> bool:
        """Validate test execution results."""
        try:
            test_files = list(Path(test_results_dir).glob("**/*test*.xml"))
            if not test_files:
                test_files = list(Path(test_results_dir).glob("**/*junit*.xml"))
            
            total_tests = 0
            failed_tests = 0
            
            for test_file in test_files:
                tests, failures = self._parse_junit_xml(test_file)
                total_tests += tests
                failed_tests += failures
            
            if failed_tests == 0:
                self.results['passed'].append(
                    f"✅ {service}: All {total_tests} tests passed"
                )
                return True
            else:
                self.results['failed'].append(
                    f"❌ {service}: {failed_tests}/{total_tests} tests failed"
                )
                return False
                
        except Exception as e:
            self.results['failed'].append(f"❌ {service}: Failed to validate test results - {str(e)}")
            return False

    def validate_performance(self, service: str, benchmark_file: str) -> bool:
        """Validate performance benchmarks."""
        try:
            if not Path(benchmark_file).exists():
                self.results['warnings'].append(
                    f"⚠️ {service}: No performance benchmark file found"
                )
                return True
            
            with open(benchmark_file, 'r') as f:
                benchmark_data = f.read()
            
            # Parse Go benchmark results
            if service == 'recommendation':
                return self._validate_go_benchmarks(service, benchmark_data)
            
            # For other services, just check if benchmarks exist
            if benchmark_data.strip():
                self.results['passed'].append(
                    f"✅ {service}: Performance benchmarks available"
                )
                return True
            else:
                self.results['warnings'].append(
                    f"⚠️ {service}: No performance benchmark data"
                )
                return True
                
        except Exception as e:
            self.results['warnings'].append(f"⚠️ {service}: Failed to validate performance - {str(e)}")
            return True  # Non-blocking for now

    def validate_database_operations(self, service: str, test_results_dir: str) -> bool:
        """Validate database-specific operations and coverage."""
        try:
            # Look for database-specific test results
            db_test_patterns = [
                "*database*test*.xml",
                "*repository*test*.xml", 
                "*integration*test*.xml"
            ]
            
            db_test_files = []
            for pattern in db_test_patterns:
                db_test_files.extend(Path(test_results_dir).glob(f"**/{pattern}"))
            
            if not db_test_files:
                self.results['warnings'].append(
                    f"⚠️ {service}: No database-specific test results found"
                )
                return True
            
            total_db_tests = 0
            failed_db_tests = 0
            
            for test_file in db_test_files:
                tests, failures = self._parse_junit_xml(test_file)
                total_db_tests += tests
                failed_db_tests += failures
            
            if failed_db_tests == 0:
                self.results['passed'].append(
                    f"✅ {service}: All {total_db_tests} database tests passed"
                )
                return True
            else:
                self.results['failed'].append(
                    f"❌ {service}: {failed_db_tests}/{total_db_tests} database tests failed"
                )
                return False
                
        except Exception as e:
            self.results['warnings'].append(f"⚠️ {service}: Failed to validate database operations - {str(e)}")
            return True

    def generate_report(self) -> Dict:
        """Generate comprehensive quality gate report."""
        total_checks = len(self.results['passed']) + len(self.results['failed'])
        passed_checks = len(self.results['passed'])
        
        self.results['summary'] = {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': len(self.results['failed']),
            'warnings': len(self.results['warnings']),
            'success_rate': (passed_checks / total_checks * 100) if total_checks > 0 else 0,
            'overall_status': 'PASSED' if len(self.results['failed']) == 0 else 'FAILED'
        }
        
        return self.results

    def _parse_coverage_file(self, coverage_file: str) -> Dict:
        """Parse coverage file based on format."""
        coverage_path = Path(coverage_file)
        
        if not coverage_path.exists():
            raise FileNotFoundError(f"Coverage file not found: {coverage_file}")
        
        if coverage_path.suffix == '.xml':
            return self._parse_coverage_xml(coverage_file)
        elif coverage_path.suffix == '.out':
            return self._parse_go_coverage(coverage_file)
        else:
            # Try to parse as text format
            return self._parse_coverage_text(coverage_file)

    def _parse_coverage_xml(self, xml_file: str) -> Dict:
        """Parse XML coverage report (JaCoCo/Cobertura format)."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # JaCoCo format
        if root.tag == 'report':
            counters = root.findall('.//counter')
            line_coverage = 0
            branch_coverage = 0
            
            for counter in counters:
                if counter.get('type') == 'LINE':
                    covered = int(counter.get('covered', 0))
                    missed = int(counter.get('missed', 0))
                    total = covered + missed
                    line_coverage = (covered / total * 100) if total > 0 else 0
                elif counter.get('type') == 'BRANCH':
                    covered = int(counter.get('covered', 0))
                    missed = int(counter.get('missed', 0))
                    total = covered + missed
                    branch_coverage = (covered / total * 100) if total > 0 else 0
            
            return {
                'line_coverage': round(line_coverage, 2),
                'branch_coverage': round(branch_coverage, 2)
            }
        
        # Cobertura format
        elif root.tag == 'coverage':
            line_rate = float(root.get('line-rate', 0)) * 100
            branch_rate = float(root.get('branch-rate', 0)) * 100
            
            return {
                'line_coverage': round(line_rate, 2),
                'branch_coverage': round(branch_rate, 2)
            }
        
        raise ValueError(f"Unsupported XML coverage format in {xml_file}")

    def _parse_go_coverage(self, coverage_file: str) -> Dict:
        """Parse Go coverage output."""
        with open(coverage_file, 'r') as f:
            content = f.read()
        
        # Parse go tool cover output
        lines = content.strip().split('\n')
        total_statements = 0
        covered_statements = 0
        
        for line in lines:
            if line.startswith('mode:'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                statements = int(parts[2])
                covered = int(parts[3])
                total_statements += statements
                covered_statements += covered if covered > 0 else 0
        
        coverage_percent = (covered_statements / total_statements * 100) if total_statements > 0 else 0
        
        return {
            'line_coverage': round(coverage_percent, 2),
            'branch_coverage': round(coverage_percent, 2)  # Go doesn't separate branch coverage
        }

    def _parse_coverage_text(self, coverage_file: str) -> Dict:
        """Parse text-based coverage report."""
        with open(coverage_file, 'r') as f:
            content = f.read()
        
        # Look for coverage percentages in text
        line_match = re.search(r'line.*?(\d+(?:\.\d+)?)%', content, re.IGNORECASE)
        branch_match = re.search(r'branch.*?(\d+(?:\.\d+)?)%', content, re.IGNORECASE)
        
        line_coverage = float(line_match.group(1)) if line_match else 0
        branch_coverage = float(branch_match.group(1)) if branch_match else 0
        
        return {
            'line_coverage': line_coverage,
            'branch_coverage': branch_coverage
        }

    def _parse_junit_xml(self, xml_file: str) -> Tuple[int, int]:
        """Parse JUnit XML test results."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        if root.tag == 'testsuite':
            tests = int(root.get('tests', 0))
            failures = int(root.get('failures', 0)) + int(root.get('errors', 0))
            return tests, failures
        elif root.tag == 'testsuites':
            total_tests = 0
            total_failures = 0
            for testsuite in root.findall('testsuite'):
                tests = int(testsuite.get('tests', 0))
                failures = int(testsuite.get('failures', 0)) + int(testsuite.get('errors', 0))
                total_tests += tests
                total_failures += failures
            return total_tests, total_failures
        
        return 0, 0

    def _validate_go_benchmarks(self, service: str, benchmark_data: str) -> bool:
        """Validate Go benchmark results."""
        lines = benchmark_data.split('\n')
        benchmark_found = False
        
        for line in lines:
            if 'Benchmark' in line and 'ns/op' in line:
                benchmark_found = True
                # Parse benchmark line: BenchmarkName-8    1000000    1234 ns/op
                parts = line.split()
                if len(parts) >= 3:
                    ns_per_op = parts[-2]
                    try:
                        time_ns = int(ns_per_op)
                        time_ms = time_ns / 1_000_000
                        
                        # Check against performance thresholds
                        perf_config = self.config['quality_gates']['performance']
                        if 'cache' in line.lower():
                            threshold = perf_config['query_performance'][service]['max_cache_operation_ms']
                            if time_ms <= threshold:
                                self.results['passed'].append(
                                    f"✅ {service}: Cache operation {time_ms:.2f}ms within threshold {threshold}ms"
                                )
                            else:
                                self.results['failed'].append(
                                    f"❌ {service}: Cache operation {time_ms:.2f}ms exceeds threshold {threshold}ms"
                                )
                                return False
                    except ValueError:
                        continue
        
        if benchmark_found:
            self.results['passed'].append(f"✅ {service}: Performance benchmarks executed")
            return True
        else:
            self.results['warnings'].append(f"⚠️ {service}: No performance benchmarks found")
            return True


def main():
    parser = argparse.ArgumentParser(description='Validate quality gates for database testing')
    parser.add_argument('--config', required=True, help='Path to quality gates configuration')
    parser.add_argument('--service', required=True, choices=['catalogue', 'voting', 'recommendation'])
    parser.add_argument('--test-results-dir', required=True, help='Directory containing test results')
    parser.add_argument('--coverage-file', help='Path to coverage report file')
    parser.add_argument('--benchmark-file', help='Path to benchmark results file')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    
    args = parser.parse_args()
    
    validator = QualityGateValidator(args.config)
    
    # Run validations
    all_passed = True
    
    # Validate test results
    if not validator.validate_test_results(args.service, args.test_results_dir):
        all_passed = False
    
    # Validate database operations
    if not validator.validate_database_operations(args.service, args.test_results_dir):
        all_passed = False
    
    # Validate coverage if provided
    if args.coverage_file:
        if not validator.validate_coverage(args.service, args.coverage_file):
            all_passed = False
    
    # Validate performance if provided
    if args.benchmark_file:
        if not validator.validate_performance(args.service, args.benchmark_file):
            all_passed = False
    
    # Generate report
    report = validator.generate_report()
    
    # Print results
    print(f"\n🔍 Quality Gate Validation Results for {args.service.title()} Service")
    print("=" * 60)
    
    for result in report['passed']:
        print(result)
    
    for result in report['failed']:
        print(result)
    
    for result in report['warnings']:
        print(result)
    
    print("\n📊 Summary:")
    print(f"Total Checks: {report['summary']['total_checks']}")
    print(f"Passed: {report['summary']['passed_checks']}")
    print(f"Failed: {report['summary']['failed_checks']}")
    print(f"Warnings: {report['summary']['warnings']}")
    print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
    print(f"Overall Status: {report['summary']['overall_status']}")
    
    # Save results if output file specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Detailed results saved to: {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()