"""Field extraction and challenge state; no model or business authorization here."""
from dataclasses import dataclass, field
from datetime import date, datetime
import re
import unicodedata


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")



NAME_LABEL = re.compile(r"\b(?:ho\s*[,;]?\s*(?:chu\s+dem\s*[,;]?\s*)?(?:va\s*)?ten(?:\s+khai\s+sinh)?|full\s*name)\b")
BIRTH_LABEL = re.compile(r"\b(?:ngay\s*[,.;]?\s*(?:thang\s*[,.;]?\s*nam\s*)?sinh|date\s*of\s*birth|sinh\s*/)")
EXPIRY_LABEL = re.compile(r"\b(?:co\s*gia\s*tri\s*den|date\s*of\s*expiry|co\s*gia\s*tri|gia\s*tri\s*den|ngay\s*het\s*han|het\s*han|han\s*su\s*dung|han\s*dung|han\s*den|valid\s*until|expiry)\b")
NO_EXPIRY_PATTERN = re.compile(r"\b(?:khong\s*(?:co\s*)?thoi\s*han|vo\s*thoi\s*han|no\s*expiry|unlimited)\b")
RESIDENCE_LABEL = re.compile(r"\b(?:noi\s*(?:thuong\s*tru|cu\s*tru)|p[li]ace\s*of\s*residen\w*)\b")
OTHER_FIELD = re.compile(r"\b(?:ngay\s*[,.;]?\s*(?:thang\s*[,.;]?\s*nam\s*)?sinh|date\s*of\s*birth|gioi\s*tinh|sex|gender|quoc\s*tich|nationality|que\s*quan|place\s*of\s*origin|noi\s*dang\s*ky\s*khai\s*sinh|place\s*of\s*birth|noi\s*(?:thuong\s*tru|cu\s*tru)|place\s*of\s*residence|ngay.*(?:het\s*han|cap)|date\s*of\s*(?:expiry|issue)|co\s*gia\s*tri|bo\s*cong\s*an|ministry|can\s*cuoc|identity\s*card)\b")
DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})(?!\d)")


def bounds(line):
    points = line.get('box')
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def label_in(line, pattern):
    return any(pattern.search(plain(line.get(k, ''))) for k in ('text', 'paddle_text'))


def name_value(text):
    value = unicodedata.normalize('NFC', text).strip(' :/.-')
    while value:
        label = NAME_LABEL.match(plain(value))
        if not label:
            break
        value = value[label.end():].strip(' :/.-')
    return value


def is_name_value(value):
    if OTHER_FIELD.search(plain(value)) or NAME_LABEL.search(plain(value)):
        return False
    if re.search(r'\b(?:full\w*|name\w*)\b', plain(value)):
        return False
    words = value.split()
    return len(words) >= 2 and all(word.strip("-'’") and all(c.isalpha() or c in "-'’" for c in word) for word in words)


def extract_full_name(lines):
    for i, line in enumerate(lines):
        if not label_in(line, NAME_LABEL):
            continue
        text = unicodedata.normalize('NFC', line['text']).strip()
        label = NAME_LABEL.search(plain(text))
        value = name_value(text[label.end():]) if label else ''
        # Never accept a mangled English label as a person's name.
        if value and value == value.upper() and is_name_value(value) and float(line.get('score', 0)) >= .8:
            return value, text
        for following in lines[i + 1:i + 4]:
            candidate = name_value(following['text'])
            if not candidate:
                continue
            if OTHER_FIELD.search(plain(candidate)) or any(c.isdigit() for c in candidate):
                break
            if is_name_value(candidate) and float(following.get('score', 0)) >= .8:
                return candidate, following['text']
            break
    for i, line in enumerate(lines):
        if not re.search(r'(?<!\d)(?:\d[ \t]*){12}(?![ \t]*\d)', line['text']):
            continue
        region, found_birthday = [], False
        for following in lines[i + 1:]:
            if label_in(following, BIRTH_LABEL) or re.search(r'\bsinh\b', plain(following['text'])):
                found_birthday = True
                break
            if OTHER_FIELD.search(plain(following['text'])):
                break
            candidate = name_value(following['text'])
            if is_name_value(candidate) and candidate == candidate.upper() and float(following.get('score', 0)) >= .8:
                region.append(candidate)
        if found_birthday and len(region) == 1:
            return region[0], region[0]
    return '', ''


