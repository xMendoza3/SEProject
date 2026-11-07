"""
ملف التصدير: يحوّل باب أو قائمة المفضلة إلى ملف، والقول الواحد إلى نص للنسخ.

المصدّر يقرر محتوى الملف وترتيبه، والكاتب يكتبه بصيغته، وورد أو PDF.
والمصدّر ما يكلم قاعدة البيانات: المتحكم يجهّز له البيانات، وهو يرتبها.
"""

import re
from datetime import datetime

from src.writers import DocumentWriter, DocxWriter, PdfWriter

# الصيغ المتاحة، كل صيغة وكاتبها. الواجهة تعرض زراً لكل صيغة هنا.
EXPORT_FORMATS: dict[str, type[DocumentWriter]] = {
    DocxWriter.extension: DocxWriter,
    PdfWriter.extension: PdfWriter,
}

SOURCE = "الفقه على المذاهب الأربعة، عبد الرحمن الجزيري، دار الكتب العلمية، الطبعة الثانية"
# نسخة قصيرة من المصدر، للنص المنسوخ اللي بينلصق في المحادثات.
SHORT_SOURCE = "الفقه على المذاهب الأربعة للجزيري"
DISCLAIMER = "تقسيم الأقوال آلي، والمرجع هو نص الكتاب. للدراسة والمقارنة، وليس بديلاً عن سؤال أهل العلم."


class Exporter:

    # ================================================= تصدير باب
    # الباب، ثم قسم لكل مذهب مختار فيه أقواله، ثم نص الباب.
    def chapter_file(self, view, madhab_names: dict[int, str], pages: dict, selected,
                     fmt: str = "docx") -> bytes:
        writer = EXPORT_FORMATS[fmt]()
        writer.title(view.chapter.title)
        if len(view.path) > 1:
            writer.line(" ‹ ".join(c.title for c in view.path[:-1]), small=True)
        self._source(writer, view.page)

        for madhab_id in selected:
            writer.heading(madhab_names[madhab_id], level=1)
            opinions = view.opinions_by_madhab.get(madhab_id, [])
            if not opinions:
                writer.line("لم يُستخرج قول مفصّل لهذا المذهب في هذا الباب. "
                            "راجع نص الباب.", small=True)
            for opinion in opinions:
                self._opinion(writer, opinion, madhab_id, madhab_names, pages)

        if view.chapter.content:
            writer.heading("نص الباب", level=1)
            writer.line(view.chapter.content)

        self._footer(writer)
        return writer.to_bytes()

    # =============================================== تصدير المفضلة
    # كل مفضلة: عنوان بابها، وملاحظتك، والقول لو كانت لقول محدد.
    # العناصر قائمة، كل عنصر فيه المفضلة، والباب، والقول أو لا شي.
    def bookmarks_file(self, entries, madhab_names: dict[int, str], pages: dict,
                       fmt: str = "docx") -> bytes:
        writer = EXPORT_FORMATS[fmt]()
        writer.title("مفضلتي")
        writer.line(f"{len(entries)} عنصراً، من كتاب {SOURCE}.", small=True)

        for bookmark, chapter, opinion in entries:
            writer.heading(chapter.title, level=2)
            writer.line(f"حُفظت في {bookmark.created_at:%Y-%m-%d}", small=True)
            if bookmark.note:
                writer.line(f"ملاحظتي: {bookmark.note}")
            if opinion is not None:
                self._opinion(writer, opinion, None, madhab_names, pages)
            else:
                page = pages[chapter.page_id]
                writer.line(f"الباب كامل، يبدأ في {page.citation()}", small=True)
                writer.line(page.shamela_url(), small=True, rtl=False)

        self._footer(writer)
        return writer.to_bytes()

    # ================================================== نسخ قول
    # نص عادي جاهز للصق في أي مكان: عنوان الباب، ثم القول، ثم مصدره ورابطه.
    # الرابط في سطر لحاله، عشان برامج المحادثة تحوّله لرابط يُضغط.
    @staticmethod
    def to_text(opinion, chapter_title: str, page) -> str:
        return (f"{chapter_title}\n\n"
                f"{opinion.text}\n\n"
                f"المصدر: {SHORT_SOURCE}، {page.citation()}\n"
                f"{page.shamela_url()}")

    # اسم ملف آمن من عنوان الباب: نشيل الرموز اللي ما يقبلها ويندوز في أسماء الملفات.
    @staticmethod
    def file_name(title: str, fmt: str = "docx") -> str:
        safe = re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
        return f"{safe or 'fiqh'}.{EXPORT_FORMATS[fmt].extension}"

    # ======================================================= الأجزاء
    # قول واحد: المذاهب المشتركة، والنص، والتوثيق، والأدلة.
    def _opinion(self, writer, opinion, madhab_id, madhab_names, pages):
        others = [madhab_names[i] for i in opinion.madhab_ids if i != madhab_id]
        if madhab_id is None:
            writer.line("، ".join(madhab_names[i] for i in opinion.madhab_ids), bold=True)
        elif others:
            writer.line("قول مشترك مع: " + "، ".join(others), small=True)

        writer.line(opinion.text)

        page = pages[opinion.page_id]
        place = "في الحاشية" if opinion.location == "footnote" else "في المتن"
        writer.line(f"{page.citation()}، {place}", small=True)

        if opinion.evidence:
            writer.line("الأدلة الواردة في القول:", small=True, bold=True)
            for evidence in opinion.evidence:
                label = "آية" if evidence.kind == "quran" else "حديث"
                writer.line(f"{label}: {evidence.text}", indent=True)

    def _source(self, writer, page):
        writer.line(f"المصدر: {SOURCE}، {page.citation()}", small=True)
        writer.line(page.shamela_url(), small=True, rtl=False)
        writer.line(DISCLAIMER, small=True)

    def _footer(self, writer):
        writer.line(f"صُدّر من المستكشف الفقهي المقارن في {datetime.now():%Y-%m-%d}.",
                    small=True)
