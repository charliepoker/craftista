#!/usr/bin/env python3
"""
Test Report Generator with Quality Gates Validation

This script generates comprehensive test reports by aggregating results
from all services and test types, and validates them against quality gates.
"""

import os
import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
import logging
import yaml
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestReportGenerator:
    """Generates comprehensive test reports from test results."""
    
    def __init__(self, results_dir: str, output_dir: str):
        """Initialize the report generator."""
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.services = ['catalogue', 'voting', 'recommendation', 'frontend']
        self.test_types = ['unit', 'integration', 'performance']
        
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        logger.info("Generating comprehensive test report...")
        
        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'results_directory': str(self.results_dir),
                'services_analyzed': self.services,
                'test_types': self.test_types
            },
            'summary': {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'skipped_tests': 0,
                'success_rate': 0.0,
                'total_duration': 0.0
            },
            'services': {},
            'coverage': {},
            'performance_metrics': {},
            'issues': []
        }
        
        # Analyze each service
        for service in self.services:
            service_results = self._analyze_service_results(service)
            if service_results:
                report['services'][service] = service_results
                
                # Update summary
                report['summary']['total_tests'] += service_results['summary']['total_tests']
                report['summary']['passed_tests'] += service_results['summary']['passed_tests']
                report['summary']['failed_tests'] += service_results['summary']['failed_tests']
                report['summary']['skipped_tests'] += service_results['summary']['skipped_tests']
                report['summary']['total_duration'] += service_results['summary']['total_duration']
        
        # Calculate success rate
        if report['summary']['total_tests'] > 0:
            report['summary']['success_rate'] = (
                report['summary']['passed_tests'] / report['summary']['total_tests'] * 100
            )
        
        # Generate coverage report
        report['coverage'] = self._generate_coverage_report()
        
        # Generate performance metrics
        report['performance_metrics'] = self._generate_performance_metrics()
        
        # Identify issues
        report['issues'] = self._identify_issues(report)
        
        return report
    
    def _analyze_service_results(self, service: str) -> Optional[Dict[str, Any]]:
        """Analyze test results for a specific service."""
        service_dir = self.results_dir / service
        if not service_dir.exists():
            logger.warning(f"No results directory found for service: {service}")
            return None
        
        service_report = {
            'name': service,
            'summary': {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'skipped_tests': 0,
                'success_rate': 0.0,
                'total_duration': 0.0
            },
            'test_types': {},
            'coverage': None,
            'issues': []
        }
        
        # Analyze each test type
        for test_type in self.test_types:
            test_results = self._analyze_test_type_results(service, test_type)
            if test_results:
                service_report['test_types'][test_type] = test_results
                
                # Update service summary
                service_report['summary']['total_tests'] += test_results['total_tests']
                service_report['summary']['passed_tests'] += test_results['passed_tests']
                service_report['summary']['failed_tests'] += test_results['failed_tests']
                service_report['summary']['skipped_tests'] += test_results['skipped_tests']
                service_report['summary']['total_duration'] += test_results['duration']
        
        # Calculate service success rate
        if service_report['summary']['total_tests'] > 0:
            service_report['summary']['success_rate'] = (
                service_report['summary']['passed_tests'] / 
                service_report['summary']['total_tests'] * 100
            )
        
        # Analyze coverage
        service_report['coverage'] = self._analyze_service_coverage(service)
        
        return service_report
    
    def _analyze_test_type_results(self, service: str, test_type: str) -> Optional[Dict[str, Any]]:
        """Analyze results for a specific test type."""
        service_dir = self.results_dir / service
        
        # Look for different result file formats
        result_files = [
            service_dir / f"{test_type}-junit.xml",
            service_dir / f"{test_type}-results.json",
            service_dir / "junit.xml",
            service_dir / f"{test_type}.xml"
        ]
        
        for result_file in result_files:
            if result_file.exists():
                if result_file.suffix == '.xml':
                    return self._parse_junit_xml(result_file)
                elif result_file.suffix == '.json':
                    return self._parse_json_results(result_file)
        
        logger.warning(f"No test results found for {service} {test_type}")
        return None
    
    def _parse_junit_xml(self, xml_file: Path) -> Dict[str, Any]:
        """Parse JUnit XML test results."""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Handle different JUnit XML formats
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
            duration = float(testsuite.get('time', 0))
            
            failed_tests = failures + errors
            passed_tests = total_tests - failed_tests - skipped
            
            # Extract individual test cases
            test_cases = []
            for testcase in testsuite.findall('testcase'):
                case_info = {
                    'name': testcase.get('name', 'Unknown'),
                    'classname': testcase.get('classname', 'Unknown'),
                    'time': float(testcase.get('time', 0)),
                    'status': 'passed'
                }
                
                if testcase.find('failure') is not None:
                    case_info['status'] = 'failed'
                    failure = testcase.find('failure')
                    case_info['failure_message'] = failure.get('message', '')
                    case_info['failure_type'] = failure.get('type', '')
                elif testcase.find('error') is not None:
                    case_info['status'] = 'error'
                    error = testcase.find('error')
                    case_info['error_message'] = error.get('message', '')
                    case_info['error_type'] = error.get('type', '')
                elif testcase.find('skipped') is not None:
                    case_info['status'] = 'skipped'
                
                test_cases.append(case_info)
            
            return {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'skipped_tests': skipped,
                'duration': duration,
                'test_cases': test_cases
            }
            
        except Exception as e:
            logger.error(f"Failed to parse JUnit XML {xml_file}: {e}")
            return None
    
    def _parse_json_results(self, json_file: Path) -> Dict[str, Any]:
        """Parse JSON test results."""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Handle different JSON formats (Go test output, Node.js, etc.)
            if isinstance(data, list):
                # Go test JSON format
                return self._parse_go_test_json(data)
            elif isinstance(data, dict):
                # Other JSON formats
                return self._parse_generic_json_results(data)
            
        except Exception as e:
            logger.error(f"Failed to parse JSON results {json_file}: {e}")
            return None
    
    def _parse_go_test_json(self, test_data: List[Dict]) -> Dict[str, Any]:
        """Parse Go test JSON output."""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        total_duration = 0.0
        test_cases = []
        
        for entry in test_data:
            if entry.get('Action') == 'run' and 'Test' in entry:
                total_tests += 1
                test_case = {
                    'name': entry.get('Test', 'Unknown'),
                    'package': entry.get('Package', 'Unknown'),
                    'time': 0.0,
                    'status': 'running'
                }
                test_cases.append(test_case)
            elif entry.get('Action') == 'pass' and 'Test' in entry:
                passed_tests += 1
                elapsed = entry.get('Elapsed', 0)
                total_duration += elapsed
                # Update corresponding test case
                for case in test_cases:
                    if case['name'] == entry.get('Test'):
                        case['status'] = 'passed'
                        case['time'] = elapsed
                        break
            elif entry.get('Action') == 'fail' and 'Test' in entry:
                failed_tests += 1
                elapsed = entry.get('Elapsed', 0)
                total_duration += elapsed
                # Update corresponding test case
                for case in test_cases:
                    if case['name'] == entry.get('Test'):
                        case['status'] = 'failed'
                        case['time'] = elapsed
                        break
            elif entry.get('Action') == 'skip' and 'Test' in entry:
                skipped_tests += 1
                # Update corresponding test case
                for case in test_cases:
                    if case['name'] == entry.get('Test'):
                        case['status'] = 'skipped'
                        break
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'skipped_tests': skipped_tests,
            'duration': total_duration,
            'test_cases': test_cases
        }
    
    def _parse_generic_json_results(self, data: Dict) -> Dict[str, Any]:
        """Parse generic JSON test results."""
        # This is a fallback for other JSON formats
        return {
            'total_tests': data.get('total', 0),
            'passed_tests': data.get('passed', 0),
            'failed_tests': data.get('failed', 0),
            'skipped_tests': data.get('skipped', 0),
            'duration': data.get('duration', 0.0),
            'test_cases': data.get('tests', [])
        }
    
    def _analyze_service_coverage(self, service: str) -> Optional[Dict[str, Any]]:
        """Analyze code coverage for a service."""
        service_dir = self.results_dir / service
        
        # Look for coverage files
        coverage_files = [
            service_dir / 'coverage.xml',
            service_dir / 'coverage' / 'coverage-final.json',
            service_dir / 'coverage.out'
        ]
        
        for coverage_file in coverage_files:
            if coverage_file.exists():
                if coverage_file.name == 'coverage.xml':
                    return self._parse_coverage_xml(coverage_file)
                elif coverage_file.name == 'coverage-final.json':
                    return self._parse_coverage_json(coverage_file)
                elif coverage_file.suffix == '.out':
                    return self._parse_go_coverage(coverage_file)
        
        return None
    
    def _parse_coverage_xml(self, xml_file: Path) -> Dict[str, Any]:
        """Parse XML coverage report."""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Extract coverage metrics
            coverage_data = {
                'line_rate': float(root.get('line-rate', 0)) * 100,
                'branch_rate': float(root.get('branch-rate', 0)) * 100,
                'lines_covered': int(root.get('lines-covered', 0)),
                'lines_valid': int(root.get('lines-valid', 0)),
                'branches_covered': int(root.get('branches-covered', 0)),
                'branches_valid': int(root.get('branches-valid', 0)),
                'packages': []
            }
            
            # Extract package-level coverage
            packages = root.find('packages')
            if packages is not None:
                for package in packages.findall('package'):
                    package_data = {
                        'name': package.get('name', 'Unknown'),
                        'line_rate': float(package.get('line-rate', 0)) * 100,
                        'branch_rate': float(package.get('branch-rate', 0)) * 100
                    }
                    coverage_data['packages'].append(package_data)
            
            return coverage_data
            
        except Exception as e:
            logger.error(f"Failed to parse coverage XML {xml_file}: {e}")
            return None
    
    def _parse_coverage_json(self, json_file: Path) -> Dict[str, Any]:
        """Parse JSON coverage report."""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract overall metrics
            total_lines = 0
            covered_lines = 0
            
            for file_path, file_data in data.items():
                if isinstance(file_data, dict) and 's' in file_data:
                    statements = file_data['s']
                    for line_num, hit_count in statements.items():
                        total_lines += 1
                        if hit_count > 0:
                            covered_lines += 1
            
            line_rate = (covered_lines / total_lines * 100) if total_lines > 0 else 0
            
            return {
                'line_rate': line_rate,
                'lines_covered': covered_lines,
                'lines_valid': total_lines,
                'files': len(data)
            }
            
        except Exception as e:
            logger.error(f"Failed to parse coverage JSON {json_file}: {e}")
            return None
    
    def _parse_go_coverage(self, coverage_file: Path) -> Dict[str, Any]:
        """Parse Go coverage output."""
        try:
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
            
            coverage_rate = (covered_statements / total_statements * 100) if total_statements > 0 else 0
            
            return {
                'line_rate': coverage_rate,
                'statements_covered': covered_statements,
                'statements_valid': total_statements
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Go coverage {coverage_file}: {e}")
            return None
    
    def _generate_coverage_report(self) -> Dict[str, Any]:
        """Generate overall coverage report."""
        coverage_report = {
            'overall_coverage': 0.0,
            'services': {},
            'summary': {
                'total_lines': 0,
                'covered_lines': 0,
                'services_with_coverage': 0
            }
        }
        
        total_coverage = 0.0
        services_with_coverage = 0
        
        for service in self.services:
            service_dir = self.results_dir / service
            coverage_data = self._analyze_service_coverage(service)
            
            if coverage_data:
                coverage_report['services'][service] = coverage_data
                total_coverage += coverage_data.get('line_rate', 0)
                services_with_coverage += 1
                
                # Update summary
                coverage_report['summary']['total_lines'] += coverage_data.get('lines_valid', 0)
                coverage_report['summary']['covered_lines'] += coverage_data.get('lines_covered', 0)
        
        coverage_report['summary']['services_with_coverage'] = services_with_coverage
        
        if services_with_coverage > 0:
            coverage_report['overall_coverage'] = total_coverage / services_with_coverage
        
        return coverage_report
    
    def _generate_performance_metrics(self) -> Dict[str, Any]:
        """Generate performance metrics report."""
        performance_report = {
            'summary': {
                'total_performance_tests': 0,
                'average_response_time': 0.0,
                'throughput_metrics': {},
                'resource_usage': {}
            },
            'services': {}
        }
        
        for service in self.services:
            service_perf = self._analyze_service_performance(service)
            if service_perf:
                performance_report['services'][service] = service_perf
                performance_report['summary']['total_performance_tests'] += service_perf.get('test_count', 0)
        
        return performance_report
    
    def _analyze_service_performance(self, service: str) -> Optional[Dict[str, Any]]:
        """Analyze performance metrics for a service."""
        service_dir = self.results_dir / service
        perf_file = service_dir / 'performance-junit.xml'
        
        if not perf_file.exists():
            return None
        
        perf_data = self._parse_junit_xml(perf_file)
        if not perf_data:
            return None
        
        # Extract performance-specific metrics
        performance_metrics = {
            'test_count': perf_data['total_tests'],
            'average_duration': perf_data['duration'] / perf_data['total_tests'] if perf_data['total_tests'] > 0 else 0,
            'total_duration': perf_data['duration'],
            'success_rate': (perf_data['passed_tests'] / perf_data['total_tests'] * 100) if perf_data['total_tests'] > 0 else 0,
            'slow_tests': []
        }
        
        # Identify slow tests (> 5 seconds)
        for test_case in perf_data.get('test_cases', []):
            if test_case.get('time', 0) > 5.0:
                performance_metrics['slow_tests'].append({
                    'name': test_case['name'],
                    'duration': test_case['time']
                })
        
        return performance_metrics
    
    def _identify_issues(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify issues from the test report."""
        issues = []
        
        # Check overall success rate
        if report['summary']['success_rate'] < 95:
            issues.append({
                'type': 'low_success_rate',
                'severity': 'high',
                'message': f"Overall test success rate is {report['summary']['success_rate']:.1f}% (< 95%)",
                'recommendation': 'Investigate and fix failing tests'
            })
        
        # Check coverage
        overall_coverage = report['coverage'].get('overall_coverage', 0)
        if overall_coverage < 80:
            issues.append({
                'type': 'low_coverage',
                'severity': 'medium',
                'message': f"Overall code coverage is {overall_coverage:.1f}% (< 80%)",
                'recommendation': 'Add more unit tests to improve coverage'
            })
        
        # Check for services with no tests
        for service in self.services:
            if service not in report['services']:
                issues.append({
                    'type': 'missing_tests',
                    'severity': 'high',
                    'message': f"No test results found for {service} service",
                    'recommendation': f'Ensure tests are running for {service} service'
                })
        
        # Check for performance issues
        for service, perf_data in report['performance_metrics']['services'].items():
            if perf_data.get('average_duration', 0) > 10:
                issues.append({
                    'type': 'slow_performance_tests',
                    'severity': 'medium',
                    'message': f"Performance tests for {service} are slow (avg: {perf_data['average_duration']:.1f}s)",
                    'recommendation': 'Optimize performance tests or infrastructure'
                })
        
        # Add quality gates validation
        quality_issues = self._validate_quality_gates(report)
        issues.extend(quality_issues)
        
        return issues

    def _validate_quality_gates(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate report against quality gates configuration."""
        issues = []
        
        # Try to load quality gates configuration
        quality_gates_path = Path(__file__).parent.parent.parent / '.github' / 'quality-gates.yml'
        if not quality_gates_path.exists():
            logger.warning("Quality gates configuration not found")
            return issues
        
        try:
            with open(quality_gates_path, 'r') as f:
                quality_config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load quality gates configuration: {e}")
            return issues
        
        # Validate coverage thresholds
        coverage_gates = quality_config.get('quality_gates', {}).get('coverage', {})
        for service in ['catalogue', 'voting', 'recommendation']:
            if service in report['services'] and service in coverage_gates:
                service_coverage = report['coverage']['services'].get(service, {})
                line_coverage = service_coverage.get('line_rate', 0)
                branch_coverage = service_coverage.get('branch_rate', 0)
                
                thresholds = coverage_gates[service]
                
                if line_coverage < thresholds.get('line_coverage', 80):
                    issues.append({
                        'type': 'quality_gate_failure',
                        'severity': 'high',
                        'message': f"{service}: Line coverage {line_coverage:.1f}% below quality gate {thresholds['line_coverage']}%",
                        'recommendation': f'Increase test coverage for {service} service'
                    })
                
                if branch_coverage < thresholds.get('branch_coverage', 75):
                    issues.append({
                        'type': 'quality_gate_failure',
                        'severity': 'medium',
                        'message': f"{service}: Branch coverage {branch_coverage:.1f}% below quality gate {thresholds['branch_coverage']}%",
                        'recommendation': f'Add more comprehensive tests for {service} service'
                    })
        
        # Validate test requirements
        test_requirements = quality_config.get('test_requirements', {})
        unit_test_min = test_requirements.get('unit_tests', {}).get('min_test_coverage', 85)
        
        if report['summary']['success_rate'] < 100:
            failed_ratio = (report['summary']['failed_tests'] / report['summary']['total_tests']) * 100
            if failed_ratio > 5:  # More than 5% failure rate
                issues.append({
                    'type': 'quality_gate_failure',
                    'severity': 'high',
                    'message': f"Test failure rate {failed_ratio:.1f}% exceeds acceptable threshold (5%)",
                    'recommendation': 'Fix failing tests before deployment'
                })
        
        # Validate deployment gates
        deployment_gates = quality_config.get('deployment_gates', {}).get('pre_deployment', [])
        for gate in deployment_gates:
            if 'Coverage thresholds met' in gate and report['coverage']['overall_coverage'] < 80:
                issues.append({
                    'type': 'deployment_gate_failure',
                    'severity': 'high',
                    'message': 'Deployment blocked: Coverage thresholds not met',
                    'recommendation': 'Increase overall test coverage before deployment'
                })
        
        return issues
    
    def generate_html_report(self, report: Dict[str, Any]) -> str:
        """Generate HTML report."""
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Craftista Test Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #007bff; }}
        .metric.success {{ border-left-color: #28a745; }}
        .metric.warning {{ border-left-color: #ffc107; }}
        .metric.danger {{ border-left-color: #dc3545; }}
        .metric-value {{ font-size: 2em; font-weight: bold; margin-bottom: 5px; }}
        .metric-label {{ color: #6c757d; font-size: 0.9em; }}
        .section {{ margin-bottom: 30px; }}
        .section-title {{ font-size: 1.5em; margin-bottom: 15px; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px; }}
        .service-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .service-card {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6; }}
        .service-name {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; color: #495057; }}
        .test-type {{ margin-bottom: 10px; padding: 10px; background-color: white; border-radius: 4px; }}
        .test-type-name {{ font-weight: bold; color: #007bff; }}
        .progress-bar {{ width: 100%; height: 20px; background-color: #e9ecef; border-radius: 10px; overflow: hidden; margin: 5px 0; }}
        .progress-fill {{ height: 100%; background-color: #28a745; transition: width 0.3s ease; }}
        .progress-fill.warning {{ background-color: #ffc107; }}
        .progress-fill.danger {{ background-color: #dc3545; }}
        .issues {{ background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 20px; }}
        .issue {{ margin-bottom: 10px; padding: 10px; border-left: 4px solid #ffc107; background-color: white; }}
        .issue.high {{ border-left-color: #dc3545; }}
        .issue.medium {{ border-left-color: #ffc107; }}
        .issue.low {{ border-left-color: #28a745; }}
        .coverage-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
        .coverage-item {{ background-color: white; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background-color: #f8f9fa; font-weight: 600; }}
        .status-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }}
        .status-passed {{ background-color: #d4edda; color: #155724; }}
        .status-failed {{ background-color: #f8d7da; color: #721c24; }}
        .status-skipped {{ background-color: #fff3cd; color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Craftista Microservices Test Report</h1>
            <p>Generated on {generated_at}</p>
        </div>

        <div class="section">
            <div class="summary">
                <div class="metric {success_class}">
                    <div class="metric-value">{total_tests}</div>
                    <div class="metric-label">Total Tests</div>
                </div>
                <div class="metric success">
                    <div class="metric-value">{passed_tests}</div>
                    <div class="metric-label">Passed</div>
                </div>
                <div class="metric {failed_class}">
                    <div class="metric-value">{failed_tests}</div>
                    <div class="metric-label">Failed</div>
                </div>
                <div class="metric {success_rate_class}">
                    <div class="metric-value">{success_rate:.1f}%</div>
                    <div class="metric-label">Success Rate</div>
                </div>
                <div class="metric {coverage_class}">
                    <div class="metric-value">{overall_coverage:.1f}%</div>
                    <div class="metric-label">Coverage</div>
                </div>
            </div>
        </div>

        {issues_section}

        <div class="section">
            <h2 class="section-title">📊 Service Results</h2>
            <div class="service-grid">
                {services_content}
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">📈 Coverage Report</h2>
            <div class="coverage-grid">
                {coverage_content}
            </div>
        </div>

        {performance_section}
    </div>
</body>
</html>
        """
        
        # Prepare template variables
        template_vars = {
            'generated_at': report['metadata']['generated_at'],
            'total_tests': report['summary']['total_tests'],
            'passed_tests': report['summary']['passed_tests'],
            'failed_tests': report['summary']['failed_tests'],
            'success_rate': report['summary']['success_rate'],
            'overall_coverage': report['coverage']['overall_coverage'],
            'success_class': 'success' if report['summary']['success_rate'] >= 95 else 'warning' if report['summary']['success_rate'] >= 80 else 'danger',
            'failed_class': 'success' if report['summary']['failed_tests'] == 0 else 'danger',
            'success_rate_class': 'success' if report['summary']['success_rate'] >= 95 else 'warning' if report['summary']['success_rate'] >= 80 else 'danger',
            'coverage_class': 'success' if report['coverage']['overall_coverage'] >= 80 else 'warning' if report['coverage']['overall_coverage'] >= 60 else 'danger',
        }
        
        # Generate issues section
        if report['issues']:
            issues_html = '<div class="section"><h2 class="section-title">⚠️ Issues</h2><div class="issues">'
            for issue in report['issues']:
                issues_html += f'''
                <div class="issue {issue['severity']}">
                    <strong>{issue['type'].replace('_', ' ').title()}:</strong> {issue['message']}<br>
                    <em>Recommendation: {issue['recommendation']}</em>
                </div>
                '''
            issues_html += '</div></div>'
            template_vars['issues_section'] = issues_html
        else:
            template_vars['issues_section'] = ''
        
        # Generate services content
        services_html = ''
        for service_name, service_data in report['services'].items():
            service_html = f'''
            <div class="service-card">
                <div class="service-name">🔧 {service_name.title()} Service</div>
                <div class="progress-bar">
                    <div class="progress-fill {'success' if service_data['summary']['success_rate'] >= 95 else 'warning' if service_data['summary']['success_rate'] >= 80 else 'danger'}" 
                         style="width: {service_data['summary']['success_rate']}%"></div>
                </div>
                <div style="margin-top: 10px;">
                    <strong>Success Rate:</strong> {service_data['summary']['success_rate']:.1f}%<br>
                    <strong>Tests:</strong> {service_data['summary']['passed_tests']}/{service_data['summary']['total_tests']}<br>
                    <strong>Duration:</strong> {service_data['summary']['total_duration']:.2f}s
                </div>
            '''
            
            for test_type, test_data in service_data['test_types'].items():
                service_html += f'''
                <div class="test-type">
                    <div class="test-type-name">{test_type.title()} Tests</div>
                    <div>Passed: {test_data['passed_tests']}, Failed: {test_data['failed_tests']}, Duration: {test_data['duration']:.2f}s</div>
                </div>
                '''
            
            service_html += '</div>'
            services_html += service_html
        
        template_vars['services_content'] = services_html
        
        # Generate coverage content
        coverage_html = ''
        for service_name, coverage_data in report['coverage']['services'].items():
            coverage_html += f'''
            <div class="coverage-item">
                <h4>{service_name.title()}</h4>
                <div class="progress-bar">
                    <div class="progress-fill {'success' if coverage_data['line_rate'] >= 80 else 'warning' if coverage_data['line_rate'] >= 60 else 'danger'}" 
                         style="width: {coverage_data['line_rate']}%"></div>
                </div>
                <div style="margin-top: 5px;">
                    <strong>{coverage_data['line_rate']:.1f}%</strong> line coverage<br>
                    {coverage_data.get('lines_covered', 0)}/{coverage_data.get('lines_valid', 0)} lines
                </div>
            </div>
            '''
        
        template_vars['coverage_content'] = coverage_html
        
        # Generate performance section
        if report['performance_metrics']['services']:
            perf_html = '<div class="section"><h2 class="section-title">⚡ Performance Metrics</h2>'
            perf_html += '<table><thead><tr><th>Service</th><th>Tests</th><th>Avg Duration</th><th>Success Rate</th><th>Slow Tests</th></tr></thead><tbody>'
            
            for service_name, perf_data in report['performance_metrics']['services'].items():
                slow_tests_count = len(perf_data.get('slow_tests', []))
                perf_html += f'''
                <tr>
                    <td>{service_name.title()}</td>
                    <td>{perf_data.get('test_count', 0)}</td>
                    <td>{perf_data.get('average_duration', 0):.2f}s</td>
                    <td>{perf_data.get('success_rate', 0):.1f}%</td>
                    <td>{slow_tests_count}</td>
                </tr>
                '''
            
            perf_html += '</tbody></table></div>'
            template_vars['performance_section'] = perf_html
        else:
            template_vars['performance_section'] = ''
        
        return html_template.format(**template_vars)
    
    def save_reports(self, report: Dict[str, Any]) -> None:
        """Save reports in multiple formats."""
        # Save JSON report
        json_file = self.output_dir / 'test-report.json'
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"JSON report saved to {json_file}")
        
        # Save HTML report
        html_content = self.generate_html_report(report)
        html_file = self.output_dir / 'test-report.html'
        with open(html_file, 'w') as f:
            f.write(html_content)
        logger.info(f"HTML report saved to {html_file}")
        
        # Save summary text report
        summary_file = self.output_dir / 'test-summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"Craftista Test Report Summary\n")
            f.write(f"Generated: {report['metadata']['generated_at']}\n\n")
            f.write(f"Overall Results:\n")
            f.write(f"  Total Tests: {report['summary']['total_tests']}\n")
            f.write(f"  Passed: {report['summary']['passed_tests']}\n")
            f.write(f"  Failed: {report['summary']['failed_tests']}\n")
            f.write(f"  Success Rate: {report['summary']['success_rate']:.1f}%\n")
            f.write(f"  Overall Coverage: {report['coverage']['overall_coverage']:.1f}%\n\n")
            
            if report['issues']:
                f.write(f"Issues Found ({len(report['issues'])}):\n")
                for issue in report['issues']:
                    f.write(f"  - {issue['message']}\n")
            else:
                f.write("No issues found.\n")
        
        logger.info(f"Summary report saved to {summary_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Generate comprehensive test reports')
    parser.add_argument('--results-dir', default='./test-results',
                       help='Directory containing test results')
    parser.add_argument('--output-dir', default='./test-reports',
                       help='Directory to save generated reports')
    
    args = parser.parse_args()
    
    # Generate report
    generator = TestReportGenerator(args.results_dir, args.output_dir)
    report = generator.generate_comprehensive_report()
    generator.save_reports(report)
    
    # Print summary
    print(f"\n📊 Test Report Summary:")
    print(f"   Total Tests: {report['summary']['total_tests']}")
    print(f"   Success Rate: {report['summary']['success_rate']:.1f}%")
    print(f"   Coverage: {report['coverage']['overall_coverage']:.1f}%")
    print(f"   Issues: {len(report['issues'])}")
    print(f"\n📁 Reports saved to: {args.output_dir}")
    
    # Exit with appropriate code
    if report['summary']['failed_tests'] > 0 or len(report['issues']) > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()