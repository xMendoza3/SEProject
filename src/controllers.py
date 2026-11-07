"""
ملف المتحكمات: ينسّق بين الطبقات.

المتحكم ما يسوي الشغل بنفسه. يعرف بس مين يسويه وبأي ترتيب.
والواجهة تكلم المتحكم بس، وما تكلم قاعدة البيانات مباشرة.
"""

from collections import defaultdict
from dataclasses import dataclass

from src.database import DatabaseManager
from src.exporter import EXPORT_FORMATS, Exporter
from src.extractor import OpinionExtractor
from src.map_data import MapRepository
from src.models import (Bookmark, Chapter, ImamProfile, MapMention, MapRegion, Madhab, Opinion,
                        Page, Source)
from src.parser import PageParser
from src.profiles import ProfileRepository
from src.scraper import BoundaryScraper, FiqhScraper


# ============================================ ما يرجعه المتحكم للواجهة
# نتائج البحث: أبواب طابق عنوانها، وأقوال طابق نصها، وعناوين أبواب هذي الأقوال.
@dataclass(frozen=True)
class SearchResults:
    query: str
    chapters: list[Chapter]
    opinions: list[Opinion]
    titles: dict[int, str]

    def is_empty(self) -> bool:
        return not self.chapters and not self.opinions


# كل اللي تحتاجه الواجهة عشان تعرض باب:
# الباب، ومساره من الجزء لين الباب، وصفحته، وأقواله مقسمة حسب المذهب.
@dataclass(frozen=True)
class ChapterView:
    chapter: Chapter
    path: list[Chapter]
    page: Page
    opinions_by_madhab: dict[int, list[Opinion]]


# كل اللي تحتاجه الواجهة عشان ترسم خريطة المذاهب:
# المصادر بمعرفاتها، والمناطق الملونة، والمناطق المذكورة بدون تلوين،
# وحدود المحافظات للدول المقسومة. الحدود لا شي لو ما تحمّلت بعد.
@dataclass(frozen=True)
class MadhabMap:
    sources: dict[str, Source]
    regions: list[MapRegion]
    mentions: list[MapMention]
    shapes: dict | None


# صفحة الإمام: المذهب، والنبذة، ومصدرها.
@dataclass(frozen=True)
class ImamView:
    madhab: Madhab
    profile: ImamProfile
    source: Source


