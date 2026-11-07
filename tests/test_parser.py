"""
اختبارات المحلل: تقسيم الصفحة، وشجرة العناوين، ولمين تتبع كل قطعة نص.
"""

from src.parser import SEPARATOR, PageParser, fix_typos


# صفحة خام بنفس شكل ملف تراث: النص، ورقم الجزء، ورقم الصفحة المطبوعة.
def raw(text: str, page: int = 1) -> dict:
    return {"text": text, "vol": "1", "page": str(page)}


# علامة عنوان مثل اللي داخل نص الكتاب.
def title(chapter_id: int, text: str) -> str:
    return f'<span data-type="title" id=toc-{chapter_id}>{text}</span>'


def test_page_is_split_into_main_text_and_footnotes():
    page = PageParser().parse_page(raw("المتن <b>هنا</b>" + SEPARATOR + "(١) الحاشية"), 5)
    assert page.page_id == 5
    assert page.main_text == "المتن هنا"
    assert page.footnote_text == "(١) الحاشية"


# لما تكون الصفحة كلها حواشي، الكتاب يحط نقاط مكان المتن.
def test_dots_only_main_text_becomes_empty():
    page = PageParser().parse_page(raw(". . ." + SEPARATOR + "حاشية"), 1)
    assert page.main_text == ""


# الفهرس قائمة مسطحة فيها مستوى كل عنوان، والمحلل يحولها لشجرة.
def test_chapter_tree_from_levels():
    index = {"headings": [
        {"title": "الجزء الأول", "level": 1, "page": 1},
        {"title": "كتاب الصلاة", "level": 2, "page": 1},
        {"title": "صلاة التراويح", "level": 3, "page": 2},
        {"title": "كتاب الزكاة", "level": 2, "page": 3},
    ]}
    chapters = PageParser().parse_chapters(index)
    assert [c.parent_id for c in chapters] == [None, 1, 2, 1]


# أجزاء الكتاب ومقدماتها تنعرض أقساماً، وباقي العناوين ما تتغير.
def test_volume_titles_become_sections():
    index = {"headings": [
        {"title": "الجزء الثاني", "level": 1, "page": 1},
        {"title": "مقدمة [الجزء الثاني]", "level": 2, "page": 1},
        {"title": "كتاب الصلاة", "level": 2, "page": 2},
    ]}
    titles = [c.title for c in PageParser().parse_chapters(index)]
    assert titles == ["القسم الثاني", "مقدمة [القسم الثاني]", "كتاب الصلاة"]


# العناوين اللي تحتمل قراءتين تاخذ تشكيلها اليدوي بدل نص الفهرس.
# العنوان رقم ٥٩١ في الكتاب عن صباغة شعر الرأس.
def test_ambiguous_titles_get_diacritics():
    index = {"headings": [{"title": "حكم صباغة الشعر", "level": 1, "page": 1}] * 591}
    chapters = PageParser().parse_chapters(index)
    assert chapters[590].title == "حكم صباغة الشَّعر"
    assert chapters[0].title == "حكم صباغة الشعر"


# أهم قاعدة في المحلل: الحاشية تتبع الباب اللي ظهرت علامتها في متنه،
# حتى لو كملت في الصفحة اللي بعدها والمتن انتقل لباب ثالث.
def test_footnote_follows_its_chapter_across_pages():
    pages = [
        raw(title(1, "الباب الأول") + "\nكلام الأول (١)\n"
            + title(2, "الباب الثاني") + "\nكلام الثاني (٢)"
            + SEPARATOR + "(١) حاشية الأول\n(٢) حاشية الثاني تبدأ هنا"),
        raw(title(3, "الباب الثالث") + "\nكلام الثالث"
            + SEPARATOR + "وتكمل حاشية الثاني هنا", page=2),
    ]
    found = [(b.chapter_id, b.page_id, b.location, b.text)
             for b in PageParser().parse_blocks(pages)]

    assert (1, 1, "footnote", "(١) حاشية الأول") in found
    assert (2, 1, "footnote", "(٢) حاشية الثاني تبدأ هنا") in found
    assert (2, 2, "footnote", "وتكمل حاشية الثاني هنا") in found
    assert (3, 2, "main", "الباب الثالث\nكلام الثالث") in found


# أخطاء الكتابة تنصحح في الكلمة الكاملة بس، ومعها الفاصلة العربية بعدها.
def test_typos_are_fixed_as_whole_words():
    assert fix_typos("وجب عليه سجود السهون") == "وجب عليه سجود السهو"
    assert fix_typos("وغلا فلا، غليه، فغن") == "وإلا فلا، إليه، فإن"
    # كلمات صحيحة فيها نفس الحروف ما تتغير.
    assert fix_typos("الغلام وإغلاق الباب") == "الغلام وإغلاق الباب"


# غلا بمعنى فار على النار صحيحة، وكذلك الغل في الآية لأنها مشكلة.
def test_correct_uses_are_kept():
    for text in ("ثم غلا مرتين", "نقيع الزبيب إذا غلا واشتد", "ولا تجعل في قلوبنا غلًا"):
        assert fix_typos(text) == text


# التصحيح يصير وقت التحليل، فيوصل للصفحات والقطع والعناوين.
def test_parser_applies_typo_fixes():
    page = PageParser().parse_page(raw("لا يصح غلا يدًا بيد" + SEPARATOR + "(١) فارجع غليه"), 1)
    assert page.main_text == "لا يصح إلا يدًا بيد"
    assert page.footnote_text == "(١) فارجع إليه"
    index = {"headings": [{"title": "سجود السهون", "level": 1, "page": 1}]}
    assert PageParser().parse_chapters(index)[0].title == "سجود السهو"
