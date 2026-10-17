"""Real OCR + YuNet/SFace integration: scanned front is the only reference source."""
import os
if not os.environ.get('EKYC_TEST_PHOTOS') or not os.path.isdir(os.environ['EKYC_TEST_PHOTOS']):
    print('SKIP: đặt EKYC_TEST_PHOTOS tới thư mục ảnh thử của chính bạn (không commit ảnh căn cước hay khuôn mặt thật).')
    raise SystemExit(0)
import runtime
import json
from pathlib import Path
from fastapi.testclient import TestClient
from server import app

ROOT = Path(__file__).resolve().parent
IMAGES = Path(os.environ['EKYC_TEST_PHOTOS'])


def photo(prefix):
    return next(path for path in IMAGES.iterdir() if prefix in path.name)


if __name__ == '__main__':
    client = TestClient(app, base_url='http://127.0.0.1:8879')
    selfie = photo('1791353035063')
    selfie_upload = {'selfie':(selfie.name, selfie.read_bytes())}
    results = []
    for prefix, expected in [('1791349811201', True), ('1791349859727', True), ('121133', True), ('122316', False), ('122411', False)]:
        front = photo(prefix)
        scanned = client.post('/api/ocr', files={'file':(front.name,front.read_bytes())}, data={'side':'front'})
        assert scanned.status_code == 200, scanned.text
        token = scanned.json()['document_token']
        assert token, 'Scanned front must yield exactly one face'
        # An extra uploaded image is deliberately the selfie itself; it must not override the front.
        response = client.post('/api/face-match', files={**selfie_upload,'reference':(selfie.name,selfie.read_bytes())}, data={'document_token':token})
        assert response.status_code == 200, response.text
        result = response.json()
        passed = result['matched'] == expected and result['reference_source'] == 'scanned_document_front'
        results.append({'case':'scan_front_then_match','file':front.name,'expected':expected,'matched':result['matched'],'score':result['score'],'passed':passed})
        print('FACE',prefix,'expected',expected,'matched',result['matched'],'score',result['score'],flush=True)
        assert client.delete('/api/documents/'+token).status_code == 200
        deleted = client.post('/api/face-match', files=selfie_upload, data={'document_token':token})
        results.append({'case':'deleted_front_reference','file':front.name,'status':deleted.status_code,'passed':deleted.status_code==410})
    back = photo('1791354186872')
    response = client.post('/api/ocr', files={'file':(back.name,back.read_bytes())}, data={'side':'back'})
    assert response.status_code == 200, response.text
    results.append({'case':'back_cannot_be_face_reference','passed':response.json()['document_token'] is None})
    response = client.post('/api/face-match', files={**selfie_upload,'reference':(selfie.name,selfie.read_bytes())})
    results.append({'case':'raw_reference_without_scan_rejected','status':response.status_code,'passed':response.status_code==422})
    (ROOT/'LOCKED_FACE_TEST_RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    failures = [result for result in results if not result['passed']]
    print('SUMMARY:',len(results),'checks,',len(failures),'failed',flush=True)
    client.close()
    raise SystemExit(bool(failures))
