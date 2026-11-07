"""
ملف المحلل: يحوّل بيانات الكتاب الخام إلى كائنات النماذج.

يطلّع ثلاث قوائم:
- الصفحات: كل صفحة مقسومة إلى متن وحواشي.
- الأبواب: شجرة العناوين من الفهرس.
- القطع: نص الكتاب مقطّع، وكل قطعة معروف بابها وصفحتها ومكانها.

المحلل ما يدوّر على أقوال المذاهب. هذي مهمة المستخرج في الخطوة الجاية.
"""

# مكتبة الأنماط: نوصف فيها شكل النص اللي ندوّر عليه.
import re

from src.models import Chapter, Page, TextBlock


# ====================================================== الأنماط
# الخط اللي يفصل المتن عن الحواشي: سطر فيه تسع شرطات سفلية.
# فحصنا الكتاب كامل، وطلع إنه نفس الشكل في كل الصفحات.
SEPARATOR = "\n_________\n"

# علامة بداية عنوان داخل النص، والقوسين يمسكون رقمه في الفهرس.
TITLE_MARKER = re.compile(r'<span data-type="title" id=toc-(\d+)>')

# أي وسم من وسوم صفحات الويب، نشيله عشان يبقى النص نظيف.
ANY_TAG = re.compile(r"<[^>]+>")

# علامة حاشية داخل المتن: رقم بأرقام الكتاب بين قوسين.
FOOTNOTE_MARKER = re.compile(r"\(([٠-٩]+)\)")

# بداية حاشية جديدة: نفس العلامة لكن في أول السطر.
# الخيار الأخير يخلي علامة أول السطر تنطبق على كل سطر، مو أول النص بس.
FOOTNOTE_START = re.compile(r"^\(([٠-٩]+)\)", re.MULTILINE)

# تشكيل يدوي لعناوين تحتمل أكثر من قراءة، ورقم كل عنوان في الفهرس.
# الشَّعر بالفتح هو شعر الرأس، والشِّعر بالكسر هو القصائد.
# حددنا القراءة من موضوع الباب نفسه، وما غيّرنا أي حرف من العنوان.
TITLE_DIACRITICS = {
    178: "شد الشَّعر على مؤخر الرأس عند الدخول في الصلاة أو بعده",
    201: "إنشاد الشِّعر بالمسجد",
    521: "لبس الثوب المصبوغ بما له رائحة طيبة، وإزالة الشَّعر",
    526: "الاكتحال بما فيه طيب، دهن الشَّعر والبدن",
    589: "[الشَّعر]",
    590: "حكم إزالة الشَّعر وقص الأظافر",
    591: "حكم صباغة الشَّعر",
}

# الكتاب المطبوع خمسة أجزاء، والفهرس يسمي أعلى مستوى فيه: الجزء الأول، الجزء الثاني...
# في التطبيق نسميها أقساماً: القسم الأول، القسم الثاني...
# اخترنا القسم لأن المؤلف نفسه يسميها كذا في مقدماته: قسم العبادات، قسم المعاملات.
# وما اخترنا الباب، لأن الباب في كتب الفقه أصغر من الكتاب، مثل باب داخل كتاب الطهارة.
# التغيير في العناوين بس. نص الكتاب ما ينلمس، والتوثيق يبقى بالجزء والصفحة،
# لأنه اللي يدلك على مكان القول في الكتاب الورقي.
# فحصنا الفهرس كامل: الكلمة ما تجي إلا في الأجزاء الخمسة ومقدماتها، ثمانية عناوين.
VOLUME_WORD = "الجزء"
SECTION_WORD = "القسم"

# نص ما فيه إلا نقاط ومسافات.
# الكتاب يحطه بدل المتن لما الصفحة كلها حواشي.
ONLY_DOTS = re.compile(r"[\s.]*")