def extract_birthday(lines):
    for i, label in enumerate(lines):
        if not label_in(label, BIRTH_LABEL):
            continue
        lb = bounds(label)
        candidates = []
        for j, line in enumerate(lines):
            box = bounds(line)
            if lb and box:
                h = max(8, lb[3] - lb[1], box[3] - box[1])
                dy = (box[1] + box[3] - lb[1] - lb[3]) / 2
                # Same printed row can occur before its label in OCR's list.
                if not -.65 * h <= dy <= 2.7 * h or box[2] < lb[0] - h:
                    continue
                distance = abs(dy) / h + max(0, lb[0] - box[0]) / (h * 4)
            else:
                if not i <= j < i + 3:
                    continue
                distance = j - i
            raw = line['text']
            if re.search(r'het\s*han|expiry|ngay.*cap|date\s*of\s*issue|co\s*gia\s*tri', plain(raw)):
                continue
            for key in ('text', 'paddle_text'):
                for match in DATE_PATTERN.finditer(line.get(key, '')):
                    try:
                        birthday = date(int(match[3]), int(match[2]), int(match[1]))
                        if 1900 <= birthday.year and birthday <= date.today():
                            candidates.append((distance, birthday.isoformat(), line.get(key, '')))
                    except ValueError:
                        pass
        if candidates:
            _, value, source = min(candidates, key=lambda item: item[0])
            return value, source
    return '', ''


def extract_expiry(lines):
    for i, label in enumerate(lines):
        if not label_in(label, EXPIRY_LABEL):
            continue
        lb = bounds(label)
        candidates = []
        for j, line in enumerate(lines):
            box = bounds(line)
            if lb and box:
                h = max(8, lb[3] - lb[1], box[3] - box[1])
                dy = (box[1] + box[3] - lb[1] - lb[3]) / 2
                if not -.65 * h <= dy <= 2.7 * h or box[2] < lb[0] - h:
                    continue
                distance = abs(dy) / h + max(0, lb[0] - box[0]) / (h * 4)
            else:
                if not i <= j < i + 3:
                    continue
                distance = j - i
            for key in ('text', 'paddle_text'):
                val_text = line.get(key, '')
                if NO_EXPIRY_PATTERN.search(plain(val_text)):
                    candidates.append((distance, 'Không thời hạn', val_text))
                for match in DATE_PATTERN.finditer(val_text):
                    try:
                        exp = date(int(match[3]), int(match[2]), int(match[1]))
                        if 1990 <= exp.year <= 2150:
                            candidates.append((distance, exp.isoformat(), val_text))
                    except ValueError:
                        pass
        if candidates:
            _, value, source = min(candidates, key=lambda item: item[0])
            return value, source

    # Fallback: quét trực tiếp xem có dòng nào chứa nhãn expiry hoặc không thời hạn
    for line in lines:
        for key in ('text', 'paddle_text'):
            val_text = line.get(key, '')
            p_text = plain(val_text)
            if EXPIRY_LABEL.search(p_text):
                if NO_EXPIRY_PATTERN.search(p_text):
                    return 'Không thời hạn', val_text
                for match in DATE_PATTERN.finditer(val_text):
                    try:
                        exp = date(int(match[3]), int(match[2]), int(match[1]))
                        if 1990 <= exp.year <= 2150:
                            return exp.isoformat(), val_text
                    except ValueError:
                        pass
    return '', ''


def residence_value(raw):
    text = unicodedata.normalize('NFC', raw).strip()
    # Remove the complete bilingual label, keeping any inline address.
    label = RESIDENCE_LABEL.search(plain(text))
    if label:
        text = text[label.end():].lstrip(' :/|I.-')
        english = re.match(r'(?:p[li]ace\s*of\s*residen\w*)\s*[:/|.-]*', plain(text))
        if english:
            text = text[english.end():].strip(' :/|.-')
    return text


