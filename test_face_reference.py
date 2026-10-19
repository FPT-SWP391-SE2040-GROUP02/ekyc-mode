"""Exercise the locked reference lifecycle and API contract without model downloads."""
import runtime
import io
import time
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from fastapi import HTTPException
from fastapi.testclient import TestClient
import face_reference as store
from engine import InputError
from server import app, sessions
from logic import Challenge
from test_document_side import FRONT, BACK


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        store.references.clear()

    def tearDown(self):
        store.references.clear()

    def test_matching_uses_a_copy_of_the_scanned_feature(self):
        feature = np.array([[1., 2.]])
        with patch.object(store.models, 'face', return_value=(None, 'front-crop', feature)), \
             patch.object(store, 'data_url', side_effect=lambda image: image):
            token = store.create_reference('front-image')
        feature[:] = 99
        with patch.object(store.models, 'face', return_value=(None, 'selfie-crop', np.array([[3., 4.]]))) as face, \
             patch.object(store.models, 'similarity', return_value=.6) as similarity, \
             patch.object(store, 'data_url', side_effect=lambda image: image):
            result = store.match_reference(token, 'selfie-image', .363)
        face.assert_called_once_with('selfie-image')
        np.testing.assert_array_equal(similarity.call_args.args[0], [[1., 2.]])
        self.assertTrue(result['matched'])
        self.assertEqual(result['reference_crop'], 'front-crop')
        self.assertEqual(result['reference_source'], 'scanned_document_front')

    def test_missing_unknown_and_expired_references_reject_before_running_models(self):
        store.references['expired'] = store.DocumentReference(None, '', time.monotonic()-store.REFERENCE_SECONDS-1)
        with patch.object(store.models, 'face') as face:
            for token, status in [('', 422), ('unknown', 410), ('expired', 410)]:
                with self.subTest(token=token), self.assertRaises(HTTPException) as caught:
                    store.match_reference(token, None, .363)
                self.assertEqual(caught.exception.status_code, status)
            face.assert_not_called()
        self.assertNotIn('expired', store.references)

    def test_capacity_evicts_oldest_reference(self):
        store.references['old'] = store.DocumentReference(None, '', time.monotonic()-2)
        store.references['new'] = store.DocumentReference(None, '', time.monotonic()-1)
        with patch.object(store, 'MAX_REFERENCES', 2), \
             patch.object(store.models, 'face', return_value=(None, 'crop', np.ones((1, 2)))), \
             patch.object(store, 'data_url', return_value='crop'):
            token = store.create_reference(None)
        self.assertNotIn('old', store.references)
        self.assertIn('new', store.references)
        self.assertIn(token, store.references)

    def test_no_face_does_not_create_a_reference(self):
        with patch.object(store.models, 'face', side_effect=InputError('No face')), self.assertRaises(InputError):
            store.create_reference(None)
        self.assertFalse(store.references)


