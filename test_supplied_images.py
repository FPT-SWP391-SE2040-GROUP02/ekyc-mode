"""Kiểm thử mô hình thật bằng ảnh do người thử cung cấp; không lưu ảnh hay vùng cắt.

Ảnh và dữ liệu mong đợi KHÔNG nằm trong repo. Đặt biến môi trường EKYC_TEST_PHOTOS tới một thư mục
cục bộ chứa ảnh của chính bạn và tệp `expected.local.json` (xem `docs/expected.example.json`).
Không có thư mục này thì chỉ chạy phần kiểm tra chung không cần ảnh cá nhân.
"""
import runtime
import json
import os
from pathlib import Path
import sys
import unicodedata
from fastapi.testclient import TestClient
from server import app

ROOT = Path(__file__).resolve().parent


def normalize(text):
    return ' '.join(unicodedata.normalize('NFC', text).upper().split()).rstrip(' .,:')


def address_normalize(text):
    # Ignore punctuation, but retain all letters, Vietnamese accents and digits.
    import re
    return ' '.join(re.sub(r'[.,:]', ' ', normalize(text)).split())


def load_local_cases():
    """Trả (thư mục ảnh, dữ liệu mong đợi) hoặc (None, None) khi người thử chưa cung cấp."""
    folder = os.environ.get('EKYC_TEST_PHOTOS', '')
    if not folder or not Path(folder).is_dir():
        return None, None
    spec = Path(folder) / 'expected.local.json'
    if not spec.exists():
        return None, None
    return Path(folder), json.loads(spec.read_text(encoding='utf-8'))


def find(folder, prefix):
    return next(path for path in folder.iterdir() if prefix in path.name)


def run_local_photo_cases(client, folder, spec, only):
    """Đọc ảnh cá nhân và đối chiếu với `expected.local.json`. Trả danh sách kết quả."""
    results = []
    document_tokens = {}
    for prefix, expected in spec.get('fronts', {}).items():
        if only and only not in prefix:
            continue
        file = find(folder, prefix)
        response = client.post('/api/ocr', files={'file': (file.name, file.read_bytes())}, data={'side': 'front'})
        if response.status_code != 200:
            raise AssertionError(response.text)
        data = response.json()
        document_tokens[prefix] = data['document_token']
        checks = {k: normalize(data['fields'][k]) == normalize(expected[k])
                  for k in ('id_number', 'full_name', 'date_of_birth') if k in expected}
        if expected.get('address'):
            checks['residence_address'] = address_normalize(data['fields']['residence_address']) == address_normalize(expected['address'])
        results.append({'file': prefix, 'side': 'front', 'checks': checks,
                        'rotation': data['rotation_degrees'], 'elapsed_ms': data['elapsed_ms']})
        print(prefix[:20], results[-1], flush=True)
    for prefix, expected in spec.get('backs', {}).items():
        if only and only not in prefix:
            continue
        file = find(folder, prefix)
        response = client.post('/api/ocr', files={'file': (file.name, file.read_bytes())}, data={'side': 'back'})
        if response.status_code != 200:
            raise AssertionError(response.text)
        data = response.json()
        checks = {}
        if expected.get('id_number'):
            checks['back_id'] = data['fields']['id_number'] == expected['id_number']
        if expected.get('address'):
            checks['residence_address'] = address_normalize(data['fields']['residence_address']) == address_normalize(expected['address'])
        results.append({'file': prefix, 'side': 'back', 'checks': checks,
                        'rotation': data['rotation_degrees'], 'elapsed_ms': data['elapsed_ms']})
        print(prefix[:20], results[-1], flush=True)
    selfie_prefix = spec.get('selfie_prefix')
    if selfie_prefix:
        selfie = find(folder, selfie_prefix)
        for prefix, expected in spec.get('face_matches', {}).items():
            if only and only != prefix:
                continue
            response = client.post('/api/face-match', files={'selfie': (selfie.name, selfie.read_bytes())},
                                   data={'document_token': document_tokens[prefix]})
            assert response.status_code == 200, response.text
            data = response.json()
            results.append({'file': prefix, 'kind': 'face_match', 'expected': expected,
                            'passed': data['matched'] == expected, 'score': data['score']})
            print('FACE', prefix, data['matched'], data['score'], flush=True)
    return results


def run_generic_checks(client):
    """Kiểm tra chung bằng ảnh mẫu giả lập của dịch vụ, không cần ảnh cá nhân."""
    sample = client.get('/api/sample-document')
    response = client.post('/api/ocr', files={'file': ('sample.png', sample.content)})
    assert response.json()['fields']['date_of_birth'] == '2000-02-01'
    assert client.post('/api/ocr', files={'file': ('fake.jpg', b'bad')}).status_code == 422
    assert client.post('/api/ocr', files={'file': ('sample.png', sample.content)}, data={'side': 'invalid'}).status_code == 422
    assert client.post('/api/liveness/start', headers={'Origin': 'https://example.com'}).status_code == 403


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', help='Chỉ chạy một ca theo tiền tố tên tệp')
    args = parser.parse_args()
    client = TestClient(app, base_url='http://127.0.0.1:8878')
    folder, spec = load_local_cases()
    results = []
    if folder is None:
        print('SKIP ảnh cá nhân: đặt EKYC_TEST_PHOTOS tới thư mục có expected.local.json '
              '(xem docs/expected.example.json). Chỉ chạy phần kiểm tra chung.', flush=True)
    else:
        results = run_local_photo_cases(client, folder, spec, args.only)
        # Kết quả chỉ ghi tên tệp và trạng thái đạt/không, không ghi dữ liệu cá nhân.
        (ROOT / 'TEST_RESULTS.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    run_generic_checks(client)
    failures = [r for r in results if not all(r.get('checks', {}).values()) or r.get('passed') is False]
    print('SUMMARY', len(results), 'cases;', len(failures), 'failed', flush=True)
    sys.exit(bool(failures))
