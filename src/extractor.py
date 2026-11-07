"""
ملف المستخرج: يدوّر داخل قطع النص على أقوال المذاهب ويفصلها.

لكل باب يطلّع:
- الأقوال: كل قول معروف مذهبه أو مذاهبه، وصفحته، ومكانه، وأدلته.
- نص الباب: كلام المؤلف اللي ما هو منسوب لمذهب معيّن.

القاعدة الذهبية في هذا الملف: الدقة قبل الشمول.
أي نص ما نقدر نحدد صاحبه بثقة، نتركه في نص الباب ولا ننسبه لأحد.
القارئ بيشوفه في الحالتين، لكن ما ينحط تحت مذهب غلط.
"""

import re
from dataclasses import dataclass, replace

from src.models import MADHAB_BY_NAME, Chapter, Evidence, Opinion, TextBlock


# ============================================ قاموس الأخطاء الكتابية
# كل خطأ لقيناه فعلاً في الكتاب، ومقابله الصحيح.
# ما استخدمنا أداة أقرب كلمة، لأن كلمات مثل الحنطة والمالكين كلمات صحيحة
# تشبه أسماء المذاهب، والتقريب ممكن ينسبها لمذهب بالغلط.
TYPO_FIXES = {
    "الحنيفية": "الحنفية",
    "الحنفيةن": "الحنفية",
    "المالكيةن": "المالكية",
    "الشافعيةن": "الشافعية",
    "الشافعيةـ": "الشافعية",
    "الحنبابلة": "الحنابلة",
    "الحنايلة": "الحنابلة",
    "الحناللة": "الحنابلة",
    "الحنبلة": "الحنابلة",
    "الحنابة": "الحنابلة",
    "الحنابلةن": "الحنابلة",
    "الحنابلةـ": "الحنابلة",
}


# ===================================================== قطع الأنماط
# نبني الأنماط الكبيرة من قطع صغيرة، عشان كل قطعة تنفهم لحالها.

# أي حرف عربي، مع الحركات.
LETTER = r"[ء-ْ]"

# اسم مذهب: الأسماء الأربعة الصحيحة، ومعها الأخطاء الكتابية.
# نرتبها من الأطول للأقصر، عشان الخطأ الطويل ينطبق كامل قبل الاسم القصير.
_ALL_NAMES = sorted(list(MADHAB_BY_NAME) + list(TYPO_FIXES), key=len, reverse=True)
NAME = "(?:" + "|".join(_ALL_NAMES) + ")"

# اسم مذهب كلمة مستقلة: قبله بداية أو فاصل، وبعده ما فيه حرف.
# هذا يمنع مثلاً كلمة للمالكية أو كالشافعية.
NAME_WORD = rf"(?<![^\s،(و=\-.])({NAME})(?!{LETTER})"

# قائمة مذاهب: اسم، وبعده أسماء ثانية بينها فواصل وواو.
NAME_LIST = rf"{NAME}(?:[،.\s]+و?{NAME})*"

# إضافات يكتبها المؤلف وسط قائمة المذاهب،
# مثل: وأبو يوسف من الحنفية، رحمهم الله تعالى، في أصح قوليهم.
QUALIFIER = (
    r"(?:(?:ال)?إمام\s)?(?:أبو يوسف|الصاحبان|محمد|زفر)(?:\sمن الحنفية)?"
    r"|رحمهم الله(?:\sتعالى)?|﵏"
    r"|في\s(?:أصح|إحدى|أظهر)\s" + LETTER + "+"
)
NAME_LIST_EXTENDED = rf"{NAME}(?:[،.\s\-]+و?(?:{NAME}|{QUALIFIER}))*"

# اللي ممكن يجي في أول السطر قبل اسم المذهب: رمز شارد، أو رقم حاشية.
LINE_LEAD = r"^[=\s]*(?:\([٠-٩]+\)\s*)?"