class LockedFaceApiTests(unittest.TestCase):
    def setUp(self):
        store.references.clear(); sessions.clear()
        stream = io.BytesIO(); Image.new('RGB', (100, 100), 'white').save(stream, format='PNG')
        self.photo = stream.getvalue()
        self.client = TestClient(app, base_url='http://127.0.0.1:8879')

    def tearDown(self):
        store.references.clear(); sessions.clear(); self.client.close()

    def scan(self, side, evidence, face_error=None):
        with patch('server.models.read_document', return_value=evidence), \
             patch('server.models.last_document_image', np.zeros((100,100,3), dtype=np.uint8), create=True), \
             patch('server.models.last_document_rotation', 0, create=True), \
             patch.object(store.models, 'face', return_value=(None, np.zeros((20,20,3), dtype=np.uint8), np.ones((1,2))), side_effect=face_error) as face:
            response = self.client.post('/api/ocr', files={'file':('card.png', self.photo)}, data={'side':side})
        return response, face.call_count

    def test_front_issues_token_back_does_not(self):
        front, calls = self.scan('front', FRONT)
        self.assertEqual(front.status_code, 200, front.text)
        self.assertEqual(calls, 1)
        self.assertIn(front.json()['document_token'], store.references)
        back, calls = self.scan('back', BACK)
        self.assertEqual(back.status_code, 200, back.text)
        self.assertIsNone(back.json()['document_token'])
        self.assertEqual(calls, 0)

    def test_no_face_still_returns_ocr_but_no_match_token(self):
        response, _ = self.scan('front', FRONT, InputError('No face'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['document_token'])
        self.assertTrue(response.json()['fields']['id_number'])
        self.assertTrue(any('khuôn mặt' in message for message in response.json()['warnings']))

    def test_separate_reference_cannot_bypass_front_scan(self):
        with patch.object(store.models, 'face') as face:
            response = self.client.post('/api/face-match', files={'reference':('forged.png',self.photo), 'selfie':('selfie.png',self.photo)})
        self.assertEqual(response.status_code, 422)
        face.assert_not_called()

    def test_valid_token_uses_stored_reference_despite_extra_upload(self):
        front, _ = self.scan('front', FRONT)
        token = front.json()['document_token']
        with patch.object(store.models, 'face', return_value=(None, np.zeros((20,20,3), dtype=np.uint8), np.full((1,2),2))) as face, \
             patch.object(store.models, 'similarity', return_value=.2) as similarity:
            response = self.client.post('/api/face-match', files={'reference':('forged.png',self.photo),'selfie':('selfie.png',self.photo)}, data={'document_token':token})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['matched'])
        self.assertEqual(face.call_count, 1, 'Only selfie is reprocessed')
        np.testing.assert_array_equal(similarity.call_args.args[0], np.ones((1,2)))

    def test_face_embedding_returns_vector_without_storing_anything(self):
        feature = np.arange(128, dtype=np.float32).reshape(1, 128)
        with patch.object(store.models, 'face', return_value=(None, None, feature)) as face:
            response = self.client.post('/api/face-embedding', files={'selfie':('selfie.png',self.photo)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['model'], 'sface')
        self.assertEqual(body['dimension'], 128)
        self.assertEqual(body['embedding'], [float(value) for value in range(128)])
        self.assertEqual(face.call_count, 1)
        self.assertFalse(store.references, 'Không giữ lại gì trong bộ nhớ dịch vụ')
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_face_embedding_rejects_image_without_exactly_one_face(self):
        with patch.object(store.models, 'face', side_effect=InputError('Ảnh cần có đúng một khuôn mặt.')):
            response = self.client.post('/api/face-embedding', files={'selfie':('selfie.png',self.photo)})
        self.assertEqual(response.status_code, 422)

    def test_deleted_expired_and_unknown_tokens_return_410(self):
        front, _ = self.scan('front', FRONT)
        token = front.json()['document_token']
        self.assertEqual(self.client.delete('/api/documents/'+token).status_code, 200)
        self.assertEqual(self.client.delete('/api/documents/'+token).status_code, 200)
        store.references['expired'] = store.DocumentReference(None,'',time.monotonic()-store.REFERENCE_SECONDS-1)
        for invalid in [token, 'unknown', 'expired']:
            response = self.client.post('/api/face-match', files={'selfie':('selfie.png',self.photo)}, data={'document_token':invalid})
            self.assertEqual(response.status_code, 410, response.text)

    def test_threshold_bounds(self):
        for threshold in ['0', '1', 'nan']:
            response = self.client.post('/api/face-match', files={'selfie':('selfie.png',self.photo)}, data={'document_token':'unknown','threshold':threshold})
            self.assertEqual(response.status_code, 422)

    def test_camera_selfie_requires_passed_session(self):
        session = Challenge(actions=['blink'], created_at=time.monotonic())
        session.best_frame = self.photo; sessions['camera'] = session
        self.assertEqual(self.client.get('/api/liveness/camera/selfie').status_code, 409)
        session.index = 1; session.live_scores = [.9]*5
        response = self.client.get('/api/liveness/camera/selfie')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.photo)
        session.created_at -= 91
        self.assertEqual(self.client.get('/api/liveness/camera/selfie').status_code, 410)


if __name__ == '__main__':
    unittest.main(verbosity=2)
