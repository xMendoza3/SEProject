"""
ملف الكتّاب: كل كاتب يعرف يكتب صيغة ملف وحدة، وورد أو PDF.

المصدّر يقرر وش ينكتب وبأي ترتيب: العنوان، ثم أقوال كل مذهب، ثم نص الباب.
والكاتب يقرر كيف ينكتب في صيغته: الخط، والحجم، والاتجاه، والألوان.
كل الكتّاب لهم نفس الدوال الأربع، فالمصدّر يكلمهم بنفس الطريقة وما يدري أي صيغة.

هذا نمط الباني: نفس خطوات البناء، ومنتج مختلف حسب الباني.
ولو بغينا صيغة ثالثة بكرة، نضيف كاتباً جديداً بس، والمصدّر ما يتغير.
"""

import importlib.util
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

# مكتبة ملفات وورد، وتثبيتها بهذا الأمر:
# pip install python-docx
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from src.models import to_arabic_digits
from src.ornament import star_outline

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ألوان الملفين: لون للعناوين، ولون باهت للتوثيق والملاحظات.
ACCENT = (0x0E, 0x6B, 0x5B)
MUTED = (0x5A, 0x6B, 0x66)
TEXT = (0x18, 0x22, 0x1F)


# ====================================================== الواجهة المشتركة
# الكلمة بين القوسين بعد اسم الكلاس معناها: هذا كلاس مجرد.
# يعني ما ننشئ منه كائناً مباشرة، هو بس يحدد الدوال اللي لازم كل كاتب يكتبها.
# والمزخرف فوق كل دالة يجبر الكاتب الفرعي إنه يكتبها، وإلا يطلع خطأ.
# في الجافا هذا يعادل الواجهة.
class DocumentWriter(ABC):
    # اسم الصيغة في الواجهة، وامتداد الملف، ونوعه اللي يفهمه المتصفح.
    label = ""
    extension = ""
    mime = ""

    # هل الصيغة جاهزة على هذا الجهاز؟ بعض الصيغ تحتاج مكتبة إضافية.
    @classmethod
    def available(cls) -> bool:
        return True

    @abstractmethod
    def title(self, text: str):
        """عنوان الملف، أول سطر فيه."""

    @abstractmethod
    def heading(self, text: str, level: int):
        """عنوان قسم: المستوى الأول لاسم المذهب، والثاني لعناوين المفضلة."""

    @abstractmethod
    def line(self, text: str, small=False, bold=False, indent=False, rtl=True):
        """فقرة عادية. الصغيرة للتوثيق، والمزاحة للأدلة، وغير العربية للروابط."""

    @abstractmethod
    def to_bytes(self) -> bytes:
        """الملف كامل، جاهز للتحميل."""


# ========================================================== كاتب الوورد
# نوع الملف اللي يفهمه المتصفح، عشان يعرف إنه ملف وورد.
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ARABIC_FONT = "Traditional Arabic"
BODY_SIZE = 15
SMALL_SIZE = 11

# ملف وورد من الداخل ملفات نصية، وترتيب الإعدادات فيها ثابت ولازم نحترمه.
# هذي الإعدادات اللي لازم تجي بعد إعداد اتجاه الفقرة، وبعد إعداد حجم الخط العربي.
_AFTER_BIDI = ("w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
               "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
               "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
               "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange")
_AFTER_SIZE_CS = ("w:highlight", "w:u", "w:effect", "w:bdr", "w:shd", "w:fitText",
                  "w:vertAlign", "w:rtl", "w:cs", "w:em", "w:lang", "w:eastAsianLayout",
                  "w:specVanish", "w:oMath")
_AFTER_BOLD_CS = ("w:i", "w:iCs", "w:caps", "w:smallCaps", "w:strike", "w:dstrike",
                  "w:outline", "w:shadow", "w:emboss", "w:imprint", "w:noProof",
                  "w:snapToGrid", "w:vanish", "w:webHidden", "w:color", "w:spacing",
                  "w:w", "w:kern", "w:position", "w:sz", "w:szCs") + _AFTER_SIZE_CS