# ================================================= أنماط بداية القول
# بداية القول في أول السطر لها شكلين.
# الأول: اسم مذهب، وبعده كلام قصير، ثم كلمة قالوا.
# الثاني: قائمة مذاهب، وبعدها نقطتين أو فعل ينتهي بواو وألف، مثل اشترطوا.
# الحواشي تقبل واو أو فاء قبل الاسم. المتن ما يقبلها،
# لأن السطر في المتن ممكن يكون تكملة جملة من السطر اللي قبله.
def _line_start_patterns(prefix: str):
    with_qalu = re.compile(
        LINE_LEAD + r"(?P<body>\(?" + prefix + NAME
        + r"[^:.؛\n]{0,120}?[\s\-]*ف?قالوا)"
    )
    with_verb = re.compile(
        LINE_LEAD + r"(?P<body>\(?" + prefix + NAME_LIST
        + rf"[\s\-]*(?::|{LETTER}+وا(?!{LETTER})|يقولون|عندهم))"
    )
    return with_qalu, with_verb


LINE_START = {
    "footnote": _line_start_patterns("[وف]?"),
    "main": _line_start_patterns(""),
}

# بداية قول في وسط السطر: لازم تجي بعد نهاية جملة،
# ولازم تكون قائمة مذاهب صافية، وبعدها قالوا مباشرة.
MID_LINE_START = re.compile(
    r"(?<=[.؛)]\s)(?P<body>[وف]?" + NAME_LIST_EXTENDED + r"[\s\-]*ف?قالوا)"
)

# مذهب يقول شي داخل السطر، نستخدمه للفحص قبل ما نضيف سطر لقول مفتوح.
MADHAB_SAYING = re.compile(NAME + r"[^:.؛\n]{0,60}?(?:قالوا|يقولون)")

# سطر ينتهي باسم مذهب وفاصلة: القائمة انكسرت على سطرين، فنوصلها.
BROKEN_LIST = re.compile(rf"({NAME})،\s*\n")

# حاشية جديدة: رقم بين قوسين في أول القطعة.
NEW_FOOTNOTE = re.compile(r"^\([٠-٩]+\)")


# ================================================== أنماط نهاية القول
# كلام عام عن كل المذاهب: اتفاق أو اختلاف، أو ذكر الأئمة أو الجمهور.
GENERAL_STATEMENT = re.compile(r"^\s*[وف]?(?:اتفق|اختلف|أجمع)|الأئمة|الجمهور")

# عنوان فرعي داخل الحاشية.
HEADING_WORD = re.compile(r"^\s*(?:مبحث|مباحث|فصل|تنبيه|خاتمة)(?!" + LETTER + ")")

# نقل عن عالم من خارج المذاهب، مثل: قال الشوكاني.
# نستثني قال رسول الله وقال تعالى، لأنها أدلة داخل القول نفسه.
SCHOLAR_QUOTE = re.compile(r"^\s*[وف]?قال\s+(?!رسول|النبي|تعالى|الله|ﷺ|﵇)" + LETTER)

# علامات الترقيم والأرقام. السطر القصير اللي ما فيه ولا وحدة منها غالباً عنوان.
PUNCTUATION = re.compile(r"[،.:؛؟!()\-٠-٩0-9]")

# أصحاب أبي حنيفة: ذكرهم يعني إن الكلام عن المذهب الحنفي.
HANAFI_FIGURES = re.compile(r"أبو يوسف|أبي يوسف|الصاحبان|الصاحبين|صاحبا أبي حنيفة|محمد بن الحسن|زفر")
HANAFI_ID = MADHAB_BY_NAME["الحنفية"].madhab_id


# ====================================================== أنماط الأدلة
# الآية: كل ما بين القوسين المزخرفين.
QURAN = re.compile(r"﴿[^﴾]{1,600}﴾")

# الحديث: نص بين علامتي تنصيص أو قوسين، يجي مباشرة بعد رمز الصلاة على النبي.
# نشترط ثلاث حروف على الأقل، عشان ما نلتقط رقم حاشية مثل (١).
HADITH = re.compile(
    r"(?:ﷺ|﵇)\s*:?\s*"
    r"(?P<quote>\"[^\"\n]{3,500}\"|\([^()\n]{3,500}\)|«[^»\n]{3,500}»)"
)


# ================================================== مسودة القول
# قول ما زال مفتوح، نضيف عليه أسطر لين ينقفل.
# هذا الكلاس بالذات مو مجمد، لأنه يتغير وهو يتجمع.
# ولما ينقفل، نحوّله لكائن قول مجمد.
@dataclass
class _Draft:
    madhab_ids: tuple[int, ...]
    page_id: int
    lines: list[str]