# ===================================================== متحكم المستكشف
class ExplorerController:

    def __init__(self, db=None, exporter=None, atlas=None, profiles=None):
        self._db = db or DatabaseManager()
        self._exporter = exporter or Exporter()
        self._atlas = atlas or MapRepository()
        self._profiles = profiles or ProfileRepository()

    # هل قاعدة البيانات فيها الكتاب؟ لو لا، لازم نشغّل الاستيراد أول.
    def is_ready(self) -> bool:
        return self._db.get_stats()["chapters"] > 0

    def get_madhabs(self) -> list[Madhab]:
        return self._db.get_madhabs()

    def get_stats(self) -> dict:
        return self._db.get_stats()

    # ------------------------------------------------------- البحث
    # من الإصدار الأول. نبحث في العناوين وفي الأقوال،
    # ونخلي من الأقوال بس اللي تخص المذاهب المختارة.
    def receive_query(self, query: str, madhab_ids) -> SearchResults:
        wanted = set(madhab_ids)
        chapters = self._db.search_index(query)
        opinions = [o for o in self._db.search_text(query)
                    if wanted.intersection(o.madhab_ids)]
        titles = self._db.get_titles(o.chapter_id for o in opinions)
        return SearchResults(query, chapters, opinions, titles)

    # ------------------------------------------------------ التصفح
    # الأبواب اللي تحت باب معيّن. بدون أب ترجع الأجزاء الخمسة.
    def browse(self, parent_id: int | None) -> list[Chapter]:
        return self._db.get_children(parent_id)

    # مسار الباب: نطلع من الباب لأبوه ثم لجده، لين نوصل للجزء،
    # ثم نقلب القائمة عشان تبدأ من الجزء.
    def get_path(self, chapter_id: int) -> list[Chapter]:
        path = []
        current = self._db.get_chapter(chapter_id, with_opinions=False)
        while current is not None:
            path.append(current)
            if current.parent_id is None:
                break
            current = self._db.get_chapter(current.parent_id, with_opinions=False)
        return list(reversed(path))

    # ------------------------------------------------------ القراءة
    # تجهّز الباب للعرض: لكل مذهب مختار، قائمة أقواله.
    # القول المشترك يظهر عند كل مذهب من مذاهبه المختارة.
    def open_chapter(self, chapter_id: int, madhab_ids) -> ChapterView | None:
        chapter = self._db.get_chapter(chapter_id)
        if chapter is None:
            return None
        by_madhab = defaultdict(list)
        for opinion in chapter.get_opinions(madhab_ids):
            for madhab_id in opinion.madhab_ids:
                if madhab_id in madhab_ids:
                    by_madhab[madhab_id].append(opinion)
        return ChapterView(
            chapter=chapter,
            path=self.get_path(chapter_id),
            page=self._db.get_page(chapter.page_id),
            opinions_by_madhab=dict(by_madhab),
        )

    def get_page(self, page_id: int) -> Page | None:
        return self._db.get_page(page_id)

    # ------------------------------------------------------ المفضلة
    def add_bookmark(self, chapter_id: int, opinion_id: int | None = None,
                     note: str = "") -> Bookmark:
        return self._db.add_bookmark(Bookmark(chapter_id, opinion_id, note.strip()))

    # كل مفضلة ومعها عنوان بابها.
    def get_bookmarks(self) -> list[tuple[Bookmark, str]]:
        bookmarks = self._db.get_bookmarks()
        titles = self._db.get_titles(b.chapter_id for b in bookmarks)
        return [(b, titles.get(b.chapter_id, "")) for b in bookmarks]

    def remove_bookmark(self, bookmark_id: int):
        self._db.remove_bookmark(bookmark_id)

    # ------------------------------------------------------- النسخ
    # نص قول واحد مع مصدره، جاهز للنسخ واللصق.
    # المتحكم يجيب صفحة القول، والمصدّر يرتب النص.
    def quote_opinion(self, opinion: Opinion, chapter_title: str) -> str:
        page = self._db.get_page(opinion.page_id)
        return self._exporter.to_text(opinion, chapter_title, page)

    # ------------------------------------------------------ التصدير
    # الصيغة امتداد الملف: وورد أو PDF. والصيغ المتاحة في قاموس الصيغ في ملف التصدير.
    # ملف للباب، فيه المذاهب المختارة بس.
    def export(self, chapter_id: int, madhab_ids, fmt: str = "docx") -> bytes:
        view = self.open_chapter(chapter_id, madhab_ids)
        page_ids = [o.page_id for o in view.chapter.opinions] + [view.chapter.page_id]
        return self._exporter.chapter_file(view, self._madhab_names(), self._pages(page_ids),
                                           sorted(madhab_ids), fmt)

    # ملف لكل المفضلة. لكل مفضلة نجيب بابها، وقولها لو كانت لقول.
    def export_bookmarks(self, fmt: str = "docx") -> bytes:
        entries = []
        chapters = {}
        for bookmark in self._db.get_bookmarks():
            if bookmark.chapter_id not in chapters:
                chapters[bookmark.chapter_id] = self._db.get_chapter(bookmark.chapter_id)
            chapter = chapters[bookmark.chapter_id]
            if chapter is None:
                continue
            # أول قول رقمه يطابق، ولو ما فيه نرجع لا شي.
            opinion = next((o for o in chapter.opinions
                            if o.opinion_id == bookmark.opinion_id), None)
            entries.append((bookmark, chapter, opinion))
        page_ids = [c.page_id for _, c, _ in entries] + \
                   [o.page_id for _, _, o in entries if o is not None]
        return self._exporter.bookmarks_file(entries, self._madhab_names(),
                                             self._pages(page_ids), fmt)

    def export_file_name(self, title: str, fmt: str = "docx") -> str:
        return Exporter.file_name(title, fmt)

    # الصيغ اللي تقدر الواجهة تعرضها، كل صيغة وكاتبها.
    @staticmethod
    def export_formats() -> dict:
        return EXPORT_FORMATS

    # ------------------------------------------------------ الخريطة
    # المتحكم يجمع من مستودع الخريطة، والواجهة هي اللي ترسم.
    def get_madhab_map(self) -> MadhabMap:
        return MadhabMap(
            sources=self._atlas.get_sources(),
            regions=self._atlas.get_regions(),
            mentions=self._atlas.get_mentions(),
            shapes=self._atlas.get_shapes(),
        )

    # -------------------------------------------------- نبذة الإمام
    # لا شي لو رقم المذهب غلط، والواجهة ترجع لشاشة البداية.
    def get_imam(self, madhab_id: int) -> ImamView | None:
        profile = self._profiles.get_profile(madhab_id)
        madhab = next((m for m in self.get_madhabs() if m.madhab_id == madhab_id), None)
        if profile is None or madhab is None:
            return None
        return ImamView(madhab=madhab, profile=profile, source=self._profiles.get_source())

    def _madhab_names(self) -> dict[int, str]:
        return {m.madhab_id: m.name for m in self._db.get_madhabs()}

    def _pages(self, page_ids) -> dict[int, Page]:
        return {page_id: self._db.get_page(page_id) for page_id in set(page_ids)}

    # تقفل اتصال قاعدة البيانات. الواجهة تناديها لما يطلع المستخدم من التطبيق.
    def close(self):
        self._db.close()


