"""
ملف قاعدة البيانات: المستودع اللي يحفظ الكتاب ويقرأ منه.

هذا تطبيق لنمط المستودع: باقي المشروع يطلب من هنا كائنات جاهزة،
مثل باب أو قول أو مفضلة، وما يعرف شي عن الجداول ولا لغة الاستعلام.
لو قررنا بكرة نغيّر نوع قاعدة البيانات، نعدّل هذا الملف بس.
"""

# مكتبة قاعدة البيانات اللي تجي مع بايثون، ما تحتاج تثبيت.
import re
import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from src.models import MADHABS, Bookmark, Chapter, Evidence, Madhab, Opinion, Page


# مكان ملف قاعدة البيانات الافتراضي: داخل مجلد البيانات في المشروع.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "fiqh.db"


# ===================================================== الجداول
# كل جدول يقابل كلاس من النماذج.
# الأعمدة اللي تبدأ بكلمة البحث فيها نسخة موحّدة من النص، نستخدمها للبحث بس.
# جدول ربط الأقوال بالمذاهب يحل علاقة متعدد لمتعدد:
# القول الواحد لأكثر من مذهب، والمذهب الواحد له أقوال كثيرة.
SCHEMA = """
CREATE TABLE IF NOT EXISTS madhabs (
    madhab_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    imam        TEXT NOT NULL,
    biography   TEXT NOT NULL DEFAULT '',
    regions     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pages (
    page_id       INTEGER PRIMARY KEY,
    volume        INTEGER NOT NULL,
    printed_page  INTEGER NOT NULL,
    main_text     TEXT NOT NULL,
    footnote_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chapters (
    chapter_id     INTEGER PRIMARY KEY,
    title          TEXT NOT NULL,
    level          INTEGER NOT NULL,
    parent_id      INTEGER REFERENCES chapters (chapter_id),
    page_id        INTEGER NOT NULL REFERENCES pages (page_id),
    content        TEXT NOT NULL,
    search_title   TEXT NOT NULL,
    search_content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opinions (
    opinion_id  INTEGER PRIMARY KEY,
    chapter_id  INTEGER NOT NULL REFERENCES chapters (chapter_id),
    page_id     INTEGER NOT NULL REFERENCES pages (page_id),
    location    TEXT NOT NULL CHECK (location IN ('main', 'footnote')),
    text        TEXT NOT NULL,
    search_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opinion_madhabs (
    opinion_id INTEGER NOT NULL REFERENCES opinions (opinion_id),
    madhab_id  INTEGER NOT NULL REFERENCES madhabs (madhab_id),
    PRIMARY KEY (opinion_id, madhab_id)
);

CREATE TABLE IF NOT EXISTS evidence (
    opinion_id INTEGER NOT NULL REFERENCES opinions (opinion_id),
    position   INTEGER NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('quran', 'hadith')),
    text       TEXT NOT NULL,
    PRIMARY KEY (opinion_id, position)
);

CREATE TABLE IF NOT EXISTS bookmarks (
    bookmark_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id     INTEGER NOT NULL,
    opinion_id     INTEGER,
    opinion_anchor TEXT,
    note           TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chapters_parent ON chapters (parent_id);
CREATE INDEX IF NOT EXISTS idx_opinions_chapter ON opinions (chapter_id);
"""

# ملاحظة على جدول المفضلة: ما ربطناه بجدول الأبواب،
# لأن إعادة الاستيراد تمسح الأبواب وترجعها، والمفضلة لازم تبقى.
# وأرقام الأبواب ثابتة، لأنها جاية من فهرس الكتاب.

# جداول محتوى الكتاب، مرتبة من الفرع للأصل.
# الحذف لازم يمشي بهالترتيب، لأن الفرع يشير للأصل.
BOOK_TABLES = ("evidence", "opinion_madhabs", "opinions", "chapters", "pages")

# طول البصمة اللي نحفظها من نص القول في المفضلة.
ANCHOR_LENGTH = 80

# أقل طول لكلمة البحث بعد التوحيد.
MIN_QUERY_LENGTH = 2

# أقصى عدد نتائج نرجعه في البحث.
MAX_RESULTS = 200


