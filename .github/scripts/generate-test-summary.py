#!/usr/bin/env python3
"""
Test Summary Generator for CI/CD Pipeline
Generates a concise summary of test results for GitHub Actions and PR comments.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any
import xml.etree.ElementTree as ET


class TestSummaryGenerator:
    """Generates concise test summaries for CI/CD pipelines."""
    
    def __init__(self, results_dir: str):
        """Initialize the summary generator."""
        self.results_dir = Path(results_dir)
        self.services = ['catalogue', 'voting', 'recommendation']
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a concise test summary."""
        summary = {
            'overall_status': 'PASSED',
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'coverage_percentage': 0.0,
            'services': {},
            'issues': [],
            'recommendations': []
        }
        
        # Analyze each service
        for service in self.services:
            service_summary = self._analyze_service(service)
            if service_summary:
                summary['services'][service] = service_summary
                summary['total_tests'] += service_summary['total_tests']
                summary['passed_tests'] += service_summary['passed_tests']
                summary['failed_tests'] += service_summary['failed_tests']
                
                if service_summary['status'] == 'FAILED':
                    summary['overall_status'] = 'FAILED'
        
        # Calculate overall success rate
        if summary['total_tests'] > 0:
            success_rate = (summary['passed_tests'] / summary['total_tests']) * 100
            summary['success_rate'] = success_rate
            
            if success_rate < 100:
                summary['overall_status'] = 'FAILED'
        
        # Calculate average coverage
        coverage_values = [
            s.get('coverage', 0) for s in summary['services'].values() 
            if s.get('coverage', 0) > 0
        ]
        if coverage_values:
            summary['coverage_percentage'] = sum(coverage_values) / len(coverage_values)
        
        # Generate issues and recommendations
        summary['issues'] = self._identify_critical_issues(summary)
        summary['recommendations'] = self._generate_recommendations(summary)
        
        return summary
    
    def _analyze_service(self, service: str) -> Dict[str, Any]:
        """Analyze test results for a specific service."""
        service_dir = self.results_dir / f"{service}-test-results"
        if not service_dir.exists():
            # Try alternative directory structure
            service_dir = self.results_dir / service
            if not service_dir.exists():
                return None
        
        service_summary = {
            'name': service,
            'status': 'PASSED',
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'coverage': 0.0,
            'test_types': {},
            'critical_failures': []
        }
        
        # Look for test result files
        test_files = list(service_dir.glob("**/*.xml"))
        if not test_files:
            test_files = list(service_dir.glob("**/junit.xml"))
        
        for test_file in test_files:
            test_data = self._parse_test_file(test_file)
            if test_data:
                service_summary['total_tests'] += test_data['total_tests']
                service_summary['passed_tests'] += test_data['passed_tests']
                service_summary['failed_tests'] += test_data['failed_tests']
                
                # Identify test type from filename
                test_type = self._identify_test_type(test_file.name)
                service_summary['test_types'][test_type] = test_data
                
                # Collect critical failures
                if test_data['failed_tests'] > 0:
                    service_summary['status'] = 'FAILED'
                    service_summary['critical_failures'].extend(
                        self._extract_critical_failures(test_data)
                    )
        
        # Parse coverage if available
        coverage_files = [
            service_dir / 'coverage.xml',
            service_dir / 'coverage.out',
            service_dir / 'coverage' / 'coverage-final.json'
        ]
        
        for coverage_file in coverage_files:
            if coverage_file.exists():
                coverage = self._parse_coverage_file(coverage_file)
                if coverage:
                    service_summary['coverage'] = coverage
                    break
        
        return service_summary
    
    def _parse_test_file(self, test_file: Path) -> Dict[str, Any]:
        """Parse a test result file."""
        try:
            if test_file.suffix == '.xml':
                return self._parse_junit_xml(test_file)
            elif test_file.suffix == '.json':
                return self._parse_json_results(test_file)
        except Exception as e:
            print(f"Warning: Failed to parse {test_file}: {e}")
        
        return None
    
    def _parse_junit_xml(self, xml_file: Path) -> Dict[str, Any]:
        """Parse JUnit XML test results."""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        if root.tag == 'testsuites':
            testsuite = root.find('testsuite')
            if testsuite is None:
                testsuite = root
        else:
            testsuite = root
        
        total_tests = int(testsuite.get('tests', 0))
        failures = int(testsuite.get('failures', 0))
        errors = int(testsuite.get('errors', 0))
        skipped = int(testsuite.get('skipped', 0))
        
        failed_tests = failures + errors
        passed_tests = total_tests - failed_tests - skipped
        
        # Extract failed test details
        failed_test_details = []
        for testcase in testsuite.findall('testcase'):
            failure = testcase.find('failure')
            error = testcase.find('error')
            
            if failure is not None or error is not None:
                failed_test_details.append({
                    'name': testcase.get('name', 'Unknown'),
                    'classname': testcase.get('classname', 'Unknown'),
                    'message': (failure or error).get('message', 'No message') if (failure or error) is not None else 'Unknown error'
                })
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'skipped_tests': skipped,
            'failed_test_details': failed_test_details
        }
    
    def _parse_json_results(self, json_file: Path) -> Dict[str, Any]:
        """Parse JSON test results."""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON formats
        if isinstance(data, dict):
            return {
                'total_tests': data.get('total', 0),
                'passed_tests': data.get('passed', 0),
                'failed_tests': data.get('failed', 0),
                'skipped_tests': data.get('skipped', 0),
                'failed_test_details': data.get('failures', [])
            }
        
        return None
    
    def _parse_coverage_file(self, coverage_file: Path) -> float:
        """Parse coverage file and return percentage."""
        try:
            if coverage_file.suffix == '.xml':
                tree = ET.parse(coverage_file)
                root = tree.getroot()
                line_rate = float(root.get('line-rate', 0))
                return line_rate * 100
            elif coverage_file.suffix == '.out':
                # Go coverage format
                with open(coverage_file, 'r') as f:
                    lines = f.readlines()
                
                total_statements = 0
                covered_statements = 0
                
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        statements = int(parts[1])
                        covered = int(parts[2])
                        total_statements += statements
                        covered_statements += covered
                
                if total_statements > 0:
                    return (covered_statements / total_statements) * 100
            elif coverage_file.suffix == '.json':
                with open(coverage_file, 'r') as f:
                    data = json.load(f)
                
                # Extract coverage from JSON format
                total_lines = 0
                covered_lines = 0
                
                for file_data in data.values():
                    if isinstance(file_data, dict) and 's' in file_data:
                        statements = file_data['s']
                        for hit_count in statements.values():
                            total_lines += 1
                            if hit_count > 0:
                                covered_lines += 1
                
                if total_lines > 0:
                    return (covered_lines / total_lines) * 100
        except Exception as e:
            print(f"Warning: Failed to parse coverage file {coverage_file}: {e}")
        
        return 0.0
    
    def _identify_test_type(self, filename: str) -> str:
        """Identify test type from filename."""
        filename_lower = filename.lower()
        
        if 'integration' in filename_lower:
            return 'integration'
        elif 'performance' in filename_lower or 'benchmark' in filename_lower:
            return 'performance'
        elif 'unit' in filename_lower:
            return 'unit'
        else:
            return 'unit'  # Default to unit tests
    
    def _extract_critical_failures(self, test_data: Dict[str, Any]) -> List[str]:
        """Extract critical failure messages."""
        critical_failures = []
        
        for failure in test_data.get('failed_test_details', []):
            # Focus on database-related failures
            message = failure.get('message', '').lower()
            if any(keyword in message for keyword in ['database', 'connection', 'timeout', 'sql']):
                critical_failures.append(f"{failure['name']}: {failure['message'][:100]}...")
        
        return critical_failures[:3]  # Limit to top 3 critical failures
    
    def _identify_critical_issues(self, summary: Dict[str, Any]) -> List[str]:
        """Identify critical issues from the summary."""
        issues = []
        
        if summary['overall_status'] == 'FAILED':
            issues.append(f"❌ {summary['failed_tests']} out of {summary['total_tests']} tests failed")
        
        if summary['coverage_percentage'] < 80:
            issues.append(f"📊 Low test coverage: {summary['coverage_percentage']:.1f}% (target: 80%)")
        
        # Check for services with no tests
        for service in self.services:
            if service not in summary['services']:
                issues.append(f"⚠️ No test results found for {service} service")
        
        # Check for critical database test failures
        for service, service_data in summary['services'].items():
            if service_data.get('critical_failures'):
                issues.append(f"🗄️ Database test failures in {service} service")
        
        return issues
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on the summary."""
        recommendations = []
        
        if summary['overall_status'] == 'FAILED':
            recommendations.append("Fix failing tests before merging")
        
        if summary['coverage_percentage'] < 80:
            recommendations.append("Add more unit tests to improve coverage")
        
        # Service-specific recommendations
        for service, service_data in summary['services'].items():
            if service_data['status'] == 'FAILED':
                if service_data.get('critical_failures'):
                    recommendations.append(f"Review database connectivity issues in {service}")
                else:
                    recommendations.append(f"Fix failing tests in {service} service")
            
            if service_data.get('coverage', 0) < 80:
                recommendations.append(f"Improve test coverage for {service} service")
        
        return recommendations
    
    def generate_github_summary(self, summary: Dict[str, Any]) -> str:
        """Generate GitHub Actions summary format."""
        status_emoji = "✅" if summary['overall_status'] == 'PASSED' else "❌"
        
        github_summary = f"""## {status_emoji} Database Test Results

