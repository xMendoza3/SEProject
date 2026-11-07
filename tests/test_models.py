"""
اختبارات النماذج: الفحوصات اللي تمنع البيانات الغلط من دخول البرنامج.
"""

from dataclasses import FrozenInstanceError

import pytest

from src.models import Chapter, Evidence, Opinion, Page, to_arabic_digits


# التوثيق بأرقام الكتاب المطبوع، والرابط برقم الصفحة في الشاملة.
def test_page_citation_and_link():
    page = Page(308, 1, 310, "", "")
    assert page.citation() == "ج١ ص٣١٠"
    assert page.shamela_url() == "https://shamela.ws/book/9849/308"


def test_arabic_digits():
    assert to_arabic_digits(1446) == "١٤٤٦"


# كل سطر في القائمة حالة غلط، والقول لازم يرفضها وقت الإنشاء.
# المزخرف يشغّل نفس الاختبار مرة لكل سطر.
@pytest.mark.parametrize("madhab_ids, location", [
    ((), "main"),        # بدون مذهب
    ((7,), "main"),      # مذهب غير موجود
    ((1, 1), "main"),    # مذهب مكرر
    ((1,), "margin"),    # مكان غير المتن والحاشية
])
def test_opinion_rejects_bad_data(madhab_ids, location):
    with pytest.raises(ValueError):
        Opinion(1, 1, 1, madhab_ids, location, "نص")


def test_evidence_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Evidence("poem", "نص")


# التجميد: أي محاولة تعديل بعد الإنشاء تنرفض.
def test_models_are_frozen():
    opinion = Opinion(1, 1, 1, (1,), "main", "نص")
    with pytest.raises(FrozenInstanceError):
        opinion.text = "نص آخر"


# القول المشترك يظهر لأي مذهب من مذاهبه، ويختفي لو ما اخترت ولا واحد منها.
def test_chapter_filters_opinions_by_madhab():
    shared = Opinion(1, 1, 1, (2, 3), "main", "المالكية، والشافعية قالوا: كذا.")
    hanafi = Opinion(2, 1, 1, (1,), "main", "الحنفية قالوا: كذا.")
    chapter = Chapter(1, "باب", 2, None, 1, opinions=(shared, hanafi))

    assert chapter.get_opinions([3]) == [shared]
    assert chapter.get_opinions([1, 2]) == [shared, hanafi]
    assert chapter.get_opinions([4]) == []