# ==================================================== توحيد النص
# الحركات والتطويل: نشيلها وقت البحث.
_TASHKEEL = re.compile(r"[ً-ْٰـ]")

# حروف لها أكثر من شكل: نوحّدها وقت البحث.
# فالباحث يكتب الصلاة أو الصلاه ويلقى نفس النتائج.
_UNIFY_LETTERS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
})

_SPACES = re.compile(r"\s+")


class DatabaseManager:

    # ==================================================== الاتصال
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        # الشرطة السفلية في أول الاسم تقابل علامة السالب في المخطط: خاص.
        self._db_path = db_path
        # كل مستخدم له اتصاله الخاص، لكن المكتبة ممكن تشغّل صفحته على أكثر من خيط.
        # الخيار الثاني يسمح بهذا، لأن الاتصال يمنعه افتراضياً.
        self._connection = sqlite3.connect(db_path, check_same_thread=False)
        # يخلي كل صف يرجع مثل القاموس، فنقرأ العمود باسمه بدل رقمه.
        self._connection.row_factory = sqlite3.Row
        # قاعدة البيانات هذي ما تفحص الروابط بين الجداول إلا لو طلبنا منها.
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def close(self):
        self._connection.close()

    # تنشئ الجداول لو ما كانت موجودة، وتضيف المذاهب الأربعة.
    def _create_tables(self):
        # الكتلة هذي معاملة: لو صار خطأ في نصها، كل التغييرات تتلغى.
        with self._connection:
            self._connection.executescript(SCHEMA)
            # الأمر يتجاهل المذهب لو كان موجود، فتشغيله مرتين ما يضر.
            self._connection.executemany(
                "INSERT OR IGNORE INTO madhabs VALUES (?, ?, ?, ?, ?)",
                [(m.madhab_id, m.name, m.imam, m.biography, m.regions) for m in MADHABS],
            )

    # ===================================================== الحفظ
    # تستبدل محتوى الكتاب كامل بالنسخة الجديدة، في معاملة وحدة.
    # يعني إما ينحفظ الكتاب كامل، أو ما يتغير شي.
    # فلو طاح البرنامج في النص، ما يبقى عندنا نصف كتاب.
    # المفضلة ما تنلمس.
    def replace_book(self, pages: list[Page], chapters: list[Chapter]):
        with self._connection:
            for table in BOOK_TABLES:
                # أسماء الجداول ما تنمرر كمعاملات، فنكتبها في النص مباشرة.
                # آمن هنا لأنها من قائمتنا الثابتة، مو من المستخدم.
                self._connection.execute(f"DELETE FROM {table}")
            self._save_pages(pages)
            self._save_chapters(chapters)
            self._save_opinions([o for chapter in chapters for o in chapter.opinions])

    def _save_pages(self, pages: list[Page]):
        # الأمر هذا ينفّذ نفس الاستعلام على قائمة كاملة، أسرع بكثير من حلقة.
        # علامات الاستفهام أماكن للقيم، والمكتبة تعبيها بأمان.
        # هذا يحمي من حقن الاستعلامات، لأن القيمة ما تنخلط مع نص الاستعلام.
        self._connection.executemany(
            "INSERT INTO pages VALUES (?, ?, ?, ?, ?)",
            [(p.page_id, p.volume, p.printed_page, p.main_text, p.footnote_text)
             for p in pages],
        )

    def _save_chapters(self, chapters: list[Chapter]):
        self._connection.executemany(
            "INSERT INTO chapters VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(c.chapter_id, c.title, c.level, c.parent_id, c.page_id, c.content,
              self._normalize(c.title), self._normalize(c.content))
             for c in chapters],
        )

    def _save_opinions(self, opinions: list[Opinion]):
        self._connection.executemany(
            "INSERT INTO opinions VALUES (?, ?, ?, ?, ?, ?)",
            [(o.opinion_id, o.chapter_id, o.page_id, o.location, o.text,
              self._normalize(o.text))
             for o in opinions],
        )
        # كل قول ومذهب في صف مستقل في جدول الربط.
        self._connection.executemany(
            "INSERT INTO opinion_madhabs VALUES (?, ?)",
            [(o.opinion_id, madhab_id) for o in opinions for madhab_id in o.madhab_ids],
        )
        # نحفظ ترتيب الدليل داخل القول، عشان نرجعه بنفس الترتيب.
        self._connection.executemany(
            "INSERT INTO evidence VALUES (?, ?, ?, ?)",
            [(o.opinion_id, position, e.kind, e.text)
             for o in opinions for position, e in enumerate(o.evidence)],
        )

    # ===================================================== البحث
    # من الإصدار الأول: البحث في عناوين الأبواب.
    def search_index(self, query: str) -> list[Chapter]:
        pattern = self._like_pattern(query)
        if pattern is None:
            return []
        rows = self._connection.execute(
            "SELECT * FROM chapters WHERE search_title LIKE ? ESCAPE '\\' "
            "ORDER BY chapter_id LIMIT ?",
            (pattern, MAX_RESULTS),
        ).fetchall()
        return [self._row_to_chapter(row) for row in rows]

    # البحث داخل نصوص الأقوال.
    def search_text(self, query: str) -> list[Opinion]:
        pattern = self._like_pattern(query)
        if pattern is None:
            return []
        return self._load_opinions(
            "WHERE search_text LIKE ? ESCAPE '\\' ORDER BY opinion_id LIMIT ?",
            (pattern, MAX_RESULTS),
        )

    # تجهّز كلمة البحث: توحّدها، وتعطّل الرموز الخاصة، وتحطها بين علامتي أي شي.
    # علامة النسبة في البحث معناها أي نص، والشرطة السفلية معناها أي حرف.
    # لو كتبها المستخدم، نبيها حرف عادي، فنحط قبلها شرطة مائلة.
    def _like_pattern(self, query: str) -> str | None:
        term = self._normalize(query)
        if len(term) < MIN_QUERY_LENGTH:
            return None
        term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{term}%"

    # ===================================================== القراءة
    # باب كامل مع نصه وأقواله وأدلتها. يرجع لا شي لو الرقم غلط.
    # ولو ما نحتاج الأقوال، مثل لما نبني مسار الباب، نطلبه خفيف بدونها.
    def get_chapter(self, chapter_id: int, with_opinions: bool = True) -> Chapter | None:
        row = self._connection.execute(
            "SELECT * FROM chapters WHERE chapter_id = ?", (chapter_id,)
        ).fetchone()
        if row is None:
            return None
        if not with_opinions:
            return self._row_to_chapter(row)
        opinions = self._load_opinions(
            "WHERE chapter_id = ? ORDER BY opinion_id", (chapter_id,)
        )
        return self._row_to_chapter(row, with_content=True, opinions=tuple(opinions))

    # عناوين مجموعة أبواب دفعة وحدة، نحتاجها لعرض نتائج البحث والمفضلة.
    def get_titles(self, chapter_ids) -> dict[int, str]:
        ids = list(set(chapter_ids))
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        rows = self._connection.execute(
            f"SELECT chapter_id, title FROM chapters WHERE chapter_id IN ({marks})", ids
        ).fetchall()
        return {row["chapter_id"]: row["title"] for row in rows}

    # الأبواب اللي تحت باب معيّن، وبدون أب ترجع الأجزاء الخمسة.
    # كلمة هل يساوي في الاستعلام تقارن صح حتى لو القيمة لا شي،
    # بعكس علامة يساوي العادية.
    def get_children(self, parent_id: int | None) -> list[Chapter]:
        rows = self._connection.execute(
            "SELECT * FROM chapters WHERE parent_id IS ? ORDER BY chapter_id",
            (parent_id,),
        ).fetchall()
        return [self._row_to_chapter(row) for row in rows]

    def get_page(self, page_id: int) -> Page | None:
        row = self._connection.execute(
            "SELECT * FROM pages WHERE page_id = ?", (page_id,)
        ).fetchone()
        if row is None:
            return None
        return Page(row["page_id"], row["volume"], row["printed_page"],
                    row["main_text"], row["footnote_text"])

    def get_madhabs(self) -> list[Madhab]:
        rows = self._connection.execute(
            "SELECT * FROM madhabs ORDER BY madhab_id"
        ).fetchall()
        return [Madhab(row["madhab_id"], row["name"], row["imam"],
                       row["biography"], row["regions"]) for row in rows]

    # أرقام عامة عن الكتاب، مفيدة لصفحة حول التطبيق.
    def get_stats(self) -> dict:
        count = lambda table: self._connection.execute(
            f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return {table: count(table)
                for table in ("pages", "chapters", "opinions", "evidence", "bookmarks")}

    # تقرأ أقوال حسب شرط، وتجيب معها مذاهبها وأدلتها.
    # ثلاث استعلامات بدل استعلام لكل قول، فتبقى سريعة حتى مع مئات الأقوال.
    def _load_opinions(self, where: str, params: tuple) -> list[Opinion]:
        rows = self._connection.execute(
            f"SELECT * FROM opinions {where}", params
        ).fetchall()
        if not rows:
            return []
        ids = [row["opinion_id"] for row in rows]
        # علامات استفهام بعدد الأقوال، مفصولة بفواصل.
        marks = ",".join("?" * len(ids))

        madhabs = {}
        for link in self._connection.execute(
                f"SELECT * FROM opinion_madhabs WHERE opinion_id IN ({marks}) "
                "ORDER BY madhab_id", ids):
            madhabs.setdefault(link["opinion_id"], []).append(link["madhab_id"])

        evidence = {}
        for item in self._connection.execute(
                f"SELECT * FROM evidence WHERE opinion_id IN ({marks}) "
                "ORDER BY position", ids):
            evidence.setdefault(item["opinion_id"], []).append(
                Evidence(item["kind"], item["text"]))

        return [
            Opinion(
                opinion_id=row["opinion_id"],
                chapter_id=row["chapter_id"],
                page_id=row["page_id"],
                madhab_ids=tuple(madhabs[row["opinion_id"]]),
                location=row["location"],
                text=row["text"],
                evidence=tuple(evidence.get(row["opinion_id"], ())),
            )
            for row in rows
        ]

    # تحوّل صف من جدول الأبواب إلى كائن باب.
    # نص الباب ما نجيبه إلا لما نحتاجه، لأن قوائم الأبواب ما تعرضه.
    @staticmethod
    def _row_to_chapter(row, with_content=False, opinions=()) -> Chapter:
        return Chapter(
            chapter_id=row["chapter_id"],
            title=row["title"],
            level=row["level"],
            parent_id=row["parent_id"],
            page_id=row["page_id"],
            content=row["content"] if with_content else "",
            opinions=opinions,
        )

    # ==================================================== المفضلة
    # تحفظ مفضلة جديدة، وترجعها ومعها رقمها من قاعدة البيانات.
    # لو كانت لقول، نحفظ أول جملة من نصه كبصمة.
    # السبب: لو أعدنا الاستيراد بعد تحسين المستخرج، أرقام الأقوال ممكن تتغير،
    # والبصمة تخلينا نلقى نفس القول حتى لو تغيّر رقمه.
    def add_bookmark(self, bookmark: Bookmark) -> Bookmark:
        anchor = None
        if bookmark.opinion_id is not None:
            row = self._connection.execute(
                "SELECT text FROM opinions WHERE opinion_id = ?", (bookmark.opinion_id,)
            ).fetchone()
            anchor = row["text"][:ANCHOR_LENGTH] if row else None
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO bookmarks (chapter_id, opinion_id, opinion_anchor, note, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (bookmark.chapter_id, bookmark.opinion_id, anchor, bookmark.note,
                 bookmark.created_at.isoformat()),
            )
        # المفضلة مجمدة، فنرجع نسخة جديدة فيها الرقم اللي عطتنا إياه القاعدة.
        return replace(bookmark, bookmark_id=cursor.lastrowid)

    # كل المفضلات، الأحدث أول.
    def get_bookmarks(self) -> list[Bookmark]:
        rows = self._connection.execute(
            "SELECT * FROM bookmarks ORDER BY created_at DESC"
        ).fetchall()
        return [
            Bookmark(
                chapter_id=row["chapter_id"],
                opinion_id=self._resolve_opinion(row),
                note=row["note"],
                created_at=datetime.fromisoformat(row["created_at"]),
                bookmark_id=row["bookmark_id"],
            )
            for row in rows
        ]

    def remove_bookmark(self, bookmark_id: int):
        with self._connection:
            self._connection.execute(
                "DELETE FROM bookmarks WHERE bookmark_id = ?", (bookmark_id,)
            )

    # تلقى القول الصحيح للمفضلة باستخدام البصمة.
    # تدوّر في نفس الباب على قول يبدأ بالبصمة، وتفضّل نفس الرقم القديم لو طابق.
    # ولو ما لقت، ترجع لا شي، فتصير المفضلة للباب كامل بدل قول غلط.
    def _resolve_opinion(self, row) -> int | None:
        if row["opinion_id"] is None or row["opinion_anchor"] is None:
            return None
        candidates = self._connection.execute(
            "SELECT opinion_id FROM opinions WHERE chapter_id = ? AND substr(text, 1, ?) = ?",
            (row["chapter_id"], len(row["opinion_anchor"]), row["opinion_anchor"]),
        ).fetchall()
        ids = [candidate["opinion_id"] for candidate in candidates]
        if row["opinion_id"] in ids:
            return row["opinion_id"]
        return ids[0] if ids else None

    # ==================================================== التوحيد
    # تحوّل النص لنسخة موحّدة للبحث: بدون حركات،
    # وبشكل واحد لكل حرف له أكثر من شكل، وبمسافة وحدة بين الكلمات.
    @staticmethod
    def _normalize(text: str) -> str:
        text = _TASHKEEL.sub("", text).translate(_UNIFY_LETTERS)
        return _SPACES.sub(" ", text).strip()


# ======================================================= التجربة
# التجربة تبني قاعدة بيانات في الذاكرة بس، مو في ملف.
# فتختبر المستودع على الكتاب كامل بدون ما تلمس ملفات المشروع.
# بناء الملف الحقيقي مهمة ملف الاستيراد في الخطوة الجاية.
if __name__ == "__main__":
    import json
    import time
    from collections import defaultdict

    from src.extractor import OpinionExtractor
    from src.parser import PageParser

    raw_dir = PROJECT_ROOT / "data" / "raw"
    book = json.loads((raw_dir / "turath_9849_book.json").read_text(encoding="utf-8"))
    info = json.loads((raw_dir / "turath_9849_info.json").read_text(encoding="utf-8"))

    parser = PageParser()
    pages = parser.parse_pages(book["pages"])
    blocks_by_chapter = defaultdict(list)
    for block in parser.parse_blocks(book["pages"]):
        blocks_by_chapter[block.chapter_id].append(block)
    extractor = OpinionExtractor()
    chapters = [extractor.extract(chapter, blocks_by_chapter[chapter.chapter_id])
                for chapter in parser.parse_chapters(info["indexes"])]

    # هذا الاسم الخاص يعني: قاعدة بيانات في الذاكرة، تختفي لما يخلص البرنامج.
    db = DatabaseManager(":memory:")
    start = time.perf_counter()
    db.replace_book(pages, chapters)
    print(f"saved in {time.perf_counter() - start:.2f}s:", db.get_stats())

    print()
    print("top level:", [c.title for c in db.get_children(None)])

    # البحث بدون همزة ولا تاء مربوطة، ويلقى النتائج.
    start = time.perf_counter()
    found = db.search_index("صلاه التراويح")
    print(f"title search ({(time.perf_counter() - start) * 1000:.0f} ms):",
          [c.title for c in found])
    start = time.perf_counter()
    found = db.search_text("عشرون ركعه")
    print(f"text search ({(time.perf_counter() - start) * 1000:.0f} ms):",
          len(found), "opinion(s)")

    print()
    chapter = db.get_chapter(267)
    page = db.get_page(chapter.page_id)
    print("chapter:", chapter.title, "|", page.citation(), "|", len(chapter.opinions), "opinions")
    names = {m.madhab_id: m.name for m in db.get_madhabs()}
    for opinion in chapter.opinions:
        who = "، ".join(names[i] for i in opinion.madhab_ids)
        print(f"  [{who}] {opinion.text[:50]}")

    print()
    saved = db.add_bookmark(Bookmark(chapter_id=267, opinion_id=chapter.opinions[0].opinion_id,
                                     note="للمراجعة"))
    print("bookmark saved with id:", saved.bookmark_id)
    print("bookmarks:", len(db.get_bookmarks()))
    db.remove_bookmark(saved.bookmark_id)
    print("after removing:", len(db.get_bookmarks()))
    db.close()
