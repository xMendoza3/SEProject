"""
اختبارات المستودع: الحفظ والبحث والمفضلة، على قاعدة بيانات في الذاكرة.
"""

import sqlite3

import pytest

from src.models import Bookmark, Chapter
from tests.book import make_book


def test_book_is_saved(db):
    assert db.get_stats() == {"pages": 2, "chapters": 3, "opinions": 3,
                              "evidence": 1, "bookmarks": 0}


# القول يرجع من القاعدة بنفس مذاهبه وأدلته وترتيبها.
def test_opinions_come_back_unchanged(db):
    _, chapters = make_book()
    assert db.get_chapter(2).opinions == chapters[1].opinions


def test_children(db):
    assert [c.chapter_id for c in db.get_children(None)] == [1]
    assert [c.chapter_id for c in db.get_children(1)] == [2, 3]


# البحث يتجاهل الحركات، ويعامل الهمزات والتاء المربوطة كحرف واحد.
@pytest.mark.parametrize("query, chapter_id", [
    ("صلاة التراويح", 2),
    ("صلاه التراويح", 2),
    ("الصَّلاة", 1),
    ("الصلاه", 1),
])
def test_search_ignores_diacritics_and_letter_forms(db, query, chapter_id):
    assert chapter_id in [c.chapter_id for c in db.search_index(query)]


# رموز البحث الخاصة تنعامل كحروف عادية، فما ترجع كل الأبواب.
def test_search_wildcards_are_literal(db):
    assert db.search_index("%%") == []
    assert db.search_index("__") == []


def test_too_short_query(db):
    assert db.search_index("ص") == []


def test_search_in_opinions(db):
    found = db.search_text("عشرون ركعه")
    assert [o.madhab_ids for o in found] == [(1,)]


# الحفظ معاملة وحدة: لو صار خطأ في النص، يبقى الكتاب القديم كامل.
# هنا أول باب يشير لصفحة غير موجودة، فقاعدة البيانات ترفضه،
# والخطأ يصير بعد ما انمسح الكتاب القديم. المعاملة لازم ترجعه.
def test_replace_book_is_all_or_nothing(db):
    pages, chapters = make_book()
    broken = [Chapter(4, "باب صفحته غير موجودة", 2, None, page_id=999)] + chapters
    with pytest.raises(sqlite3.IntegrityError):
        db.replace_book(pages, broken)
    stats = db.get_stats()
    assert (stats["chapters"], stats["opinions"]) == (3, 3)


def test_bookmark_add_list_remove(db):
    saved = db.add_bookmark(Bookmark(2, opinion_id=1, note="للمراجعة"))
    assert saved.bookmark_id is not None
    assert [(b.chapter_id, b.opinion_id, b.note) for b in db.get_bookmarks()] == \
           [(2, 1, "للمراجعة")]
    db.remove_bookmark(saved.bookmark_id)
    assert db.get_bookmarks() == []


# المفضلة تبقى بعد إعادة الاستيراد، وتلقى قولها بالبصمة حتى لو تغيّر رقمه.
def test_bookmark_survives_reimport_with_new_ids(db):
    db.add_bookmark(Bookmark(2, opinion_id=2))
    db.replace_book(*make_book(first_opinion_id=101))
    assert db.get_bookmarks()[0].opinion_id == 102
