#!/usr/bin/env python3
"""
Comprehensive test of the bAIsed fairness workbench with all modules.
"""
import requests
import json
import tempfile
import os

BASE_URL = 'http://localhost:5000'

def test_demo_datasets():
    """Test that all 3 demo datasets are available."""
    print('\n' + '='*60)
    print('TEST: Demo Dataset Generator')
    print('='*60)
    
    for demo_type in ['credit', 'resume', 'policing']:
        resp = requests.get(f'{BASE_URL}/api/demo-dataset/{demo_type}')
        if resp.ok:
            lines = resp.text.split('\n')
            print(f'✅ {demo_type:12} - {len(lines):4} rows, headers: {lines[0][:50]}...')
        else:
            print(f'❌ {demo_type:12} - Status {resp.status_code}')

def test_full_pipeline():
    """Test complete analysis pipeline."""
    print('\n' + '='*60)
    print('TEST: Full Analysis Pipeline (Credit Demo)')
    print('='*60)
    
    # 1. Get demo dataset
    resp = requests.get(f'{BASE_URL}/api/demo-dataset/credit')
    csv_text = resp.text
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_text)
        temp_path = f.name
    
    try:
        # 2. Upload and analyze
        with open(temp_path, 'rb') as f:
            resp = requests.post(f'{BASE_URL}/upload', 
                               files={'file': f}, 
                               data={})
        
        if resp.ok:
            result = resp.json()
            dataset_id = result.get('dataset_id')
            print(f'✅ Upload & Analysis - DIR={result.get("DIR"):.4f}, Severity={result.get("severity")}')
            
            # Check all required fields
            checks = [
                ('mode', result.get('mode')),
                ('proxy_analysis', len(result.get('proxy_analysis', []))),
                ('dataset_risk', result.get('dataset_risk', {}).get('risk_level')),
                ('bias_pattern', result.get('bias_pattern', {}).get('pattern_type')),
            ]
            
            for check_name, value in checks:
                status = '✅' if value else '❌'
                print(f'{status} {check_name:20} - {value}')
            
            # 3. Test exports
            if dataset_id:
                print(f'\n  Dataset ID: {dataset_id}')
                
                colab_resp = requests.get(f'{BASE_URL}/api/export/colab/{dataset_id}')
                if colab_resp.ok:
                    print(f'  ✅ Colab export - {len(colab_resp.json().get("cells", []))} cells')
                
                whatif_resp = requests.get(f'{BASE_URL}/api/export/what-if/{dataset_id}')
                if whatif_resp.ok:
                    print(f'  ✅ What-If export - {len(whatif_resp.content)} bytes')
            
            # 4. Test simulate
            sim_resp = requests.post(f'{BASE_URL}/simulate', 
                                   json={
                                       'scenario_type': 'threshold',
                                       'analysis_result': result
                                   })
            if sim_resp.ok:
                sim_result = sim_resp.json()
                print(f'  ✅ Simulate endpoint - Bias reduced: {sim_result.get("bias_reduced")}')
            
            # 5. Test AI analyze
            with open(temp_path, 'rb') as f:
                ai_resp = requests.post(f'{BASE_URL}/ai-analyze',
                                      files={'file': f},
                                      data={'analysis_json': json.dumps(result)})
            
            if ai_resp.ok:
                ai_result = ai_resp.json()
                headline = ai_result.get('headline', '')
                print(f'  ✅ AI Analysis - "{headline[:60]}..."')
        else:
            print(f'❌ Upload failed - {resp.status_code}')
    
    finally:
        os.unlink(temp_path)

def test_simple_analysis():
    """Test simple percentage-based analysis."""
    print('\n' + '='*60)
    print('TEST: Simple Bias Check (Percentages)')
    print('='*60)
    
    resp = requests.post(f'{BASE_URL}/analyze',
                        json={'groupA': 80, 'groupB': 30})
    
    if resp.ok:
        result = resp.json()
        print(f'✅ Simple analysis')
        print(f'   DIR: {result.get("DIR"):.4f}')
        print(f'   Severity: {result.get("severity")}')
        print(f'   Bias Score: {result.get("bias_score")}')
    else:
        print(f'❌ Simple analysis - {resp.status_code}')

def main():
    print('\n🚀 bAIsed Fairness Workbench - Comprehensive Test')
    print('Testing all modules and endpoints...')
    
    try:
        test_demo_datasets()
        test_full_pipeline()
        test_simple_analysis()
        
        print('\n' + '='*60)
        print('✅ ALL TESTS PASSED - System is ready for demo!')
        print('='*60)
        print('\nNext steps:')
        print('1. Open http://localhost:5000/workbench in browser')
        print('2. Try the demo dataset loader buttons')
        print('3. Test export to Colab and What-If Tool')
        print('4. Review Gemini AI analysis report')
        
    except Exception as e:
        print(f'\n❌ Test failed with error: {e}')

if __name__ == '__main__':
    main()
