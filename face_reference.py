"""Short-lived, in-memory face references created only by front-side OCR."""
from dataclasses import dataclass
import secrets
import time

from fastapi import HTTPException
from engine import models, data_url

REFERENCE_SECONDS = 30 * 60
MAX_REFERENCES = 50


@dataclass
class DocumentReference:
    feature: object
    crop: str
    created_at: float


references: dict[str, DocumentReference] = {}


def prune_references():
    now = time.monotonic()
    for token, reference in list(references.items()):
        if now - reference.created_at > REFERENCE_SECONDS:
            del references[token]


def create_reference(image):
    """Caller holds engine.LOCK and has recognized the front-side layout."""
    prune_references()
    _, crop, feature = models.face(image)
    while len(references) >= MAX_REFERENCES:
        oldest = min(references, key=lambda key: references[key].created_at)
        del references[oldest]
    token = secrets.token_urlsafe(24)
    references[token] = DocumentReference(feature.copy(), data_url(crop), time.monotonic())
    return token


def match_reference(token, selfie, threshold):
    """Never accepts an independently uploaded reference image."""
    if not token:
        raise HTTPException(422, 'Hãy đọc mặt trước CCCD trước khi so khớp selfie.')
    prune_references()
    reference = references.get(token)
    if reference is None:
        raise HTTPException(410, 'Ảnh CCCD đã hết hạn hoặc được thay đổi. Hãy đọc lại mặt trước.')
    _, crop, feature = models.face(selfie)
    score = models.similarity(reference.feature, feature)
    return {'score':round(score,5), 'threshold':threshold, 'matched':score >= threshold,
            'reference_crop':reference.crop, 'selfie_crop':data_url(crop),
            'reference_source':'scanned_document_front',
            'note':'Ảnh tham chiếu được khóa từ mặt trước đã đọc. Điểm cosine không phải phần trăm xác suất.'}