class DocxWriter(DocumentWriter):
    label = "وورد"
    extension = "docx"
    mime = DOCX_MIME

    # ملف جديد، وكل أنماطه من اليمين لليسار، وبخط عربي.
    def __init__(self):
        self._document = Document()
        for name, size, bold in (("Normal", BODY_SIZE, False), ("Title", 26, True),
                                 ("Heading 1", 18, True), ("Heading 2", 15, True)):
            style = self._document.styles[name]
            self._set_direction(style.element.get_or_add_pPr(), rtl=True)
            style.font.name = ARABIC_FONT
            style.font.bold = bold
            # وورد يستخدم إعدادات منفصلة للخط العربي، فنضبطها هي بعد.
            style.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), ARABIC_FONT)
            style.font.size = Pt(size)
            self._size_cs(style.element.get_or_add_rPr(), size)
            if bold:
                self._bold_cs(style.element.get_or_add_rPr())
            if name != "Normal":
                style.font.color.rgb = RGBColor(*ACCENT)

    def title(self, text: str):
        paragraph = self._document.add_paragraph(style="Title")
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._rtl_run(paragraph.add_run(text))

    def heading(self, text: str, level: int):
        paragraph = self._document.add_heading(level=level)
        self._rtl_run(paragraph.add_run(text))

    # السطر الجديد داخل النص يصير سطراً جديداً في الملف.
    def line(self, text: str, small=False, bold=False, indent=False, rtl=True):
        paragraph = self._document.add_paragraph()
        if indent:
            paragraph.paragraph_format.right_indent = Pt(18)
        run = paragraph.add_run(text)
        if bold:
            run.bold = True
            self._bold_cs(run._r.get_or_add_rPr())
        if small:
            run.font.size = Pt(SMALL_SIZE)
            self._size_cs(run._r.get_or_add_rPr(), SMALL_SIZE)
            run.font.color.rgb = RGBColor(*MUTED)
        if rtl:
            self._rtl_run(run)
        else:
            # الرابط إنجليزي، فنخلي فقرته من اليسار لليمين.
            self._set_direction(paragraph._p.get_or_add_pPr(), rtl=False)

    # يحفظ الملف في الذاكرة ويرجعه كبايتات، بدون ما ينكتب على القرص.
    def to_bytes(self) -> bytes:
        buffer = BytesIO()
        self._document.save(buffer)
        return buffer.getvalue()

    # ---------------------------------------------- إعدادات الوورد الداخلية
    # يضبط اتجاه الفقرة في مكانه الصحيح: من اليمين لليسار، أو العكس.
    # الأنماط كلها من اليمين لليسار، فالفقرات ترث هذا الاتجاه تلقائياً.
    @staticmethod
    def _set_direction(paragraph_properties, rtl: bool):
        old = paragraph_properties.find(qn("w:bidi"))
        if old is not None:
            paragraph_properties.remove(old)
        element = OxmlElement("w:bidi")
        if not rtl:
            element.set(qn("w:val"), "0")
        paragraph_properties.insert_element_before(element, *_AFTER_BIDI)

    # يعلّم الكلام إنه عربي، عشان وورد يرتب علامات الترقيم صح.
    @staticmethod
    def _rtl_run(run):
        run._r.get_or_add_rPr().get_or_add_rtl()

    # حجم الخط العربي يُكتب بأنصاف النقاط، يعني ١٥ نقطة تنكتب ٣٠.
    @staticmethod
    def _size_cs(run_properties, size):
        old = run_properties.find(qn("w:szCs"))
        if old is not None:
            run_properties.remove(old)
        element = OxmlElement("w:szCs")
        element.set(qn("w:val"), str(size * 2))
        run_properties.insert_element_before(element, *_AFTER_SIZE_CS)

    @staticmethod
    def _bold_cs(run_properties):
        if run_properties.find(qn("w:bCs")) is None:
            run_properties.insert_element_before(OxmlElement("w:bCs"), *_AFTER_BOLD_CS)