class PageParser:

    # ================================================== الصفحات
    # تحوّل صفحة خام وحدة إلى كائن صفحة.
    def parse_page(self, raw: dict, page_id: int) -> Page:
        # نقسم النص عند الخط: اللي قبله متن، واللي بعده حواشي.
        # لو ما فيه خط، الحواشي تطلع فاضية، والشرطة السفلية تعني: ما نحتاج هالجزء.
        main, _, footnotes = raw["text"].partition(SEPARATOR)
        return Page(
            page_id=page_id,
            volume=int(raw["vol"]),
            printed_page=int(raw["page"]),
            main_text=self._clean(main),
            footnote_text=self._clean(footnotes),
        )

    # تحوّل كل صفحات الكتاب.
    # نبدأ العد من واحد، لأن أول صفحة رقمها واحد في الشاملة.
    def parse_pages(self, raw_pages: list[dict]) -> list[Page]:
        return [self.parse_page(raw, page_id)
                for page_id, raw in enumerate(raw_pages, start=1)]

    # ================================================== الأبواب
    # تبني شجرة الأبواب من الفهرس.
    # الفهرس قائمة مسطحة، كل عنوان فيها معه مستواه بس،
    # وإحنا نبي نعرف لكل عنوان: مين العنوان اللي فوقه؟
    def parse_chapters(self, index: dict) -> list[Chapter]:
        chapters = []
        # قائمة نستخدمها كمكدس: فيها سلسلة العناوين المفتوحة حالياً،
        # من الجزء لين آخر عنوان قريناه.
        open_chapters = []

        for chapter_id, heading in enumerate(index["headings"], start=1):
            level = heading["level"]
            # العنوان الجديد يقفل كل عنوان مفتوح بنفس مستواه أو أعمق منه،
            # فنشيلهم من آخر المكدس.
            while open_chapters and open_chapters[-1].level >= level:
                open_chapters.pop()
            # الأب هو آخر عنوان باقي في المكدس. ولو المكدس فاضي، ما له أب.
            parent_id = open_chapters[-1].chapter_id if open_chapters else None

            # العنوان المشكّل يدوياً لو موجود، وإلا عنوان الفهرس.
            # وبعدها نبدّل كلمة الجزء بكلمة القسم.
            title = TITLE_DIACRITICS.get(chapter_id, heading["title"].strip())
            chapter = Chapter(
                chapter_id=chapter_id,
                title=title.replace(VOLUME_WORD, SECTION_WORD),
                level=level,
                parent_id=parent_id,
                page_id=heading["page"],
            )
            chapters.append(chapter)
            open_chapters.append(chapter)

        return chapters

    # ==================================================== القطع
    # تقطّع نص الكتاب كله، وتحدد لكل قطعة بابها.
    #
    # القاعدتين الأساسيتين:
    # المتن: اللي قبل علامة العنوان للباب القديم، واللي بعدها للباب الجديد.
    # الحاشية: تتبع الباب اللي ظهرت علامتها في متنه، حتى لو كملت في صفحات بعدها.
    def parse_blocks(self, raw_pages: list[dict]) -> list[TextBlock]:
        blocks = []
        # الباب اللي وصل له المتن حالياً.
        current_chapter = None
        # الباب صاحب آخر حاشية، عشان لو كملت في الصفحة اللي بعدها نعرف لمين.
        footnote_chapter = None

        for page_id, raw in enumerate(raw_pages, start=1):
            main, _, footnotes = raw["text"].partition(SEPARATOR)
            # الباب اللي كنا فيه أول الصفحة، نحتاجه احتياط تحت.
            chapter_at_start = current_chapter

            # -------------------------------------------- المتن
            # نقسم المتن عند كل علامة عنوان.
            # كل قطعة تنحفظ مع الباب اللي كان مفتوح وقتها.
            pieces = []
            position = 0
            for marker in TITLE_MARKER.finditer(main):
                pieces.append((current_chapter, main[position:marker.start()]))
                current_chapter = int(marker.group(1))
                position = marker.end()
            # آخر قطعة: من آخر علامة لين نهاية المتن.
            pieces.append((current_chapter, main[position:]))

            # قاموس: كل رقم حاشية، وش الباب اللي ظهرت علامته في متنه.
            footnote_owner = {}
            for chapter_id, piece in pieces:
                for number in FOOTNOTE_MARKER.findall(piece):
                    # لو الرقم تكرر في نفس الصفحة، نعتمد أول ظهور.
                    footnote_owner.setdefault(number, chapter_id)
                text = self._clean(piece)
                if text and chapter_id is not None:
                    blocks.append(TextBlock(chapter_id, page_id, "main", text))

            # ------------------------------------------ الحواشي
            # نلقى مكان بداية كل حاشية مرقمة.
            starts = list(FOOTNOTE_START.finditer(footnotes))

            # النص اللي قبل أول رقم: تكملة لحاشية من صفحة قبل.
            # فيتبع صاحب آخر حاشية، ولو ما فيه، يتبع باب أول الصفحة.
            first_start = starts[0].start() if starts else len(footnotes)
            continuation = self._clean(footnotes[:first_start])
            owner = footnote_chapter or chapter_at_start
            if continuation and owner is not None:
                blocks.append(TextBlock(owner, page_id, "footnote", continuation))

            # كل حاشية مرقمة: من رقمها لين بداية الحاشية اللي بعدها.
            for i, start in enumerate(starts):
                end = starts[i + 1].start() if i + 1 < len(starts) else len(footnotes)
                number = start.group(1)
                # صاحبها: الباب اللي فيه علامتها.
                # ولو ما لقينا علامتها، وهذا صار ثلاث مرات بس في الكتاب كله،
                # نعطيها لصاحب الحاشية اللي قبلها.
                owner = footnote_owner.get(number, footnote_chapter or chapter_at_start)
                text = self._clean(footnotes[start.start():end])
                if text and owner is not None:
                    blocks.append(TextBlock(owner, page_id, "footnote", text))
                footnote_chapter = owner

        return blocks

    # ================================================== مساعدة
    # تنظّف النص: تشيل وسوم صفحات الويب والمسافات الزايدة.
    # ولو ما بقى إلا نقاط، ترجع نص فاضي.
    # الكلمة اللي فوق الدالة معناها: الدالة ما تحتاج الكائن نفسه.
    @staticmethod
    def _clean(text: str) -> str:
        text = ANY_TAG.sub("", text).strip()
        if ONLY_DOTS.fullmatch(text):
            return ""
        return text


