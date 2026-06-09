import requests
import json

# Get demo dataset
response = requests.get('http://localhost:5000/api/demo-dataset/credit')
csv_text = response.text

# Save to temp file
import tempfile
import os
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    f.write(csv_text)
    temp_path = f.name

try:
    # Upload and analyze (let auto-detect find the columns)
    with open(temp_path, 'rb') as f:
        files = {'file': f}
        data = {}
        response = requests.post('http://localhost:5000/upload', files=files, data=data)
        
    result = response.json()
    print('Upload Status:', 'SUCCESS' if not result.get('error') else f'ERROR: {result.get("error")}')
    print('Dataset ID:', result.get('dataset_id', 'N/A'))
    print('Mode:', result.get('mode', 'N/A'))
    print('Severity:', result.get('severity', 'N/A'))
    print('DIR:', result.get('DIR', 'N/A'))
    print('Has proxy_analysis:', 'proxy_analysis' in result)
    print('Has dataset_risk:', 'dataset_risk' in result)
    print('Has bias_pattern:', 'bias_pattern' in result)
    print()
    print('Sample proxy finding:', json.dumps(result.get('proxy_analysis', [{}])[0], indent=2)[:200])
finally:
    os.unlink(temp_path)
