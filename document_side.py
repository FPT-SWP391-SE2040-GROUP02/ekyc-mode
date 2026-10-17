"""Conservative side detection from OCR anchors; independent of the requested slot.

This identifies a printed layout, not whether the document is genuine. Weak or
conflicting evidence yields unknown and must not populate personal fields.
"""
import re
from logic import plain, NAME_LABEL, BIRTH_LABEL, label_in, extract_fields


def detect_document_side(lines):
    texts = [plain(line.get(key, '')) for line in lines for key in ('text', 'paddle_text')]
    compact = [re.sub(r'\s+', '', text).upper() for text in texts]
    def has(pattern):
        return any(re.search(pattern, text) for text in texts)

    fields = extract_fields(lines, 'front')['fields']
    # Birth registration is a back-side anchor, not the date-of-birth field.
    birth_label = any(label_in(line, BIRTH_LABEL) and not any(
        re.search(r'khai\s*sin\w*|place\s*of\s*birth', plain(line.get(key, '')))
        for key in ('text', 'paddle_text')) for line in lines)
    front = {
        'card_title': has(r'\bcan\s*cuoc\b|\b(?:citizen\s*)?identity\s*card\b'),
        'personal_number': bool(fields['id_number']),
        'name_field': any(label_in(line, NAME_LABEL) for line in lines) or bool(fields['full_name']),
        'birth_field': birth_label and bool(fields['date_of_birth']),
        'sex_or_nationality': has(r'\bgioi\s*tinh\b|\bsex\b|\bquoc\s*tich\b|\bnationality\b'),
    }
    back = {
        'mrz_id': any(re.search(r'IDVNM\d{10,}', text) for text in compact),
        'mrz_other_row': any('VNM<<' in text and not text.startswith('IDVNM') for text in compact),
        'birth_registration': has(r'noi\s*dang\s*ky\s*khai\s*sin\w*|place\s*of\s*birth'),
        'issue_date_label': has(r'\bngay\b.*\bcap\b|date\s*of\s*issue'),
        'issuing_authority': has(r'bo\s*cong\s*an|ministry\s*of\s*public\s*security|cuc\s*truong|director\s*general'),
        'fingerprint_labels': has(r'\bngon\s*tro\b|\bvan\s*tay\b|index\s*finger|fingerprint'),
        'identifying_marks': has(r'dac\s*diem\s*nhan\s*dang|dau\s*vet\s*rieng|personal\s*identification\s*marks'),
    }
    front_score = sum(front[key] * weight for key,weight in
                      [('card_title',2),('personal_number',2),('name_field',2),('birth_field',2),('sex_or_nationality',1)])
    back_score = sum(back[key] * weight for key,weight in
                     [('mrz_id',4),('mrz_other_row',2),('birth_registration',2),('issue_date_label',2),
                      ('issuing_authority',1),('fingerprint_labels',2),('identifying_marks',2)])
    is_front = front_score >= 6 and (front['name_field'] or front['birth_field']) and (front['card_title'] or front['personal_number'])
    is_back = back_score >= 5 and any(back[key] for key in ('mrz_id','birth_registration','fingerprint_labels','identifying_marks'))
    if is_front and is_back:
        side, reason = 'unknown', 'Ảnh có dấu hiệu của cả hai mặt; hãy chọn ảnh chỉ có một mặt thẻ.'
    elif is_front:
        side, reason = 'front', 'Nhận diện bố cục mặt trước từ thông tin danh tính.'
    elif is_back:
        side, reason = 'back', 'Nhận diện bố cục mặt sau từ MRZ hoặc nhãn đặc trưng mặt sau.'
    else:
        side, reason = 'unknown', 'Chưa đủ dấu hiệu để xác định mặt thẻ. Hãy chụp rõ một mặt, đủ phần chữ.'
    return {'side':side,'reason':reason,'front_evidence':[key for key,value in front.items() if value],
            'back_evidence':[key for key,value in back.items() if value], 'method':'ocr-layout-rules-v1'}


def side_error(detection, expected):
    if detection['side'] == expected:
        return None
    if detection['side'] == 'unknown':
        return {'code':'document_side_unknown','detail':detection['reason'],'document_detection':detection}
    actual_label = 'mặt trước' if detection['side'] == 'front' else 'mặt sau'
    expected_label = 'mặt trước' if expected == 'front' else 'mặt sau'
    return {'code':'wrong_document_side','detail':f'Ảnh này là {actual_label}, nhưng bạn đang quét {expected_label}. Hãy chọn đúng ảnh {expected_label}.',
            'document_detection':detection}