# ======================================================= التجربة
if __name__ == "__main__":
    import json
    from collections import Counter
    from pathlib import Path

    # نحسب مكان مجلد المشروع من مكان هذا الملف نفسه،
    # عشان التجربة تشتغل مهما كان المجلد اللي شغّلتها منه.
    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / "data" / "raw"

    book = json.loads((raw_dir / "turath_9849_book.json").read_text(encoding="utf-8"))
    info = json.loads((raw_dir / "turath_9849_info.json").read_text(encoding="utf-8"))

    parser = PageParser()
    pages = parser.parse_pages(book["pages"])
    chapters = parser.parse_chapters(info["indexes"])
    blocks = parser.parse_blocks(book["pages"])

    print("pages:          ", len(pages))
    print("chapters:       ", len(chapters))
    print("top level:      ", sum(1 for c in chapters if c.parent_id is None))
    print("blocks:         ", len(blocks), dict(Counter(b.location for b in blocks)))

    chapters_with_text = {b.chapter_id for b in blocks}
    print("empty chapters: ", len(chapters) - len(chapters_with_text))

    # نفس الصفحة اللي فحصناها في الشاملة: ٣٠٨.
    print()
    print("page 308:       ", pages[307].citation())
    for block in blocks:
        if block.page_id == 308:
            print(f"  chapter {block.chapter_id}  {block.location:<8}  {block.text[:50]}")

    # سلسلة الآباء لباب صلاة التراويح، من الباب لين الجزء.
    print()
    by_id = {c.chapter_id: c for c in chapters}
    chapter = by_id[267]
    while chapter is not None:
        print(f"  level {chapter.level}: {chapter.title}")
        chapter = by_id.get(chapter.parent_id)
