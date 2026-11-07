"""
اختبارات التصدير: الملف يفتح بالصيغتين، وفيه المطلوب بس، ومن اليمين لليسار.
"""

import math
from io import BytesIO

import pytest
from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader

from src.exporter import EXPORT_FORMATS, Exporter
from src.ornament import star_outline
from src.writers import FONT_BOLD, FONT_REGULAR, HONORIFICS, PdfWriter


# تفتح ملف الوورد وترجع كل نصه.
def docx_text(data: bytes) -> str:
    return "\n".join(p.text for p in Document(BytesIO(data)).paragraphs)


# المذاهب اللي ما اخترتها ما تدخل الملف.
def test_export_contains_only_selected_madhabs(controller):
    text = docx_text(controller.export(2, [1]))
    assert "الحنفية قالوا: التراويح عشرون ركعة." in text
    assert "المالكية" not in text
    assert "صلاة التراويح مشروعة عند الأئمة." in text


def test_export_is_right_to_left(controller):
    document = Document(BytesIO(controller.export(2, [1, 2, 3, 4])))
    paragraph_settings = document.styles["Normal"].element.pPr
    assert paragraph_settings.find(qn("w:bidi")) is not None


def test_bookmarks_export(controller):
    controller.add_bookmark(2, 1, "مهم")
    controller.add_bookmark(3)
    text = docx_text(controller.export_bookmarks())
    assert "ملاحظتي: مهم" in text
    assert "صلاة الوتر" in text


# اسم الملف ما فيه رموز يرفضها ويندوز، ولو ما بقى شي ناخذ اسم افتراضي.
def test_file_name_is_safe():
    assert Exporter.file_name('صلاة: "التراويح"?') == "صلاة التراويح.docx"
    assert Exporter.file_name("???") == "fiqh.docx"


# ================================================== ملف الـ PDF
# اختبارات الـ PDF تحتاج مكتبتي الـ PDF. لو مو مثبتة، تتخطى نفسها بدل ما تفشل.
pdf_ready = pytest.mark.skipif(not PdfWriter.available(), reason="pdf libraries not installed")


@pdf_ready
def test_pdf_export_is_a_pdf(controller):
    data = controller.export(2, [1, 2], "pdf")
    assert data.startswith(b"%PDF")
    assert len(PdfReader(BytesIO(data)).pages) >= 1


@pdf_ready
def test_bookmarks_pdf_export(controller):
    controller.add_bookmark(2, 1, "مهم")
    assert controller.export_bookmarks("pdf").startswith(b"%PDF")


# الرموز اللي ما في الخط تنكتب عبارتها، مثل رمز: عز وجل.
def test_honorific_symbols_become_words():
    assert "الله ﷿".translate(str.maketrans(HONORIFICS)) == "الله عز وجل"


# الخط ورخصته مرفقين مع المشروع، لأن الـ PDF ما يشتغل بدونه.
def test_pdf_font_and_license_exist():
    assert FONT_REGULAR.exists() and FONT_BOLD.exists()
    assert (FONT_REGULAR.parent / "OFL.txt").exists()


# كل صيغة لها امتداد في اسم الملف.
def test_file_name_follows_format():
    assert Exporter.file_name("صلاة الوتر", "pdf") == "صلاة الوتر.pdf"
    assert set(EXPORT_FORMATS) == {"docx", "pdf"}


# النجمة الثمانية: ستة عشر رأساً، والأطراف الثمانية كلها على نفس البعد من المركز.
def test_star_outline_has_eight_points():
    points = star_outline(0, 0, 10)
    assert len(points) == 16
    tips = points[0::2]
    assert all(abs(math.hypot(x, y) - 10) < 1e-9 for x, y in tips)