### 📊 Overall Summary
- **Status**: {summary['overall_status']}
- **Tests**: {summary['passed_tests']}/{summary['total_tests']} passed
- **Success Rate**: {summary.get('success_rate', 0):.1f}%
- **Coverage**: {summary['coverage_percentage']:.1f}%

### 🔧 Service Results
"""
        
        for service, service_data in summary['services'].items():
            service_emoji = "✅" if service_data['status'] == 'PASSED' else "❌"
            github_summary += f"- **{service.title()}**: {service_emoji} {service_data['passed_tests']}/{service_data['total_tests']} tests, {service_data['coverage']:.1f}% coverage\n"
        
        if summary['issues']:
            github_summary += "\n### ⚠️ Issues\n"
            for issue in summary['issues']:
                github_summary += f"- {issue}\n"
        
        if summary['recommendations']:
            github_summary += "\n### 💡 Recommendations\n"
            for rec in summary['recommendations']:
                github_summary += f"- {rec}\n"
        
        return github_summary
    
    def generate_pr_comment(self, summary: Dict[str, Any]) -> str:
        """Generate PR comment format."""
        status_emoji = "✅" if summary['overall_status'] == 'PASSED' else "❌"
        
        pr_comment = f"""## {status_emoji} Database Testing Results

| Service | Status | Tests | Coverage |
|---------|--------|-------|----------|
"""
        
        for service, service_data in summary['services'].items():
            status_emoji = "✅" if service_data['status'] == 'PASSED' else "❌"
            pr_comment += f"| {service.title()} | {status_emoji} | {service_data['passed_tests']}/{service_data['total_tests']} | {service_data['coverage']:.1f}% |\n"
        
        pr_comment += f"\n**Overall**: {summary['passed_tests']}/{summary['total_tests']} tests passed ({summary.get('success_rate', 0):.1f}%)\n"
        
        if summary['overall_status'] == 'FAILED':
            pr_comment += "\n❌ **Action Required**: Fix failing tests before merging.\n"
        else:
            pr_comment += "\n✅ **All database tests passed!** Ready for review.\n"
        
        return pr_comment


def main():
    parser = argparse.ArgumentParser(description='Generate test summary for CI/CD')
    parser.add_argument('--results-dir', required=True, help='Directory containing test results')
    parser.add_argument('--format', choices=['github', 'pr', 'json'], default='github', 
                       help='Output format')
    parser.add_argument('--output', help='Output file (default: stdout)')
    
    args = parser.parse_args()
    
    generator = TestSummaryGenerator(args.results_dir)
    summary = generator.generate_summary()
    
    # Generate output based on format
    if args.format == 'github':
        output = generator.generate_github_summary(summary)
    elif args.format == 'pr':
        output = generator.generate_pr_comment(summary)
    elif args.format == 'json':
        output = json.dumps(summary, indent=2)
    
    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)
    
    # Exit with appropriate code
    sys.exit(0 if summary['overall_status'] == 'PASSED' else 1)


if __name__ == '__main__':
    main()