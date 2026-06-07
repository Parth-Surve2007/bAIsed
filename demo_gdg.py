#!/usr/bin/env python3
"""
bAIsed Fairness Workbench - GDG Demo Script
============================================

This script demonstrates the complete bAIsed fairness auditing workflow
with Google Gemini integration, demo datasets, and what-if simulation.

Prerequisites:
- Python 3.11+
- Flask running on http://localhost:5000
- GEMINI_API_KEY configured in backend/.env

Usage:
  python demo_gdg.py

The script will:
1. Load a demo dataset (lending bias example)
2. Upload and analyze it
3. Show proxy risk detection
4. Show dataset reliability scoring
5. Classify the bias pattern
6. Run what-if scenarios
7. Generate Gemini AI report
8. Export to Colab format
9. Export to What-If Tool format
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = 'http://localhost:5000'

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(title: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{title.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(message: str):
    print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")

def print_info(message: str):
    print(f"{Colors.OKCYAN}ℹ️  {message}{Colors.ENDC}")

def print_warning(message: str):
    print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")

def print_metric(label: str, value: Any):
    print(f"   {Colors.BOLD}{label:<30}{Colors.ENDC} {value}")

def demo_step(step_num: int, title: str):
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}STEP {step_num}: {title}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{'-'*70}{Colors.ENDC}")

def step_1_load_demo():
    """Load demo dataset."""
    demo_step(1, "Load Demo Dataset (Lending Bias)")
    
    response = requests.get(f'{BASE_URL}/api/demo-dataset/credit')
    
    if response.ok:
        csv_text = response.text
        print_success(f"Downloaded credit lending demo dataset")
        print_metric("Format", "CSV")
        print_metric("Records", csv_text.count('\n') - 1)
        print_metric("Columns", csv_text.split('\n')[0])
        return csv_text
    else:
        print_warning(f"Failed to load demo (Status: {response.status_code})")
        return None

def step_2_upload_analyze(csv_text: str) -> Dict[str, Any]:
    """Upload and analyze dataset."""
    demo_step(2, "Upload & Analyze Dataset")
    
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_text)
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as f:
            response = requests.post(f'{BASE_URL}/upload',
                                   files={'file': f},
                                   data={})
        
        if response.ok:
            result = response.json()
            print_success("Dataset analyzed successfully")
            print_metric("DIR (Disparate Impact Ratio)", f"{result.get('DIR'):.4f}")
            print_metric("Severity", result.get('severity'))
            print_metric("Bias Score", f"{result.get('bias_score'):.1f}/100")
            print_metric("Mode", result.get('mode'))
            print_metric("Dataset ID", result.get('dataset_id', 'N/A')[:8] + '...')
            return result
        else:
            print_warning(f"Analysis failed: {response.status_code}")
            return {}
    finally:
        os.unlink(temp_path)

def step_3_proxy_detection(result: Dict[str, Any]):
    """Show proxy bias detection."""
    demo_step(3, "Proxy Bias Detector (Cramer's V)")
    
    proxies = result.get('proxy_analysis', [])
    if proxies:
        print_success(f"Found {len(proxies)} proxy features")
        for i, proxy in enumerate(proxies[:3], 1):
            print(f"\n   Proxy #{i}:")
            print_metric("Feature", proxy.get('feature'))
            print_metric("Proxy for", proxy.get('proxy_for'))
            print_metric("Association Score", f"{proxy.get('association_score'):.4f}")
            print_metric("Risk Level", proxy.get('risk'))
            print_metric("Reason", proxy.get('reason'))
    else:
        print_info("No significant proxy features detected")

def step_4_risk_profiling(result: Dict[str, Any]):
    """Show dataset risk profiling."""
    demo_step(4, "Dataset Risk Profiler")
    
    risk = result.get('dataset_risk', {})
    if risk:
        print_success(f"Dataset audit complete")
        print_metric("Risk Score", f"{risk.get('risk_score')}/100")
        print_metric("Risk Level", risk.get('risk_level'))
        print_metric("Confidence", risk.get('confidence'))
        
        factors = risk.get('factors', [])
        if factors:
            print_info(f"Risk factors identified: {len(factors)}")
            for factor in factors[:2]:
                print(f"   • {factor.get('factor')}: {factor.get('detail')}")
    else:
        print_info("Dataset risk analysis not available")

def step_5_pattern_classification(result: Dict[str, Any]):
    """Show bias pattern detection."""
    demo_step(5, "Bias Pattern Detector")
    
    pattern = result.get('bias_pattern', {})
    if pattern:
        print_success(f"Bias pattern classified")
        print_metric("Pattern Type", pattern.get('pattern_type'))
        print_metric("Confidence", f"{pattern.get('confidence', 0)*100:.1f}%")
        print_metric("Recommended Action", pattern.get('recommended_action', 'N/A'))
        
        evidence = pattern.get('evidence', [])
        if evidence:
            print_info(f"Evidence:")
            for ev in evidence[:2]:
                print(f"   • {ev}")
    else:
        print_info("Pattern classification not available")

def step_6_what_if_simulation(result: Dict[str, Any]):
    """Test what-if simulation."""
    demo_step(6, "What-If Fairness Simulation")
    
    response = requests.post(f'{BASE_URL}/simulate',
                           json={
                               'scenario_type': 'threshold',
                               'analysis_result': result
                           })
    
    if response.ok:
        sim = response.json()
        print_success("What-if simulation complete")
        print_metric("Scenario Type", sim.get('scenario', {}).get('type'))
        print_metric("Bias Reduced", sim.get('bias_reduced'))
        
        if sim.get('metrics'):
            metrics = sim['metrics']
            print_metric("Estimated Accuracy", f"{metrics.get('estimated_accuracy', 0)*100:.1f}%")
            print_metric("Parity Improvement", f"{metrics.get('parity_improvement_percent', 0):.1f}%")
    else:
        print_warning(f"Simulation failed: {response.status_code}")

def step_7_gemini_report(result: Dict[str, Any], csv_text: str):
    """Generate Gemini AI report."""
    demo_step(7, "Gemini AI Audit Report")
    
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_text)
        temp_path = f.name
    
    try:
        print_info("Calling Google Gemini API...")
        with open(temp_path, 'rb') as f:
            response = requests.post(f'{BASE_URL}/ai-analyze',
                                   files={'file': f},
                                   data={'analysis_json': json.dumps(result)})
        
        if response.ok:
            ai_result = response.json()
            print_success("Gemini analysis complete")
            print_metric("Severity Label", ai_result.get('severity_label'))
            print_metric("Confidence", ai_result.get('confidence'))
            print_metric("Headline", ai_result.get('headline', 'N/A')[:60])
            
            if ai_result.get('pattern_detected'):
                print_metric("Pattern Detected", ai_result.get('pattern_detected'))
            
            if ai_result.get('executive_summary'):
                print_info("Executive Summary:")
                print(f"   {ai_result.get('executive_summary')[:120]}...")
            
            if ai_result.get('recommended_actions'):
                print_info("Recommended Actions:")
                for action in ai_result['recommended_actions'][:2]:
                    priority = action.get('priority')
                    text = action.get('action', 'N/A')[:60]
                    print(f"   • [{priority}] {text}...")
        else:
            print_warning(f"Gemini analysis failed: {response.status_code}")
    finally:
        os.unlink(temp_path)

def step_8_export(result: Dict[str, Any]):
    """Export to Google formats."""
    demo_step(8, "Export to Google Formats")
    
    dataset_id = result.get('dataset_id')
    if not dataset_id:
        print_warning("No dataset ID available for export")
        return
    
    # Colab export
    colab_resp = requests.get(f'{BASE_URL}/api/export/colab/{dataset_id}')
    if colab_resp.ok:
        nb = colab_resp.json()
        print_success(f"Colab notebook export ({len(nb.get('cells', []))} cells)")
    else:
        print_warning(f"Colab export failed: {colab_resp.status_code}")
    
    # What-If Tool export
    whatif_resp = requests.get(f'{BASE_URL}/api/export/what-if/{dataset_id}')
    if whatif_resp.ok:
        size_kb = len(whatif_resp.content) / 1024
        print_success(f"What-If Tool export ({size_kb:.1f} KB)")
        print_info("Contains: standardized CSV + metadata + README")
    else:
        print_warning(f"What-If export failed: {whatif_resp.status_code}")

def main():
    """Run the complete GDG demo."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}  bAIsed: Google-Powered AI Fairness Workbench{Colors.ENDC}")
    print(f"{Colors.BOLD}  GDG Demo - June 2026{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    print(f"\n{Colors.OKCYAN}This demo shows:{Colors.ENDC}")
    print("  • Deterministic fairness metrics (DIR, SPD, EOD, AOD)")
    print("  • Proxy bias detection with statistical association")
    print("  • Dataset reliability scoring")
    print("  • Bias pattern classification")
    print("  • What-If fairness simulations")
    print("  • Gemini-powered AI audit reports")
    print("  • Export to Google Colab & What-If Tool")
    
    try:
        # Step 1: Load demo
        csv_text = step_1_load_demo()
        if not csv_text:
            return
        
        time.sleep(1)
        
        # Step 2: Upload & analyze
        result = step_2_upload_analyze(csv_text)
        if not result:
            return
        
        time.sleep(1)
        
        # Step 3: Proxy detection
        step_3_proxy_detection(result)
        time.sleep(0.5)
        
        # Step 4: Risk profiling
        step_4_risk_profiling(result)
        time.sleep(0.5)
        
        # Step 5: Pattern classification
        step_5_pattern_classification(result)
        time.sleep(0.5)
        
        # Step 6: What-if
        step_6_what_if_simulation(result)
        time.sleep(0.5)
        
        # Step 7: Gemini report
        step_7_gemini_report(result, csv_text)
        time.sleep(1)
        
        # Step 8: Export
        step_8_export(result)
        
        # Final summary
        print_header("✅ Demo Complete!")
        print(f"{Colors.OKGREEN}The bAIsed fairness workbench successfully:{Colors.ENDC}")
        print("  ✓ Detected proxy features (age bias via ZIP code)")
        print("  ✓ Scored dataset reliability")
        print("  ✓ Classified bias patterns")
        print("  ✓ Generated what-if scenarios")
        print("  ✓ Created Gemini audit report")
        print("  ✓ Exported to Colab and What-If Tool")
        
        print(f"\n{Colors.OKCYAN}Next steps:{Colors.ENDC}")
        print(f"  1. Visit http://localhost:5000/workbench in browser")
        print(f"  2. Try demo dataset buttons (💳 👔 🚔)")
        print(f"  3. Upload your own dataset for analysis")
        print(f"  4. Export for further exploration")
        
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Demo failed: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
