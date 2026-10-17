"""Fresh CPU model inference; accept correct sides and reject the opposite slot."""
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
BACK_KEYS = ('1791349537388','1791354186872','1791354224152')

if __name__ == '__main__':
    client=TestClient(app,base_url='http://127.0.0.1:8878')
    results=[]
    for photo in sorted(IMAGES.iterdir()):
        if photo.suffix.lower() not in {'.jpg','.png','.jpeg','.webp'}:
            continue
        expected='unknown' if '1791353035063' in photo.name else 'back' if any(k in photo.name for k in BACK_KEYS) else 'front'
        for slot in ('front','back'):
            response=client.post('/api/ocr',files={'file':(photo.name,photo.read_bytes())},data={'side':slot})
            data=response.json()
            detected=data.get('document_detection',{}).get('side')
            expected_http=200 if slot==expected else 422
            passed=response.status_code==expected_http and detected==expected
            if expected_http==422:
                passed=passed and 'fields' not in data and data.get('code')==('document_side_unknown' if expected=='unknown' else 'wrong_document_side')
            row={'file':photo.name,'slot':slot,'expected':expected,'detected':detected,'http':response.status_code,'passed':passed}
            results.append(row)
            (ROOT/'SIDE_TEST_RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(photo.name[:20],slot,detected,response.status_code,'PASS' if passed else 'FAIL',flush=True)
    sample=client.get('/api/sample-document')
    response=client.post('/api/ocr',files={'file':('sample.png',sample.content)},data={'side':'front'})
    assert response.status_code==200,response.text
    assert response.json()['fields']['date_of_birth']=='2000-02-01'
    failures=[row for row in results if not row['passed']]
    print('SUMMARY:',len(results),'requests,',len(failures),'failed',flush=True)
    raise SystemExit(bool(failures))