class OpinionExtractor:

    def __init__(self):
        # رقم القول الجاي. يزيد مع كل قول عبر الكتاب كله.
        self._next_id = 1

    # =============================================== الدالة الرئيسية
    # تاخذ باب وقطعه، وترجع نسخة جديدة من الباب فيها نصه وأقواله.
    def extract(self, chapter: Chapter, blocks: list[TextBlock]) -> Chapter:
        opinions = []
        leftover = []
        # قول مفتوح لكل مكان، لأن المتن والحواشي خطين منفصلين يمشون مع بعض.
        open_drafts = {"main": None, "footnote": None}

        # تقفل القول المفتوح في مكان معيّن، وتحوله لكائن قول.
        def close(location):
            draft = open_drafts[location]
            if draft is None:
                return
            text = "\n".join(draft.lines).strip()
            opinions.append(Opinion(
                opinion_id=self._next_id,
                chapter_id=chapter.chapter_id,
                page_id=draft.page_id,
                madhab_ids=draft.madhab_ids,
                location=location,
                text=text,
                evidence=self._find_evidence(text),
            ))
            self._next_id += 1
            open_drafts[location] = None

        for block in blocks:
            location = block.location
            # حاشية جديدة تقفل أي قول مفتوح من الحاشية اللي قبلها.
            if location == "footnote" and NEW_FOOTNOTE.match(block.text):
                close(location)

            text = BROKEN_LIST.sub(r"\1، ", block.text)
            for line in text.split("\n"):
                for madhab_ids, segment in self._split_line(line, location):
                    if madhab_ids:
                        # بداية قول جديد: نقفل القديم ونفتح واحد جديد.
                        close(location)
                        open_drafts[location] = _Draft(madhab_ids, block.page_id, [segment])
                    elif open_drafts[location] and not self._ends_statement(
                            segment, open_drafts[location].madhab_ids):
                        # تكملة للقول المفتوح.
                        open_drafts[location].lines.append(segment)
                    else:
                        # كلام ما هو منسوب لمذهب: يروح لنص الباب.
                        close(location)
                        if re.search(LETTER, segment):
                            leftover.append(segment)

        close("main")
        close("footnote")
        # الباب مجمد، فما نعدّله. ننشئ نسخة جديدة منه فيها النص والأقوال.
        return replace(chapter, content="\n".join(leftover).strip(), opinions=tuple(opinions))

    # ================================================== تقسيم السطر
    # تقسم السطر عند كل بداية قول فيه.
    # ترجع قائمة أجزاء، كل جزء معه مذاهبه لو كان بداية قول، أو فاضي لو ما كان.
    def _split_line(self, line: str, location: str) -> list[tuple[tuple, str]]:
        starts = self._find_starts(line, location)
        if not starts:
            return [((), line)]
        parts = []
        # الكلام اللي قبل أول بداية.
        if starts[0][0] > 0:
            parts.append(((), line[:starts[0][0]]))
        for i, (position, madhab_ids) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(line)
            parts.append((madhab_ids, line[position:end]))
        return parts

    # تلقى بدايات الأقوال في السطر، وترجع مكان كل بداية ومذاهبها.
    def _find_starts(self, line: str, location: str) -> list[tuple[int, tuple]]:
        found = []
        # آخر مكان غطّته بداية قول، عشان ما نحسب نفس البداية مرتين.
        covered = 0
        for pattern in LINE_START[location]:
            match = pattern.match(line)
            if match and self._madhab_ids(match.group("body")):
                found.append((match.start("body"), self._madhab_ids(match.group("body"))))
                covered = match.end("body")
                break
        for match in MID_LINE_START.finditer(line):
            madhab_ids = self._madhab_ids(match.group("body"))
            if madhab_ids and match.start("body") >= covered:
                found.append((match.start("body"), madhab_ids))
                covered = match.end("body")
        return sorted(found)

    # تقرأ أسماء المذاهب من بداية القول، وترجع أرقامها مرتبة.
    # تتجاهل الاسم اللي قبله كلمة من، مثل: والصاحبان من الحنفية،
    # لأن القول هنا لصاحبي أبي حنيفة، مو للمذهب الحنفي نفسه.
    def _madhab_ids(self, text: str) -> tuple[int, ...]:
        ids = set()
        for match in re.finditer(NAME_WORD, text):
            if text[:match.start()].endswith("من "):
                continue
            name = self._fix_typo(match.group(1))
            ids.add(MADHAB_BY_NAME[name].madhab_id)
        return tuple(sorted(ids))

    # ================================================== نهاية القول
    # هل هذا السطر يقفل القول المفتوح، بدل ما يكون تكملة له؟
    def _ends_statement(self, line: str, madhab_ids: tuple[int, ...]) -> bool:
        head = line[:50]
        # كلام عام عن اتفاق الأئمة أو اختلافهم.
        general = GENERAL_STATEMENT.search(head)
        if general and general.start() < 45:
            return True
        # عنوان فرعي صريح.
        if HEADING_WORD.match(line):
            return True
        # نقل عن عالم من خارج المذاهب.
        if SCHOLAR_QUOTE.match(line):
            return True
        # سطر قصير بدون أي ترقيم: غالباً عنوان.
        stripped = line.strip()
        if len(stripped) <= 40 and not PUNCTUATION.search(stripped):
            return True
        # أول السطر يذكر مذهب ثاني غير مذهب القول.
        if self._mentioned_madhabs(head) - set(madhab_ids):
            return True
        # مذهب ثاني يقول شي في أي مكان من السطر.
        for match in MADHAB_SAYING.finditer(line):
            if self._mentioned_madhabs(match.group()) - set(madhab_ids):
                return True
        return False

    # المذاهب المذكورة في النص بأي شكل، حتى لو كان الاسم ملزّق بحرف.
    def _mentioned_madhabs(self, text: str) -> set[int]:
        ids = {MADHAB_BY_NAME[self._fix_typo(name)].madhab_id
               for name in re.findall(NAME, text)}
        if HANAFI_FIGURES.search(text):
            ids.add(HANAFI_ID)
        return ids

    # ======================================================= الأدلة
    # تلقى الآيات والأحاديث داخل نص القول، مرتبة حسب مكانها فيه.
    def _find_evidence(self, text: str) -> tuple[Evidence, ...]:
        found = [(m.start(), Evidence("quran", m.group())) for m in QURAN.finditer(text)]
        found += [(m.start("quote"), Evidence("hadith", m.group("quote")))
                  for m in HADITH.finditer(text)]
        found.sort(key=lambda item: item[0])
        return tuple(evidence for _, evidence in found)

    # ===================================================== مساعدة
    # تصحح اسم المذهب لو كان من الأخطاء المعروفة، وإلا ترجعه مثل ما هو.
    @staticmethod
    def _fix_typo(name: str) -> str:
        return TYPO_FIXES.get(name, name)


