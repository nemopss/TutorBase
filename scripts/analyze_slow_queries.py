#!/usr/bin/env python3
"""
Analyze slow query logs and generate performance report.
Helps identify performance bottlenecks and optimization opportunities.
"""
import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class SlowQueryAnalyzer:
    """Analyzes slow query logs and generates reports."""
    
    def __init__(self):
        self.queries: List[Dict] = []
        self.by_tenant: Dict[int, List[Dict]] = defaultdict(list)
        self.by_endpoint: Dict[str, List[Dict]] = defaultdict(list)
        self.by_severity: Dict[str, List[Dict]] = defaultdict(list)
    
    def parse_log_line(self, line: str) -> Dict | None:
        """Parse a log line and extract slow query information."""
        # Look for slow query log entries
        if "Slow query detected" not in line:
            return None
        
        try:
            # Extract JSON extra data if present
            if "extra={" in line:
                extra_start = line.index("extra={")
                extra_str = line[extra_start + 6:]
                # Simple parsing - in production, use proper JSON parsing
                
                # Extract key fields using regex
                duration_match = re.search(r"duration_ms['\"]:\s*([0-9.]+)", extra_str)
                tenant_match = re.search(r"tenant_id['\"]:\s*([0-9]+|None)", extra_str)
                path_match = re.search(r"path['\"]:\s*['\"]([^'\"]+)", extra_str)
                severity_match = re.search(r"severity['\"]:\s*['\"]([^'\"]+)", extra_str)
                
                if duration_match and path_match:
                    tenant_id = None
                    if tenant_match and tenant_match.group(1) != "None":
                        tenant_id = int(tenant_match.group(1))
                    
                    return {
                        "duration_ms": float(duration_match.group(1)),
                        "tenant_id": tenant_id,
                        "path": path_match.group(1),
                        "severity": severity_match.group(1) if severity_match else "UNKNOWN",
                        "timestamp": datetime.now().isoformat(),  # Simplified
                    }
        except Exception as e:
            print(f"Error parsing line: {e}")
            return None
        
        return None
    
    def analyze_file(self, log_file: Path):
        """Analyze a log file for slow queries."""
        print(f"Analyzing {log_file}...")
        
        with open(log_file, 'r') as f:
            for line in f:
                query_data = self.parse_log_line(line)
                if query_data:
                    self.queries.append(query_data)
                    
                    # Categorize
                    if query_data['tenant_id']:
                        self.by_tenant[query_data['tenant_id']].append(query_data)
                    
                    self.by_endpoint[query_data['path']].append(query_data)
                    self.by_severity[query_data['severity']].append(query_data)
        
        print(f"Found {len(self.queries)} slow queries")
    
    def generate_report(self) -> str:
        """Generate a performance report."""
        if not self.queries:
            return "No slow queries found."
        
        report = []
        report.append("=" * 80)
        report.append("SLOW QUERY ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Summary
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total slow queries: {len(self.queries)}")
        report.append(f"Unique tenants affected: {len(self.by_tenant)}")
        report.append(f"Unique endpoints affected: {len(self.by_endpoint)}")
        report.append("")
        
        # By severity
        report.append("BY SEVERITY")
        report.append("-" * 80)
        for severity in ["CRITICAL", "HIGH", "MEDIUM"]:
            count = len(self.by_severity.get(severity, []))
            if count > 0:
                report.append(f"{severity}: {count} queries")
        report.append("")
        
        # Top slow endpoints
        report.append("TOP 10 SLOWEST ENDPOINTS")
        report.append("-" * 80)
        endpoint_stats = []
        for endpoint, queries in self.by_endpoint.items():
            avg_duration = sum(q['duration_ms'] for q in queries) / len(queries)
            max_duration = max(q['duration_ms'] for q in queries)
            endpoint_stats.append({
                'endpoint': endpoint,
                'count': len(queries),
                'avg_ms': avg_duration,
                'max_ms': max_duration,
            })
        
        endpoint_stats.sort(key=lambda x: x['avg_ms'], reverse=True)
        for stat in endpoint_stats[:10]:
            report.append(
                f"{stat['endpoint']}: "
                f"avg={stat['avg_ms']:.2f}ms, "
                f"max={stat['max_ms']:.2f}ms, "
                f"count={stat['count']}"
            )
        report.append("")
        
        # By tenant
        if self.by_tenant:
            report.append("TOP 10 TENANTS WITH SLOW QUERIES")
            report.append("-" * 80)
            tenant_stats = []
            for tenant_id, queries in self.by_tenant.items():
                avg_duration = sum(q['duration_ms'] for q in queries) / len(queries)
                tenant_stats.append({
                    'tenant_id': tenant_id,
                    'count': len(queries),
                    'avg_ms': avg_duration,
                })
            
            tenant_stats.sort(key=lambda x: x['count'], reverse=True)
            for stat in tenant_stats[:10]:
                report.append(
                    f"Tenant {stat['tenant_id']}: "
                    f"{stat['count']} slow queries, "
                    f"avg={stat['avg_ms']:.2f}ms"
                )
            report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS")
        report.append("-" * 80)
        
        critical_count = len(self.by_severity.get("CRITICAL", []))
        if critical_count > 0:
            report.append(f"⚠️  {critical_count} CRITICAL slow queries (>1s) - immediate action required!")
        
        high_count = len(self.by_severity.get("HIGH", []))
        if high_count > 0:
            report.append(f"⚠️  {high_count} HIGH severity queries (>500ms) - optimization recommended")
        
        # Check for specific patterns
        if any("/learners" in ep for ep in self.by_endpoint.keys()):
            report.append("• Consider adding indexes on learner queries")
        
        if any("/lessons" in ep for ep in self.by_endpoint.keys()):
            report.append("• Consider optimizing lesson queries with better indexes")
        
        if len(self.by_tenant) > 5:
            report.append("• Multiple tenants affected - check for systemic performance issues")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Analyze slow query logs")
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to log file to analyze"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for report (default: stdout)"
    )
    
    args = parser.parse_args()
    
    if not args.log_file.exists():
        print(f"Error: Log file not found: {args.log_file}")
        return 1
    
    analyzer = SlowQueryAnalyzer()
    analyzer.analyze_file(args.log_file)
    report = analyzer.generate_report()
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)
    
    return 0


if __name__ == "__main__":
    exit(main())
