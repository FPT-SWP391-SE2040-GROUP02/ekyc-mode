import runtime
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from document_side import detect_document_side
from server import app


def lines(*texts):
    return [{'text':text,'score':.99} for text in texts]


FRONT = lines('CĂN CƯỚC CÔNG DÂN','000000000001','Họ và tên / Full name:',
              'NGUYỄN VĂN AN','Ngày sinh / Date of birth: 01/02/2000',
              'Nơi thường trú / Place of residence: Hà Nội','Có giá trị đến: 01/02/2040')
BACK = lines('Nơi cư trú / Place of residence: Hà Nội','Nơi đăng ký khai sinh / Place of birth: Hà Nội',
             'Ngày, tháng, năm cấp / Date of issue: 01/01/2025',
             'IDVNM0000000010000000000001<<0','0002010M4002010VNM<<<<<<<<<<<2')


class DocumentSideTests(unittest.TestCase):
    def test_old_front_address_and_expiry_do_not_make_it_back(self):
        self.assertEqual(detect_document_side(FRONT)['side'],'front')

    def test_new_back_birth_registration_is_not_date_of_birth(self):
        result = detect_document_side(BACK)
        self.assertEqual(result['side'],'back')
        self.assertNotIn('birth_field',result['front_evidence'])

    def test_old_back_without_mrz(self):
        evidence = lines('Ngón trỏ trái / Left index finger','Ngón trỏ phải / Right index finger',
                         'Ngày cấp / Date of issue: 01/01/2021','Cục trưởng / Director General')
        self.assertEqual(detect_document_side(evidence)['side'],'back')

    def test_title_residence_qr_or_unlabelled_numbers_alone_are_unknown(self):
        for case in [[],lines('Căn cước'),lines('Nơi cư trú / Place of residence: Hà Nội'),
                     lines('000000000001'),lines('QR code'),lines('01/01/2000','Nguyễn Văn An')]:
            with self.subTest(case=case):
                self.assertEqual(detect_document_side(case)['side'],'unknown')

    def test_two_sides_in_one_image_are_unknown(self):
        self.assertEqual(detect_document_side(FRONT+BACK)['side'],'unknown')

    def test_do_not_depend_on_residence_or_chip_for_front(self):
        evidence = lines('CĂN CƯỚC','000000000001','Họ, chữ đệm và tên khai sinh / Full name:',
                         'NGUYỄN VĂN AN','Ngày, tháng, năm sinh / Date of birth: 01/02/2000')
        self.assertEqual(detect_document_side(evidence)['side'],'front')

    def test_mrz_requires_more_than_country_word(self):
        self.assertEqual(detect_document_side(lines('VNM','NGUYEN<<VAN<AN'))['side'],'unknown')

    def test_api_rejects_wrong_side_and_unknown_without_fields(self):
        stream=io.BytesIO();Image.new('RGB',(100,100),'white').save(stream,format='PNG')
        client=TestClient(app,base_url='http://127.0.0.1:8878')
        for evidence,expected,code in [(FRONT,'back','wrong_document_side'),(BACK,'front','wrong_document_side'),([], 'front','document_side_unknown')]:
            with self.subTest(expected=expected,code=code), patch('server.models.read_document',return_value=evidence):
                response=client.post('/api/ocr',files={'file':('test.png',stream.getvalue())},data={'side':expected})
                self.assertEqual(response.status_code,422)
                self.assertEqual(response.json()['code'],code)
                self.assertNotIn('fields',response.json())

    def test_api_classification_ignores_requested_slot(self):
        stream=io.BytesIO();Image.new('RGB',(100,100),'white').save(stream,format='PNG')
        client=TestClient(app,base_url='http://127.0.0.1:8878')
        for evidence,expected in [(FRONT,'front'),(BACK,'back')]:
            with self.subTest(expected=expected), patch('server.models.read_document',return_value=evidence), \
                 patch('server.models.last_document_image',np.zeros((100,100,3),dtype=np.uint8),create=True), \
                 patch('server.create_reference',return_value='mock-front-token'), \
                 patch('server.models.last_document_rotation',0,create=True):
                response=client.post('/api/ocr',files={'file':('test.png',stream.getvalue())},data={'side':expected})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['document_detection']['side'],expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
