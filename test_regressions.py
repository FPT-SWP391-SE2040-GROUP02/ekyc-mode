import runtime
import unittest
from logic import extract_fields
from test_prototype import LogicTests


def row(text, x=200, y=100, w=400, h=20, **extra):
    return dict(text=text, score=.95, box=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]], **extra)


class RegressionTests(unittest.TestCase):
    def test_new_birth_label_uses_paddle_and_keeps_vietnamese(self):
        lines = [row('Ngày, tháng, năm sinh / Dinh', paddle_text='Ngày, tháng, năm sinh / Date of birth'),
                 row('Giới tính / Sex', y=130), row('12/03/2000', x=600, y=129)]
        self.assertEqual(extract_fields(lines)['fields']['date_of_birth'], '2000-03-12')

    def test_same_row_birthday_before_label(self):
        self.assertEqual(extract_fields([row('05/04/1990', x=500), row('Ngày sinh / Date of birth:')])['fields']['date_of_birth'], '1990-04-05')

    def test_mangled_full_name_label_is_not_a_person(self):
        lines = [row('Họ và tên I Fulls'), row('NGUYỄN VĂN AN', y=130)]
        self.assertEqual(extract_fields(lines)['fields']['full_name'], 'NGUYỄN VĂN AN')

    def test_residence_multiline_ignores_expiry_on_left(self):
        lines = [row('Nơi thường trú / Place of residence:', w=300), row('15/2/8, Đường', x=520),
                 row('21/07/2035', x=20, y=125, w=100), row('Mẫu Số 1, Phường 1, Thành phố Mẫu, Tỉnh Mẫu', y=135)]
        self.assertEqual(extract_fields(lines)['fields']['residence_address'], '15/2/8, Đường Mẫu Số 1, Phường 1, Thành phố Mẫu, Tỉnh Mẫu')

    def test_new_back_residence_stops_before_birthplace(self):
        lines = [row('Nơi cư trú/Place of residence: 5/27 Đường Mẫu Thứ', h=12),
                 row('Tam, Phường Mẫu, Thành phố Mẫu', y=118, h=18),
                 row('Nơi đăng ký khai sinh / Place of birth:', y=148),
                 row('Phường Mẫu, Thành phố Mẫu', y=173), row('20/10/2025', y=198)]
        result = extract_fields(lines, 'back')['fields']
        self.assertEqual(result['residence_address'], '5/27 Đường Mẫu Thứ Tam, Phường Mẫu, Thành phố Mẫu')
        self.assertEqual(result['date_of_birth'], '')

    def test_back_mrz_matches_front_id(self):
        result = extract_fields([row('IDVNM2000123450079200012345<<8')], 'back')
        self.assertEqual(result['fields']['id_number'], '079200012345')

    def test_unlabelled_date_or_birthplace_is_not_residence(self):
        result = extract_fields([row('Nơi đăng ký khai sinh / Place of birth:'), row('Hà Nội', y=130)], 'back')
        self.assertEqual(result['fields']['residence_address'], '')

    def test_mangled_residence_label_uses_paddle_and_previous_same_row(self):
        lines = [row('Xóm 5 Thôn Mẫu', x=600),
                 row('accumplaceofresidence', paddle_text='di cu tru/Place of residend'),
                 row('Xã Mẫu, Huyện Mẫu, Tỉnh Mẫu', x=175, y=130),
                 row('Nơi đăng ký khai sinh / Place of birth:', y=160)]
        self.assertEqual(extract_fields(lines,'back')['fields']['residence_address'], 'Xóm 5 Thôn Mẫu Xã Mẫu, Huyện Mẫu, Tỉnh Mẫu')

    def test_residence_uses_paddle_house_number_without_changing_street_name(self):
        lines = [row('Nơi cư trú /Place of residence 5 2/27 Đường Mẫu Thứ',
                     paddle_text='Nơi cư trú / Place of residence: 5/27 Đường Mau Thứ', paddle_score=.98),
                 row('Tám Phường Mẫu, Thành phố Mẫu',y=130),
                 row('Nơi đăng ký khai sinh / Place of birth:',y=160)]
        self.assertEqual(extract_fields(lines,'back')['fields']['residence_address'], '5/27 Đường Mẫu Thứ Tám Phường Mẫu, Thành phố Mẫu')


if __name__ == '__main__':
    unittest.main(verbosity=2)