# ===================================================== متحكم الاستيراد
class ImportController:

    # الخدمات تنمرر من برا، ولو ما انمررت ننشئ الافتراضية.
    # فايدتها في الاختبار: تقدر تعطيه قاعدة بيانات في الذاكرة بدل الملف الحقيقي.
    def __init__(self, scraper=None, parser=None, extractor=None, db=None,
                 boundaries=None, atlas=None):
        self._scraper = scraper or FiqhScraper()
        self._parser = parser or PageParser()
        self._extractor = extractor or OpinionExtractor()
        self._db = db or DatabaseManager()
        self._boundaries = boundaries or BoundaryScraper()
        self._atlas = atlas or MapRepository()

    # تشغّل الاستيراد كامل. الدالة اللي تنمرر تستقبل رسائل التقدم.
    def run(self, report=print) -> dict:
        report("1/5 loading book data")
        index = self._scraper.fetch_index()
        book = self._scraper.fetch_book()

        report("2/5 parsing pages and chapters")
        pages = self._parser.parse_pages(book["pages"])
        chapters = self._parser.parse_chapters(index["indexes"])
        blocks_by_chapter = defaultdict(list)
        for block in self._parser.parse_blocks(book["pages"]):
            blocks_by_chapter[block.chapter_id].append(block)

        report("3/5 extracting opinions")
        chapters = [self._extractor.extract(chapter, blocks_by_chapter[chapter.chapter_id])
                    for chapter in chapters]

        report("4/5 saving to the database")
        self._db.replace_book(pages, chapters)

        report("5/5 loading region boundaries for the map")
        self._fetch_boundaries(report)
        return self._db.get_stats()

    # الخطوة الأخيرة اختيارية: لو ما فيه إنترنت، الكتاب انحفظ عادي،
    # والخريطة بس تنتظر لين يشتغل الاستيراد مرة ثانية والجهاز متصل.
    # أخطاء الشبكة والملفات كلها من نوع خطأ النظام، والملف التالف خطأ قيمة،
    # والمفتاح الناقص في رد الموقع خطأ مفتاح.
    def _fetch_boundaries(self, report):
        for country in self._atlas.split_countries():
            try:
                self._boundaries.fetch_regions(country, self._atlas.shapes_file(country))
            except (OSError, ValueError, KeyError) as error:
                report(f"    skipped {country}: {error}")
