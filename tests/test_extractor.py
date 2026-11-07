"""
اختبارات المستخرج: صاحب كل قول، ووين ينتهي، والأدلة اللي فيه.
"""

import re

from src.extractor import OpinionExtractor
from src.models import Chapter, TextBlock

CHAPTER = Chapter(1, "باب للتجربة", 3, None, 1)


# تشغّل المستخرج على قطع نص. كل قطعة معها مكانها: متن أو حاشية.
def extract(*pieces) -> Chapter:
    blocks = [TextBlock(1, 1, location, text) for location, text in pieces]
    return OpinionExtractor().extract(CHAPTER, blocks)


def test_each_madhab_gets_its_own_opinion():
    chapter = extract(("footnote", "(١) الحنفية قالوا: تجب.\nالمالكية قالوا: تسن."))
    assert [o.madhab_ids for o in chapter.opinions] == [(1,), (2,)]
    assert chapter.opinions[1].text == "المالكية قالوا: تسن."


# المؤلف يجمع المذاهب المتفقة في عبارة وحدة، فالقول يكون لأكثر من مذهب.
def test_shared_opinion():
    chapter = extract(("footnote", "الشافعية، والحنابلة قالوا: لا تصح."))
    assert chapter.opinions[0].madhab_ids == (3, 4)


# الأخطاء الكتابية المعروفة في الكتاب تنصلح قبل ما ننسب القول.
def test_known_typo_is_fixed():
    chapter = extract(("footnote", "الحنبابلة قالوا: تكره."))
    assert chapter.opinions[0].madhab_ids == (4,)


# صاحبا أبي حنيفة مو المذهب الحنفي نفسه، فما ننسب قولهم للمذهب.
def test_hanafi_companions_are_not_the_madhab():
    chapter = extract(("footnote", "المالكية، والصاحبان من الحنفية قالوا: تجوز."))
    assert chapter.opinions[0].madhab_ids == (2,)


# كلام عن اتفاق الأئمة يقفل القول المفتوح، ويروح لنص الباب.
def test_general_statement_goes_to_chapter_text():
    chapter = extract(("footnote", "الحنفية قالوا: تجب.\nواتفق الأئمة على أنها مشروعة."))
    assert chapter.opinions[0].text == "الحنفية قالوا: تجب."
    assert chapter.content == "واتفق الأئمة على أنها مشروعة."


# الدقة قبل الشمول: سطر في المتن يبدأ بواو ممكن يكون تكملة جملة قبله،
# فما نعتبره بداية قول، ويبقى في نص الباب.
def test_main_text_line_starting_with_waw_is_not_attributed():
    chapter = extract(("main", "والحنفية قالوا: كذا."))
    assert chapter.opinions == ()
    assert chapter.content == "والحنفية قالوا: كذا."


# سطر حقيقي من الكتاب، صفحة ٤٧٥: النقطة ناقصة قبل قول الحنفية.
# بداية القول وسط السطر لازم تجي بعد علامة نهاية جملة، فالمستخرج ما يخمّن،
# ويبقى الكلام في قول المالكية. هذا من الحدود المعروفة المكتوبة في التوثيق.
def test_no_split_without_end_of_sentence():
    line = "المالكية قالوا: الأحق بالصلاة على الميت الخليفة، وأما نئبه فلا الحنفية قالوا: له في التقدم"
    chapter = extract(("footnote", line))
    assert [o.madhab_ids for o in chapter.opinions] == [(2,)]


def test_evidence_is_found_in_order():
    text = 'الحنفية قالوا: لقوله تعالى: ﴿أَقِيمُوا الصَّلَاةَ﴾ ولقوله ﷺ: "صلوا كما رأيتموني أصلي".'
    evidence = extract(("footnote", text)).opinions[0].evidence
    assert [e.kind for e in evidence] == ["quran", "hadith"]
    assert evidence[0].text == "﴿أَقِيمُوا الصَّلَاةَ﴾"


# أرقام الأقوال تكمل عبر الكتاب كله، ما تبدأ من جديد في كل باب.
def test_ids_continue_across_chapters():
    extractor = OpinionExtractor()
    first = extractor.extract(CHAPTER, [TextBlock(1, 1, "footnote", "الحنفية قالوا: أ.")])
    second = extractor.extract(Chapter(2, "باب ثاني", 3, None, 1),
                               [TextBlock(2, 1, "footnote", "المالكية قالوا: ب.")])
    assert first.opinions[0].opinion_id == 1
    assert second.opinions[0].opinion_id == 2


# ولا حرف يضيع: كل حرف عربي دخل المستخرج يطلع، يا في قول يا في نص الباب.
def test_no_letter_is_lost():
    text = ("(١) الحنفية قالوا: تجب.\nالمالكية، والشافعية قالوا: تسن.\n"
            "واتفق الأئمة على أنها مشروعة.\nالحنابلة قالوا: تكره.")
    chapter = extract(("footnote", text))
    output = chapter.content + "".join(o.text for o in chapter.opinions)
    letters = lambda s: sorted(re.findall(r"[ء-ي]", s))
    assert letters(output) == letters(text)