def extract_residence(lines):
    for i, label in enumerate(lines):
        if not label_in(label, RESIDENCE_LABEL):
            continue
        lb = bounds(label)
        pieces = []
        candidates = []
        for j, line in enumerate(lines):
            box = bounds(line)
            if lb and box:
                h = max(8, lb[3] - lb[1])
                dy = box[1] - lb[1]
                if not -.65 * h <= dy <= 5 * h or box[0] < lb[0] - h * 1.5:
                    continue
                # Stop at birthplace/issue/expiry labels below residence.
                blocked = any(k != i and bounds(other) and label_in(other, OTHER_FIELD)
                              and bounds(other)[1] > lb[1] + h * .5
                              and bounds(other)[1] < box[1] - h * .3
                              and bounds(other)[0] >= lb[0] - h
                              for k, other in enumerate(lines))
                if blocked:
                    continue
            elif not i <= j < i + 4:
                continue
            candidates.append((j, line))
        for j, line in candidates:
            if j != i and label_in(line, OTHER_FIELD):
                continue
            value = residence_value(line['text']) if j == i else line['text'].strip()
            # As in the ID/date pipeline, use Paddle's numeric reading and
            # VietOCR's Vietnamese words. Never invent or normalize a street name.
            paddle_value = residence_value(line.get('paddle_text', '')) if j == i else line.get('paddle_text', '').strip()
            if j == i and not RESIDENCE_LABEL.search(plain(line['text'])):
                value = paddle_value
            number = re.match(r'^[\d\s/.-]+(?=[^\W\d_])', value)
            paddle_number = re.match(r'^[\d\s/.-]+(?=[^\W\d_])', paddle_value)
            if number and paddle_number and float(line.get('paddle_score', 0)) >= .8:
                value = paddle_number[0].strip() + ' ' + value[number.end():]
            if not value or DATE_PATTERN.fullmatch(value) or '<' in value or not any(c.isalpha() for c in value):
                continue
            if label_in(line, NAME_LABEL) or re.search(r'\b(?:IDVNM|VNM)\b', value):
                continue
            pieces.append(value)
        if pieces:
            return ' '.join(pieces), ' | '.join(pieces)
    return '', ''


def extract_fields(lines, side='front'):
    result = {'id_number': '', 'full_name': '', 'date_of_birth': '', 'date_of_expiry': '', 'residence_address': ''}
    sources = {}
    for line in lines:
        for match in re.finditer(r'(?<!\d)(?:\d[ \t]*){12}(?![ \t]*\d)', line['text']):
            result['id_number'] = re.sub(r'\s', '', match.group())
            sources['id_number'] = line['text']
            break
        if result['id_number']:
            break
    if side == 'front':
        for field_name, extractor in [('full_name', extract_full_name), ('date_of_birth', extract_birthday), ('date_of_expiry', extract_expiry)]:
            value, source = extractor(lines)
            result[field_name] = value
            if value:
                sources[field_name] = source
    else:
        # New cards repeat the personal ID at the end of MRZ line 1.
        # Only use it to detect mixing the front and back of different cards.
        for line in lines:
            compact = re.sub(r'\s', '', line.get('paddle_text', line['text'])).upper()
            match = re.search(r'IDVNM\d+?(\d{12})<<', compact)
            if match:
                result['id_number'] = match[1]
                sources['id_number'] = 'MRZ'
                break
    address, source = extract_residence(lines)
    result['residence_address'] = address
    if address:
        sources['residence_address'] = source
    required = [('residence_address', 'nơi cư trú')] if side == 'back' else [('id_number', 'số căn cước'), ('full_name', 'họ tên'), ('date_of_birth', 'ngày sinh')]
    warnings = [f'Chưa lấy được {label}; hãy kiểm tra ảnh hoặc nhập lại.' for key, label in required if not result[key]]
    if any(float(line.get('score', 0)) < .8 for line in lines):
        warnings.append('Có dòng chữ với điểm OCR thấp; hãy đối chiếu ảnh gốc.')
    return {'fields': result, 'sources': sources, 'warnings': warnings, 'side': side}


