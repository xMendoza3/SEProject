"""
اختبارات المتحكمات: هل تنسّق بين الطبقات صح؟
"""

from src.controllers import ExplorerController, ImportController
from src.database import DatabaseManager


# كل مذهب مختار ياخذ أقواله، والقول المشترك يظهر عند كل مذاهبه.
def test_open_chapter_groups_opinions_by_madhab(controller):
    view = controller.open_chapter(2, [1, 3])
    assert set(view.opinions_by_madhab) == {1, 3}
    assert [o.opinion_id for o in view.opinions_by_madhab[3]] == [2]
    assert [c.chapter_id for c in view.path] == [1, 2]
    assert view.page.citation() == "ج١ ص٣٠٧"


def test_missing_chapter(controller):
    assert controller.open_chapter(999, [1]) is None


# البحث يعرض أقوال المذاهب المختارة بس.
def test_search_respects_selected_madhabs(controller):
    results = controller.receive_query("قالوا", [4])
    assert [o.madhab_ids for o in results.opinions] == [(4,)]
    assert results.titles == {2: "صلاة التراويح: حكمها، ووقتها"}


# النص المنسوخ: العنوان، ثم القول، ثم المصدر، ثم الرابط في سطر لحاله.
def test_quote_has_title_text_citation_and_link(controller):
    opinion = controller.open_chapter(2, [1]).opinions_by_madhab[1][0]
    lines = controller.quote_opinion(opinion, "صلاة التراويح").split("\n")
    assert lines[0] == "صلاة التراويح"
    assert lines[2] == opinion.text
    assert lines[-2] == "المصدر: الفقه على المذاهب الأربعة للجزيري، ج١ ص٣٠٧"
    assert lines[-1] == "https://shamela.ws/book/9849/1"


# متحكم الاستيراد ياخذ خدماته من برا.
# فنعطيه ساحب مزيف بدل الإنترنت، وقاعدة بيانات في الذاكرة بدل الملف الحقيقي،
# ونجرب المراحل الأربع كاملة على صفحة وحدة.
class FakeScraper:
    def fetch_index(self):
        return {"indexes": {"headings": [
            {"title": "كتاب الصلاة", "level": 1, "page": 1},
            {"title": "صلاة الوتر", "level": 2, "page": 1},
        ]}}

    def fetch_book(self):
        text = ('<span data-type="title" id=toc-1>كتاب الصلاة</span>\n'
                '<span data-type="title" id=toc-2>صلاة الوتر</span>\nالوتر مشروع (١)'
                "\n_________\n"
                "(١) الحنفية قالوا: واجب.\nالشافعية قالوا: سنة.")
        return {"pages": [{"text": text, "vol": "1", "page": "1"}]}


# ساحب حدود مزيف: يسجل الدول اللي انطلبت بدل ما يتصل بالإنترنت.
class FakeBoundaries:
    def __init__(self):
        self.countries = []

    def fetch_regions(self, country, target):
        self.countries.append(country)
        return target


# ساحب حدود يتصرف كأن الجهاز بدون إنترنت.
class OfflineBoundaries:
    def fetch_regions(self, country, target):
        raise OSError("no internet")


def test_import_runs_all_stages():
    db = DatabaseManager(":memory:")
    boundaries = FakeBoundaries()
    stats = ImportController(scraper=FakeScraper(), db=db, boundaries=boundaries) \
        .run(report=lambda message: None)
    assert (stats["chapters"], stats["opinions"]) == (2, 2)
    # الدول المقسومة في الخريطة كلها انطلبت حدودها.
    assert boundaries.countries == ["EGY", "IRQ", "SAU"]

    view = ExplorerController(db=db).open_chapter(2, [1, 3])
    assert [o.text for o in view.opinions_by_madhab[3]] == ["الشافعية قالوا: سنة."]
    db.close()


# بدون إنترنت: الكتاب ينحفظ عادي، والخريطة بس تنتظر.
def test_import_survives_missing_boundaries():
    db = DatabaseManager(":memory:")
    messages = []
    stats = ImportController(scraper=FakeScraper(), db=db, boundaries=OfflineBoundaries()) \
        .run(report=messages.append)
    assert stats["chapters"] == 2
    assert any("skipped" in message for message in messages)
    db.close()


# المتحكم يجمع الخريطة من مستودعها، ورابط المصدر يوصل لصفحة الشاملة.
def test_controller_returns_madhab_map(controller):
    madhab_map = controller.get_madhab_map()
    assert madhab_map.sources["taymur"].page_url(87) == "https://shamela.ws/book/96605/87"
    assert any(region.name == "مصر: الصعيد" for region in madhab_map.regions)


# صفحة الإمام: النبذة ومصدرها ومذهبها. ورقم مذهب غلط يرجع لا شي.
def test_controller_returns_imam(controller):
    view = controller.get_imam(3)
    assert view.profile.born == 150 and view.madhab.madhab_id == 3
    # رقم الصفحة المطبوع ١٣٤ هو الصفحة ١٢٨ في الموقع، لأن الموقع يعدّ المقدمات بفرق ستة.
    assert view.source.page_url(134).endswith("/128")
    assert controller.get_imam(9) is None
