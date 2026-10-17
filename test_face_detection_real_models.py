"""Run local YuNet/SFace regression checks; do not save images or embeddings."""
import os
if not os.environ.get('EKYC_TEST_PHOTOS') or not os.path.isdir(os.environ['EKYC_TEST_PHOTOS']):
    print('SKIP: đặt EKYC_TEST_PHOTOS tới thư mục ảnh thử của chính bạn (không commit ảnh căn cước hay khuôn mặt thật).')
    raise SystemExit(0)
import runtime
import json
from pathlib import Path
from engine import models, decode_image, InputError, cv2, np

ROOT = Path(__file__).resolve().parent
PHOTOS = Path(os.environ['EKYC_TEST_PHOTOS'])


def photo(prefix):
    return next(path for path in PHOTOS.iterdir() if prefix in path.name)


def read(path):
    return decode_image(path.read_bytes())


def main():
    results = []
    close_up = read(PHOTOS / 'Image(1).png')
    face, crop, feature = models.face(close_up)
    results.append({'case':'reported_close_up', 'detected_faces':1, 'confidence':round(float(face[-1]),5),
                    'original_size':[close_up.shape[1],close_up.shape[0]],
                    'crop_size':[crop.shape[1],crop.shape[0]], 'passed':crop.shape[:2]==(112,112)})
    for rotation in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180):
        _, rotated_crop, _ = models.face(cv2.rotate(close_up, rotation))
        results.append({'case':'close_up_rotation', 'rotation_code':rotation, 'passed':rotated_crop.shape[:2]==(112,112)})
    for case, image in [('blank',np.zeros_like(close_up)),('two_faces',np.concatenate([close_up,close_up],axis=1))]:
        try:
            models.face(image)
            passed = False
        except InputError as error:
            passed = ('đúng một' in str(error)) if case=='two_faces' else ('Chưa tìm' in str(error))
        results.append({'case':case,'passed':passed})
    _, _, selfie = models.face(read(photo('1791353035063')))
    for prefix, expected in [('1791349811201',True),('1791349859727',True),('121133',True),('122316',False),('122411',False)]:
        _, _, reference = models.face(read(photo(prefix)))
        score = models.similarity(reference, selfie)
        results.append({'case':'prior_face_pair', 'photo_prefix':prefix, 'expected':expected,
                        'score':round(score,5),'passed':(score>=.363)==expected})
    report={'checks':results,'passed':sum(item['passed'] for item in results),'total':len(results)}
    (ROOT/'test-results/FACE_SCALE_RESULTS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n','utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return int(report['passed'] != report['total'])


if __name__ == '__main__':
    raise SystemExit(main())
