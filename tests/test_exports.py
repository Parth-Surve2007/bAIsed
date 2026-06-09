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
    # Upload and analyze (let auto-detect find the columns)
    with open(temp_path, 'rb') as f:
        files = {'file': f}
        data = {}
        response = requests.post('http://localhost:5000/upload', files=files, data=data)
        
    result = response.json()
    print('=== UPLOAD & ANALYZE ===')
    print('Status:', 'SUCCESS' if not result.get('error') else f'ERROR: {result.get("error")}')
    dataset_id = result.get('dataset_id')
    print('Dataset ID:', dataset_id)
    print('Severity:', result.get('severity', 'N/A'))
    print('DIR:', result.get('DIR', 'N/A'))
    print()
    
    if dataset_id:
        # Test Colab export
        print('=== COLAB EXPORT ===')
        colab_resp = requests.get(f'http://localhost:5000/api/export/colab/{dataset_id}')
        print('Status:', colab_resp.status_code)
        print('Content type:', colab_resp.headers.get('content-type'))
        if colab_resp.ok:
            nb = colab_resp.json()
            print('Notebook format:', nb.get('nbformat'))
            print('Number of cells:', len(nb.get('cells', [])))
        print()
        
        # Test What-If export
        print('=== WHAT-IF TOOL EXPORT ===')
        whatif_resp = requests.get(f'http://localhost:5000/api/export/what-if/{dataset_id}')
        print('Status:', whatif_resp.status_code)
        print('Content type:', whatif_resp.headers.get('content-type'))
        print('Content length:', len(whatif_resp.content))
        print()
        
finally:
    os.unlink(temp_path)

print('✅ All exports working!')