# =========================================================== كاتب الـ PDF
# خط أميري: خط نسخ مفتوح المصدر برخصة تسمح بإرفاقه مع المشروع، ورخصته معه في نفس المجلد.
# وهو نفسه خط نص الكتاب في الواجهة، فالملف يشبه التطبيق.
FONT_DIR = PROJECT_ROOT / "static" / "fonts"
FONT_REGULAR = FONT_DIR / "Amiri-Regular.ttf"
FONT_BOLD = FONT_DIR / "Amiri-Bold.ttf"

# الأحجام بالنقاط، والمسافات بالمليمترات.
PDF_SIZES = {"title": 24, "h1": 17, "h2": 15, "body": 14, "small": 10.5}
MARGIN = 20
# ارتفاع السطر نسبة لحجم الخط. خط أميري يحتاج مسافة واسعة عشان الحركات ما تتلاصق.
LINE_HEIGHT = 0.68

# الكتاب يستخدم رموزاً تختصر عبارات، مثل رمز واحد معناه: عز وجل.
# خط أميري ما فيه هذي الرموز، فتطلع مربعات فاضية، فنكتب العبارة نفسها بدلها.
# الرموز جديدة في المعيار العالمي للحروف، وكل رمز اسمه الرسمي يقول عبارته.
HONORIFICS = {
    "﵀": "رحمه الله",
    "﵁": "رضي الله عنه",
    "﵂": "رضي الله عنها",
    "﵃": "رضي الله عنهم",
    "﵄": "رضي الله عنهما",
    "﵅": "رضي الله عنهن",
    "﵇": "عليه السلام",
    "﵈": "عليهم السلام",
    "﵉": "عليهما السلام",
    "﵊": "عليه الصلاة والسلام",
    "﵌": "صلى الله عليه وآله وسلم",
    "﵍": "عليها السلام",
    "﵎": "تبارك وتعالى",
    "﵏": "رحمهم الله",
    "﷾": "سبحانه وتعالى",
    "﷿": "عز وجل",
}
_HONORIFIC_TABLE = str.maketrans(HONORIFICS)