ACTION_LABELS = {
    "blink": "Nhắm mắt khoảng 1 giây, rồi mở mắt",
    "left": "Quay đầu nhẹ sang trái, giữ 1 giây, rồi nhìn thẳng",
    "right": "Quay đầu nhẹ sang phải, giữ 1 giây, rồi nhìn thẳng",
}


@dataclass
class Challenge:
    actions: list[str]
    created_at: float
    index: int = 0
    calibrated: bool = False
    baseline_yaw: float = 0.0
    baseline_eye: float = 0.25
    calibration: list = field(default_factory=list)
    phase: str = "neutral"
    hits: int = 0
    completed: list = field(default_factory=list)
    failed_reason: str = ""
    live_scores: list = field(default_factory=list)
    last_frame_at: float = 0.0
    seen_hashes: set = field(default_factory=set)
    anchor: object = None
    best_frame: bytes | None = None
    frames: int = 0

    def update(self, yaw, eye, now):
        if self.failed_reason or self.index >= len(self.actions):
            return
        # A gap breaks a gesture sequence; timestamps are from the server.
        if self.last_frame_at and now - self.last_frame_at > 3:
            self.phase, self.hits = "neutral", 0
        self.last_frame_at = now
        if not self.calibrated:
            if eye < 0.14 or abs(yaw) > 0.16:
                self.calibration.clear()
                return
            self.calibration.append((yaw, eye))
            if len(self.calibration) >= 4:
                self.baseline_yaw = sum(x[0] for x in self.calibration) / len(self.calibration)
                self.baseline_eye = sum(x[1] for x in self.calibration) / len(self.calibration)
                self.calibrated = True
            return
        offset = yaw - self.baseline_yaw
        open_eye = eye > self.baseline_eye * 0.72
        neutral = abs(offset) < 0.08 and open_eye
        action = self.actions[self.index]
        condition = {"blink": eye < self.baseline_eye * 0.55,
                     "left": offset > 0.13 and open_eye,
                     "right": offset < -0.13 and open_eye}[action]
        if self.phase == "neutral":
            if neutral:
                self.hits += 1
                if self.hits >= 2:
                    self.phase, self.hits = "action", 0
            else:
                self.hits = 0
        elif self.phase == "action":
            self.hits = self.hits + 1 if condition else 0
            if self.hits >= 2:
                self.phase, self.hits = "return", 0
        elif self.phase == "return":
            self.hits = self.hits + 1 if neutral else 0
            if self.hits >= 2:
                self.completed.append(action)
                self.index += 1
                self.phase, self.hits = "neutral", 0

    def snapshot(self):
        finished = self.index == len(self.actions) and not self.failed_reason
        pad_score = sum(self.live_scores) / len(self.live_scores) if self.live_scores else None
        pad_pass = pad_score is not None and len(self.live_scores) >= 5 and pad_score >= 0.7
        if self.failed_reason:
            prompt = self.failed_reason
        elif not self.calibrated:
            prompt = "Nhìn thẳng, mở mắt và giữ yên khoảng 2 giây để bắt đầu"
        elif finished:
            prompt = "Đã hoàn thành động tác. Đối chiếu thêm kết quả chống giả mạo."
        elif self.phase == "return":
            prompt = "Mở mắt, nhìn thẳng lại và giữ yên"
        else:
            prompt = ACTION_LABELS[self.actions[self.index]]
        return {"actions": [{"key": a, "label": ACTION_LABELS[a]} for a in self.actions],
                "completed": self.completed, "current_index": self.index,
                "prompt": prompt, "calibrated": self.calibrated,
                "challenge_completed": finished, "pad_score": round(pad_score, 4) if pad_score is not None else None,
                "pad_samples": len(self.live_scores), "pad_threshold": 0.7,
                "pad_passed": pad_pass, "prototype_passed": finished and pad_pass,
                "failed_reason": self.failed_reason, "frames": self.frames,
                "note": "Kết quả thử nghiệm; chưa bảo đảm chống deepfake/video phát lại hoặc xác thực CCCD."}