# ======================================================= التجربة
if __name__ == "__main__":
    import json
    from collections import Counter, defaultdict
    from pathlib import Path

    from src.models import MADHABS
    from src.parser import PageParser

    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / "data" / "raw"
    book = json.loads((raw_dir / "turath_9849_book.json").read_text(encoding="utf-8"))
    info = json.loads((raw_dir / "turath_9849_info.json").read_text(encoding="utf-8"))

    parser = PageParser()
    chapters = parser.parse_chapters(info["indexes"])
    blocks = parser.parse_blocks(book["pages"])

    # نجمع القطع حسب بابها.
    blocks_by_chapter = defaultdict(list)
    for block in blocks:
        blocks_by_chapter[block.chapter_id].append(block)

    extractor = OpinionExtractor()
    chapters = [extractor.extract(chapter, blocks_by_chapter[chapter.chapter_id])
                for chapter in chapters]
    opinions = [opinion for chapter in chapters for opinion in chapter.opinions]

    names = {madhab.madhab_id: madhab.name for madhab in MADHABS}
    print("opinions:            ", len(opinions))
    print("shared opinions:     ", sum(1 for o in opinions if len(o.madhab_ids) > 1))
    print("chapters with them:  ", sum(1 for c in chapters if c.opinions), "of", len(chapters))
    print("evidence:            ", dict(Counter(e.kind for o in opinions for e in o.evidence)))
    per_madhab = Counter(i for o in opinions for i in o.madhab_ids)
    for madhab_id, count in sorted(per_madhab.items()):
        print(f"  {names[madhab_id]}: {count}")

    # نفس الصفحتين اللي فحصناهم من البداية.
    for page_id in (308, 1837):
        print()
        print("page", page_id)
        for opinion in opinions:
            if opinion.page_id == page_id:
                who = "، ".join(names[i] for i in opinion.madhab_ids)
                print(f"  [{who}]  {opinion.text[:60]}")