class PdfWriter(DocumentWriter):
    label = "PDF"
    extension = "pdf"
    mime = "application/pdf"

    # الـ PDF يحتاج مكتبتين: وحدة تبني الملف، ووحدة تشكّل الحروف العربية.
    # التشكيل يعني: نفس الحرف له شكل في أول الكلمة وشكل في وسطها وآخرها.
    @classmethod
    def available(cls) -> bool:
        return all(importlib.util.find_spec(name) for name in ("fpdf", "uharfbuzz"))

    def __init__(self):
        # الاستيراد هنا بدل أول الملف: لو المكتبة مو مثبتة، الوورد يشتغل عادي.
        from fpdf import FPDF

        pdf = FPDF(format="A4")
        pdf.set_margins(MARGIN, MARGIN, MARGIN)
        pdf.set_auto_page_break(auto=True, margin=MARGIN)
        pdf.add_font("Amiri", "", FONT_REGULAR)
        pdf.add_font("Amiri", "B", FONT_BOLD)
        pdf.set_lang("ar")
        pdf.set_creator("المستكشف الفقهي المقارن")
        # محرك التشكيل يرتب الحروف ويوصلها، والاتجاه من اليمين لليسار.
        pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab",
                             language="ara")
        # المكتبة تنادي هذي الدالة في آخر كل صفحة، فنحط فيها رقم الصفحة.
        pdf.footer = self._footer
        pdf.add_page()
        self._pdf = pdf

    # العنوان في الوسط، وتحته شريط زخرفي في وسطه نجمة ثمانية.
    def title(self, text: str):
        self._pdf.set_title(text)
        self._write(text, "title", bold=True, color=ACCENT, align="C")
        self._ornament()

    # عنوان المستوى الأول تحته خط بعرض الصفحة، مثل رأس العمود في التطبيق.
    # وجنبه نجمة صغيرة في الهامش الأيمن.
    def heading(self, text: str, level: int):
        pdf = self._pdf
        pdf.ln(3)
        # لو العنوان في آخر الصفحة، ننقله للصفحة الجاية عشان ما ينفصل عن كلامه.
        if pdf.get_y() > pdf.h - MARGIN - 30:
            pdf.add_page()
        top = pdf.get_y()
        style = "h1" if level == 1 else "h2"
        self._write(text, style, bold=True, color=ACCENT, gap=0.5)
        center = top + PDF_SIZES[style] * LINE_HEIGHT / 2
        self._star(pdf.w - MARGIN + 4, center, 1.6)
        if level == 1:
            pdf.set_draw_color(*ACCENT)
            pdf.set_line_width(0.4)
            pdf.line(MARGIN, pdf.get_y(), pdf.w - MARGIN, pdf.get_y())
            pdf.ln(2)

    def line(self, text: str, small=False, bold=False, indent=False, rtl=True):
        self._write(text, "small" if small else "body", bold=bold,
                    color=MUTED if small else TEXT, indent=8 if indent else 0, rtl=rtl)

    def to_bytes(self) -> bytes:
        return bytes(self._pdf.output())

    # -------------------------------------------------- أدوات الرسم
    # يكتب فقرة: العرض من الهامش الأيسر، ناقص الإزاحة من اليمين لو فيه إزاحة.
    # الروابط تنكتب من اليسار لليمين، لكن نصفّها يمين مثل باقي الملف.
    def _write(self, text, style, bold=False, color=TEXT, align="R", indent=0, rtl=True,
               gap=None):
        pdf = self._pdf
        size = PDF_SIZES[style]
        pdf.set_font("Amiri", "B" if bold else "", size)
        pdf.set_text_color(*color)
        if not rtl:
            pdf.set_text_shaping(use_shaping_engine=True, direction="ltr")
        pdf.set_x(MARGIN)
        pdf.multi_cell(pdf.epw - indent, size * LINE_HEIGHT, text.translate(_HONORIFIC_TABLE),
                       align=align, new_x="LMARGIN", new_y="NEXT")
        if not rtl:
            pdf.set_text_shaping(use_shaping_engine=True, direction="rtl", script="arab",
                                 language="ara")
        # بعد النص مسافة صغيرة عشان يلتصق بتوثيقه، وبعد التوثيق مسافة أكبر تفصله عن اللي بعده.
        pdf.ln(gap if gap is not None else (3 if style == "small" else 1))

    # نجمة ثمانية معبّأة باللون الأساسي.
    def _star(self, cx, cy, radius):
        self._pdf.set_fill_color(*ACCENT)
        self._pdf.polygon(star_outline(cx, cy, radius), style="F")

    # خطين رفيعين، وبينهم نجمة.
    def _ornament(self):
        pdf = self._pdf
        y = pdf.get_y() + 1
        middle = pdf.w / 2
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN + 25, y, middle - 6, y)
        pdf.line(middle + 6, y, pdf.w - MARGIN - 25, y)
        self._star(middle, y, 3)
        pdf.set_y(y + 6)

    # تذييل كل صفحة: خط رفيع، وتحته رقم الصفحة بأرقام عربية.
    def _footer(self):
        pdf = self._pdf
        pdf.set_y(-MARGIN + 4)
        pdf.set_draw_color(*MUTED)
        pdf.set_line_width(0.2)
        pdf.line(MARGIN, pdf.get_y(), pdf.w - MARGIN, pdf.get_y())
        pdf.set_font("Amiri", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 8, f"صفحة {to_arabic_digits(pdf.page_no())}", align="C")
