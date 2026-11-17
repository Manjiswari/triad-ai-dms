import io
import json
from app import create_app

def run_tests():
    app = create_app()
    client = app.test_client()

    print("1. Health check...")
    res = client.get('/api/health')
    assert res.status_code == 200

    print("2. Register User A (Division A)...")
    res = client.post('/api/auth/register', json={
        'username': 'tester_a',
        'email': 'tester_a@diva.com',
        'password': 'Password@123',
        'division': 'Division A'
    })
    assert res.status_code in [200, 201]
    token_a = res.get_json()['token']

    print("3. Register User B (Division B)...")
    res = client.post('/api/auth/register', json={
        'username': 'tester_b',
        'email': 'tester_b@divb.com',
        'password': 'Password@123',
        'division': 'Division B'
    })
    assert res.status_code in [200, 201]
    token_b = res.get_json()['token']

    print("4. Document upload with dynamic metadata & GridFS...")
    file_bytes = b"%PDF-1.4\nCONFIDENTIAL FINANCIAL AUDIT REPORT 2024\n%%EOF"
    upload_data = {
        'file': (io.BytesIO(file_bytes), 'audit_2024.pdf', 'application/pdf'),
        'title': 'Audit 2024',
        'metadata': json.dumps({'Division': 'Division A', 'Report Type': 'Financial', 'Tier': 'High'})
    }
    res = client.post('/api/documents/upload', data=upload_data, headers={'Authorization': f'Bearer {token_a}'}, content_type='multipart/form-data')
    assert res.status_code in [200, 201]
    doc_id = res.get_json()['doc_id']

    print("5. Verify RBAC isolation on upload (User A cannot upload to Division B)...")
    res = client.post('/api/documents/upload', data={
        'file': (io.BytesIO(file_bytes), 'illegal.pdf', 'application/pdf'),
        'metadata': json.dumps({'Division': 'Division B', 'Report Type': 'Operations'})
    }, headers={'Authorization': f'Bearer {token_a}'}, content_type='multipart/form-data')
    assert res.status_code == 403

    print("6. Verify Cross-Division download denial (User B downloading Division A doc)...")
    res = client.get(f'/api/documents/{doc_id}/download', headers={'Authorization': f'Bearer {token_b}'})
    assert res.status_code == 403

    print("7. Access request & approval workflow...")
    res = client.post('/api/access/request', json={'doc_id': doc_id, 'reason': 'Audit review'}, headers={'Authorization': f'Bearer {token_b}'})
    assert res.status_code in [200, 201]
    req_id = res.get_json()['request_id']

    res = client.post('/api/access/approve', json={'request_id': req_id, 'status': 'approved'}, headers={'Authorization': f'Bearer {token_a}'})
    assert res.status_code == 200

    res = client.get(f'/api/documents/{doc_id}/download', headers={'Authorization': f'Bearer {token_b}'})
    assert res.status_code == 200
    assert len(res.data) > 0

    print("8. Dynamic metadata filtering (?Report Type=Financial)...")
    res = client.get('/api/documents?Report Type=Financial', headers={'Authorization': f'Bearer {token_a}'})
    assert res.status_code == 200
    assert len(res.get_json()['documents']) >= 1

    print("9. OCR Search Engine (?q=CONFIDENTIAL)...")
    res = client.get('/api/search?q=CONFIDENTIAL')
    assert res.status_code == 200
    assert len(res.get_json()['results']) >= 1

    print("\nSUCCESS: All tests passed!")

if __name__ == "__main__":
    run_tests()
