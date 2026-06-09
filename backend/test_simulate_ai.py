import requests
import json
import tempfile
import os

# Get demo dataset
response = requests.get('http://localhost:5000/api/demo-dataset/credit')
csv_text = response.text

# Save to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    f.write(csv_text)
    temp_path = f.name

try:
    # Upload and analyze
    with open(temp_path, 'rb') as f:
        files = {'file': f}
        response = requests.post('http://localhost:5000/upload', files=files, data={})
        
    result = response.json()
    dataset_id = result.get('dataset_id')
    
    print('=== SIMULATE ENDPOINT ===')
    # Test simulate
    sim_resp = requests.post('http://localhost:5000/simulate', json={
        'scenario_type': 'threshold',
        'analysis_result': result
    })
    
    if sim_resp.ok:
        sim_result = sim_resp.json()
        print('Status: SUCCESS')
        print('Scenario:', sim_result.get('scenario'))
        print('Bias reduced:', sim_result.get('bias_reduced'))
        print('New DIR:', sim_result.get('new_DIR'))
        print('Has simulations:', 'simulations' in sim_result)
    else:
        print('Status: ERROR', sim_resp.status_code)
    print()
    
    print('=== AI ANALYZE ENDPOINT ===')
    # Test AI analyze
    with open(temp_path, 'rb') as f:
        files = {'file': f}
        data = {'analysis_json': json.dumps(result)}
        ai_resp = requests.post('http://localhost:5000/ai-analyze', files=files, data=data)
    
    if ai_resp.ok:
        ai_result = ai_resp.json()
        print('Status: SUCCESS')
        print('Has severity_label:', 'severity_label' in ai_result)
        print('Has executive_summary:', 'executive_summary' in ai_result)
        print('Has pattern_detected:', 'pattern_detected' in ai_result)
        print('Has proxy_risks:', 'proxy_risks' in ai_result)
        if 'headline' in ai_result:
            print('Headline:', ai_result['headline'][:100])
    else:
        print('Status: ERROR', ai_resp.status_code)
        print('Error:', ai_resp.text[:200])
    
finally:
    os.unlink(temp_path)
