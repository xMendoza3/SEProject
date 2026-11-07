"""
ملف الواجهة: طبقة العرض في نمط النموذج والعرض والمتحكم.

الواجهة تعرض بس، وتكلم متحكم المستكشف. ما تعرف شي عن قاعدة البيانات.

التشغيل من الطرفية، داخل مجلد المشروع:
    streamlit run app.py
"""

import html
import socket
import textwrap
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from src.controllers import ExplorerController, ImportController
from src.models import OTHER_MADHAB_ID, to_arabic_digits
from src.ornament import star_outline

# مجلد المشروع، نحسبه من مكان هذا الملف عشان يشتغل من أي مكان.
APP_DIR = Path(__file__).resolve().parent

# أيقونة التطبيق: تظهر في تبويب المتصفح، وفي الشاشة الرئيسية للجوال.
# مكانها مجلد الملفات الثابتة، والمكتبة تقدّمه على رابط ثابت يعرفه المتصفح.
ICON_PATH = APP_DIR / "static" / "icon.png"

# إعدادات الصفحة: العنوان والأيقونة في تبويب المتصفح، والعرض الكامل للشاشة.
# لازم يكون أول أمر من مكتبة الواجهة في الملف.
st.set_page_config(page_title="المستكشف الفقهي المقارن", page_icon=ICON_PATH,
                   layout="wide")


# ==================================================== هوية الألوان
# فكرة التصميم: كل مذهب له حبر، مثل المخطوطات اللي تكتب العناوين بلون مختلف.
# الحبر يظهر في رأس العمود، وخط بطاقة القول، والنجمة الثمانية جنب الاسم.
# لون للوضع الفاتح، ولون أفتح للوضع الداكن عشان يبقى واضح.
INKS = {
    "light": {1: "#3566c9", 2: "#b8740f", 3: "#14885f", 4: "#c23a55"},
    "dark": {1: "#6b93e6", 2: "#e0a03a", 3: "#3fbf8c", 4: "#ec6f88"},
}

# ألوان الخريطة غير ألوان المذاهب: اللون الخامس للمناطق اللي مذهبها غير الأربعة
# أو ما ذكرها المصدر، ولون البحر، ولون الحدود بين الدول.
MAP_COLORS = {
    "light": {"other": "#d9d3c7", "ocean": "#e9eef2", "border": "#ffffff"},
    "dark": {"other": "#4b505a", "ocean": "#1b2129", "border": "#0e1117"},
}

# ===================================================== الزخارف
# زخارف هندسية إسلامية بسيطة، كلها مبنية من النجمة الثمانية في ملف الزخرفة:
# نقش خفيف يغطي الخلفية، وشريط تحت العناوين، وفاصل في وسطه نجمة.
# لون الخطوط في النقش خافت جداً عشان ما يزاحم النص،
# ولون الشريط والفاصل برونزي مثل تذهيب المخطوطات، وهو للزينة بس، ما يعني أي مذهب.
ORNAMENTS = {
    "light": {"line": "#6b5432", "alpha": 0.08, "gold": "#8a6d3b"},
    "dark": {"line": "#e8dcc4", "alpha": 0.06, "gold": "#c9a96b"},
}


# رؤوس شكل بصيغة الصور المرسومة بالخطوط: أزواج أرقام بينها مسافات.
def svg_points(points) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


# المتصفح يقبل الصورة المرسومة بالخطوط مكتوبة داخل التنسيق نفسه،
# بشرط نرمّز الرموز الخاصة فيها، مثل علامة اللون.
def svg_url(svg: str) -> str:
    return 'url("data:image/svg+xml,' + quote(svg) + '")'


# مربع النقش اللي يتكرر في الخلفية: نجمة في الوسط، وأرباع نجوم في الزوايا
# تكتمل مع المربعات المجاورة، ومعيّنات صغيرة في منتصف الأضلاع،
# وخطوط تربط أطراف النجوم ببعض، فتطلع شبكة متصلة مثل نقوش المساجد.
def pattern_svg(color: str, alpha: float, size: int = 96, radius: int = 18) -> str:
    half = size / 2
    centers = [(half, half), (0, 0), (size, 0), (0, size), (size, size)]
    shapes = [f'<polygon points="{svg_points(star_outline(x, y, radius))}"/>' for x, y in centers]
    gem = radius * 0.32
    for x, y in [(half, 0), (0, half), (size, half), (half, size)]:
        diamond = [(x + gem, y), (x, y + gem), (x - gem, y), (x, y - gem)]
        shapes.append(f'<polygon points="{svg_points(diamond)}"/>')
    # الأطراف المائلة تمتد للنجوم في الزوايا، والمستقيمة للمعيّنات.
    tip = radius / 2 ** 0.5
    lines = [(half + radius, half, size - gem, half), (half - radius, half, gem, half),
             (half, half + radius, half, size - gem), (half, half - radius, half, gem),
             (half + tip, half + tip, size - tip, size - tip), (half - tip, half - tip, tip, tip),
             (half + tip, half - tip, size - tip, tip), (half - tip, half + tip, tip, size - tip)]
    shapes += [f'<line x1="{a:.2f}" y1="{b:.2f}" x2="{c:.2f}" y2="{d:.2f}"/>'
               for a, b, c, d in lines]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
            f'<g fill="none" stroke="{color}" stroke-opacity="{alpha}" stroke-width="1">'
            + "".join(shapes) + "</g></svg>")


# قطعة الشريط الزخرفي: خطّان رفيعان، وبينهم نجمة صغيرة يربطها خط بالنجمة اللي بعدها.
def band_svg(color: str, width: int = 40, height: int = 22) -> str:
    middle = height / 2
    star = svg_points(star_outline(width / 2, middle, 6))
    rules = (f'<line x1="0" y1="1.5" x2="{width}" y2="1.5"/>'
             f'<line x1="0" y1="{height - 1.5}" x2="{width}" y2="{height - 1.5}"/>'
             f'<line x1="0" y1="{middle}" x2="{width / 2 - 7}" y2="{middle}"/>'
             f'<line x1="{width / 2 + 7}" y1="{middle}" x2="{width}" y2="{middle}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<g stroke="{color}" stroke-opacity="0.55" stroke-width="1">{rules}</g>'
            f'<polygon points="{star}" fill="{color}" fill-opacity="0.55"/></svg>')


# أجزاء جاهزة نحطها في الصفحة: شريط تحت العنوان، وفاصل في وسطه نجمة.
BAND = '<div class="fx-band"></div>'
DIVIDER = '<div class="fx-divider"><span class="fx-star"></span></div>'

# سنة وفاة كل إمام بالهجري، للخط الزمني في شاشة الترحيب.
IMAM_DEATH_YEARS = {1: 150, 2: 179, 3: 204, 4: 241}


# ======================================================= التنسيق
# المكتبة ما تدعم الكتابة من اليمين لليسار، فنضيفها بتنسيق يدوي.
# خطين: أميري لنص الكتاب والعناوين، وبلكس العربي للواجهة.
# الأقواس المعقوفة المضاعفة لأن النص يمر على دالة تعبئة القيم.
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap');

:root {{
    --ink-1: {ink1}; --ink-2: {ink2}; --ink-3: {ink3}; --ink-4: {ink4};
    --book: "Amiri", "Traditional Arabic", serif;
    --ui: "IBM Plex Sans Arabic", Tahoma, sans-serif;
}}

/* اتجاه المحتوى دائماً من اليمين لليسار */
[data-testid="stMain"], [data-testid="stSidebarUserContent"],
[data-testid="stMarkdownContainer"] {{ direction: rtl; }}
/* وفي الشاشات العريضة بس، ننقل الشريط الجانبي لليمين.
   في الجوال الشريط ينزلق فوق الصفحة، وقلب اتجاهه يخربه. */
@media (min-width: 768px) {{
    [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{ direction: rtl; }}
}}
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"], .stButton button p, input, textarea {{
    font-family: var(--ui);
    text-align: right;
}}

/* النجمة الثمانية: مربع، وفوقه نسخة منه مائلة ٤٥ درجة */
.fx-star {{
    display: inline-block; flex: none; position: relative;
    width: .7em; height: .7em; background: var(--ink, currentColor);
}}
.fx-star::after {{
    content: ""; position: absolute; inset: 0;
    background: inherit; transform: rotate(45deg);
}}

/* شاشة الترحيب */
.fx-hero h1 {{
    font-family: var(--book); font-weight: 700; font-size: 3rem;
    line-height: 1.4; margin: 0 0 .4rem; padding: 0;
}}
.fx-hero p {{ font-size: 1.15rem; opacity: .8; max-width: 46rem; line-height: 1.9; }}

/* الخط الزمني للأئمة: خط أفقي وعليه نجمة لكل إمام، الأقدم على اليمين */
.fx-timeline {{
    list-style: none; margin: 2.2rem 0 2rem; padding: 0;
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem;
    position: relative;
}}
.fx-timeline::before {{
    content: ""; position: absolute; top: .55rem; right: 0; left: 0;
    height: 2px; background: currentColor; opacity: .15;
}}
.fx-timeline li {{ position: relative; display: grid; gap: .25rem; justify-items: start; }}
.fx-timeline .fx-star {{ font-size: 1.6rem; margin-bottom: .6rem; }}
.fx-timeline b {{
    font-family: var(--book); font-size: 1.6rem; color: var(--ink); line-height: 1.3;
}}
.fx-timeline span {{ opacity: .85; }}
.fx-timeline em {{ font-style: normal; opacity: .6; font-size: .9rem; }}

.fx-steps {{ margin: 0; padding-inline-start: 1.3rem; line-height: 2.1; opacity: .9; }}
.fx-steps, .fx-steps li {{ text-align: right; }}
.fx-note {{ font-size: .88rem; opacity: .6; line-height: 1.8; }}

/* رأس الباب */
.fx-crumbs {{ font-size: .9rem; opacity: .65; margin-bottom: .2rem; }}
.fx-title {{
    font-family: var(--book); font-weight: 700; font-size: 2.3rem;
    line-height: 1.5; margin: 0; padding: 0;
}}
.fx-meta {{ display: flex; flex-wrap: wrap; gap: .5rem 1rem; align-items: center; margin: .3rem 0 .8rem; }}
.fx-cite {{
    font-family: var(--book); font-size: 1.05rem;
    padding: .05rem .7rem; border-radius: 999px;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
}}
.fx-meta a {{ font-size: .95rem; }}

/* شريط المذاهب فوق المقارنة: كل مذهب وعدد أقواله */
.fx-legend {{ display: flex; flex-wrap: wrap; gap: .4rem 1.4rem; margin: .2rem 0 .6rem; }}
.fx-legend span {{ display: inline-flex; align-items: center; gap: .45rem; font-size: .95rem; }}
.fx-legend .fx-empty {{ opacity: .5; }}

/* رأس عمود المذهب */
.fx-col-head {{
    display: flex; align-items: center; gap: .7rem;
    padding-bottom: .55rem; margin-bottom: .3rem;
    border-bottom: 2px solid var(--ink);
}}
.fx-col-head .fx-star {{ font-size: 1.35rem; }}
.fx-col-head h3 {{
    font-family: var(--book); font-weight: 700; font-size: 1.7rem;
    color: var(--ink); margin: 0; padding: 0; line-height: 1.3;
}}
.fx-col-head small {{ display: block; opacity: .65; font-size: .85rem; }}

/* بطاقة القول: خط حبر على يمينها، وخلفية خفيفة من نفس الحبر */
{card_rules}
[class*="st-key-op-m"] {{ gap: .55rem; }}

/* أزرار اختيار المذاهب: كل زر بحبر مذهبه، والمعيّن الصغير علامته */
.st-key-madhab_pills [role="toolbar"] > button {{ display: inline-flex; align-items: center; gap: .45rem; }}
.st-key-madhab_pills [role="toolbar"] > button::before {{
    content: ""; flex: none; width: .5em; height: .5em;
    transform: rotate(45deg); background: var(--pill-ink);
}}
.st-key-madhab_pills [role="toolbar"] > button:nth-child(1) {{ --pill-ink: var(--ink-1); }}
.st-key-madhab_pills [role="toolbar"] > button:nth-child(2) {{ --pill-ink: var(--ink-2); }}
.st-key-madhab_pills [role="toolbar"] > button:nth-child(3) {{ --pill-ink: var(--ink-3); }}
.st-key-madhab_pills [role="toolbar"] > button:nth-child(4) {{ --pill-ink: var(--ink-4); }}
.st-key-madhab_pills [role="toolbar"] > button[data-selected="true"] {{
    border-color: var(--pill-ink);
    background: color-mix(in srgb, var(--pill-ink) 16%, transparent);
}}
.st-key-madhab_pills [role="toolbar"] > button[data-selected="false"] {{ opacity: .5; }}

.fx-shared {{ display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .8rem; font-size: .85rem; opacity: .85; }}
.fx-shared span {{ display: inline-flex; align-items: center; gap: .3rem; }}
.fx-book {{
    font-family: var(--book); font-size: 1.22rem; line-height: 2.15;
    text-align: justify; max-width: 75ch;
}}
.fx-foot {{ display: flex; flex-wrap: wrap; gap: .3rem .9rem; font-size: .85rem; opacity: .7; }}
.fx-evidence {{
    font-family: var(--book); font-size: 1.15rem; line-height: 2;
    padding-right: .8rem; border-right: 2px solid color-mix(in srgb, currentColor 30%, transparent);
}}
.fx-kind {{ font-size: .8rem; opacity: .6; }}

/* الجوال: عناوين أصغر، والأئمة في عمودين بدل أربعة */
@media (max-width: 640px) {{
    .fx-hero h1 {{ font-size: 2.1rem; }}
    .fx-title {{ font-size: 1.7rem; }}
    .fx-timeline {{ grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 1.6rem; }}
    .fx-timeline::before {{ display: none; }}
    /* في الجوال المكتبة تحط الأعمدة تحت بعض، فنرجعها عمودين جنب بعض */
    .st-key-timeline::before {{ display: none; }}
    .st-key-timeline [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; row-gap: 1.4rem; }}
    .st-key-timeline [data-testid="stColumn"] {{
        flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important;
        width: calc(50% - 1rem) !important;
    }}
    .fx-book {{ font-size: 1.15rem; }}
}}

/* الشريط الجانبي */
.fx-brand {{ display: flex; align-items: center; gap: .6rem; margin-bottom: .3rem; }}
.fx-brand .fx-star {{ font-size: 1.2rem; --ink: currentColor; }}
.fx-brand b {{ font-family: var(--book); font-size: 1.6rem; font-weight: 700; }}
.fx-section {{ font-size: .85rem; opacity: .6; margin: .6rem 0 .1rem; }}

/* قوائم الأبواب: صفوف بدون إطار، تبدأ من اليمين */
[class*="st-key-nav_"] button, [class*="st-key-navcur_"] button,
[class*="st-key-crumb_"] button, [class*="st-key-result_"] button {{
    justify-content: flex-start; text-align: right; width: 100%;
    padding: .3rem .6rem; border-radius: 6px; min-height: 0;
}}
[class*="st-key-nav_"] button:hover, [class*="st-key-result_"] button:hover {{
    background: color-mix(in srgb, currentColor 8%, transparent);
}}
[class*="st-key-navcur_"] button {{
    background: color-mix(in srgb, currentColor 12%, transparent);
    font-weight: 600;
}}
[class*="st-key-crumb_"] button p {{ font-size: .88rem; opacity: .75; }}

/* زر الرجوع: خفيف مثل مسار الباب، ويبان أكثر لما تمر عليه */
.st-key-back button {{ padding: .2rem .6rem; border-radius: 6px; min-height: 0; }}
.st-key-back button:hover {{ background: color-mix(in srgb, currentColor 8%, transparent); }}

/* نص ما ينقسم على سطرين، مثل اسم المؤلف */
.fx-nowrap {{ white-space: nowrap; }}

/* الخط الزمني في الترحيب: أعمدة، وفوقها خط أفقي يربط نجوم الأئمة */
.st-key-timeline {{ position: relative; margin: 1.6rem 0 .2rem; }}
.st-key-timeline::before {{
    content: ""; position: absolute; top: .8rem; right: 0; left: 0;
    height: 2px; background: currentColor; opacity: .15;
}}
.fx-tl {{ display: grid; gap: .25rem; justify-items: start; }}
.fx-tl .fx-star {{ font-size: 1.6rem; margin-bottom: .5rem; position: relative; }}
.fx-tl b {{ font-family: var(--book); font-size: 1.6rem; color: var(--ink); line-height: 1.3; }}
.fx-tl-year {{ font-style: normal; opacity: .6; font-size: .9rem; }}
/* اسم الإمام زر يشبه الرابط: بلون مذهبه، وتحته خط منقط يدل إنه ينضغط */
[class*="st-key-imam_"] button {{ padding: 0; min-height: 0; }}
[class*="st-key-imam_"] button p {{
    text-align: right; text-decoration: underline dotted; text-underline-offset: .4em;
}}
.st-key-imam_1 button p {{ color: var(--ink-1); }}
.st-key-imam_2 button p {{ color: var(--ink-2); }}
.st-key-imam_3 button p {{ color: var(--ink-3); }}
.st-key-imam_4 button p {{ color: var(--ink-4); }}
.fx-hint {{ font-size: .9rem; opacity: .7; margin: .6rem 0 1.4rem; }}

/* صفحة الإمام */
.fx-imam-head {{ display: flex; align-items: center; gap: .5rem; color: var(--ink); font-weight: 600; }}
.fx-profile-title {{
    font-family: var(--book); font-size: 1.35rem; font-weight: 700; margin: 1.4rem 0 .3rem;
}}
.fx-points {{ margin: 0; padding-inline-start: 1.2rem; line-height: 2; max-width: 52rem; }}
.fx-points li {{ text-align: right; }}
.fx-cite {{ font-size: .8rem; opacity: .7; white-space: nowrap; }}

/* بطاقة الخريطة في شاشة الترحيب */
.fx-card-title {{ font-family: var(--book); font-weight: 700; font-size: 1.6rem; line-height: 1.5; }}
.st-key-map_card p {{ opacity: .8; margin: .2rem 0 .4rem; }}

/* صفحة الخريطة: مربع اللون الخامس في الشرح، وجدول المصادر */
.fx-map-lead {{ font-size: 1.05rem; opacity: .8; line-height: 1.9; max-width: 52rem; }}
.fx-swatch {{ display: inline-block; width: .8em; height: .8em; border-radius: 2px; }}
.fx-table-wrap {{ overflow-x: auto; }}
.fx-table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
.fx-table th, .fx-table td {{
    text-align: right; vertical-align: top; padding: .45rem .5rem;
    border-bottom: 1px solid color-mix(in srgb, currentColor 12%, transparent);
}}
.fx-table th {{ opacity: .65; font-weight: 600; white-space: nowrap; }}
.fx-table .fx-q {{ font-family: var(--book); font-size: 1.05rem; min-width: 14rem; }}
.fx-table .fx-n {{ opacity: .7; min-width: 12rem; }}

/* زر النسخ: مكتوب يدوياً، فنعطيه نفس شكل زر الإضافة اللي جنبه */
.fx-copy {{
    font-family: var(--ui); font-size: .875rem; color: inherit;
    background: none; border: none; padding: 0; cursor: pointer;
}}
.fx-copy:hover {{ text-decoration: underline; text-underline-offset: .3em; }}

/* مكان السكربت: ما نبيه ياخذ مساحة في الصفحة */
.st-key-fx_script {{ display: none; }}

/* الزخارف: نقش الخلفية، والشريط، والفاصل */
.stApp {{ background-image: {pattern}; }}
[data-testid="stSidebar"] {{ background-image: {pattern_small}; }}
.fx-band {{
    height: 22px; max-width: 46rem; margin: .6rem 0 1rem;
    background-image: {band}; background-repeat: repeat-x; background-position: center;
    /* الشريط يخفت عند طرفيه بدل ما ينقطع فجأة */
    -webkit-mask-image: linear-gradient(to left, transparent, #000 10%, #000 90%, transparent);
    mask-image: linear-gradient(to left, transparent, #000 10%, #000 90%, transparent);
}}
.fx-brand + .fx-band {{ margin: .1rem 0 .8rem; }}
.fx-divider {{
    display: flex; align-items: center; gap: .8rem; margin: 1.6rem 0;
    color: {gold}; max-width: 52rem;
}}
.fx-divider::before, .fx-divider::after {{
    content: ""; flex: 1; height: 1px; opacity: .6;
    background: linear-gradient(to left, transparent, currentColor);
}}
.fx-divider::after {{ background: linear-gradient(to right, transparent, currentColor); }}
.fx-divider .fx-star {{ font-size: 1rem; }}
/* بطاقة الخريطة: نجمة برونزية في زاويتها */
.st-key-map_card {{ position: relative; }}
.st-key-map_card::before {{
    content: ""; position: absolute; top: 1rem; left: 1rem; width: 1.6rem; height: 1.6rem;
    background-image: {star}; background-size: contain; opacity: .8;
}}
/* عناوين أقسام النبذة: نجمة صغيرة قبل كل عنوان */
.fx-profile-title {{ display: flex; align-items: center; gap: .5rem; }}
.fx-profile-title::before {{
    content: ""; width: .7rem; height: .7rem; flex: none;
    background-image: {star}; background-size: contain;
}}
</style>
"""

# =================================================== سكربت الصفحة
# أسطر بلغة المتصفح، تشتغل مرة وحدة لما تنفتح الصفحة، وتسوي شيئين.
#
# الأول زر النسخ: المكتبة ما فيها زر ينسخ للحافظة،
# فنسمع أي ضغطة على زر نسخ، وننسخ النص المحفوظ داخله.
# الطريقة الحديثة للنسخ تحتاج رابط آمن، وهذا ما يتوفر لما أهلك يفتحون التطبيق
# من جوالاتهم في نفس الشبكة، فنرجع للطريقة القديمة في هالحالة.
#
# الثاني أيقونة الجوال: نضيف للصفحة سطر يحدد أيقونة الشاشة الرئيسية.
# وبعد النشر، التطبيق يكون داخل إطار في صفحة الموقع، فنضيفها للصفحة الكبيرة بعد.
SCRIPT = """
<script>
(function () {
  if (window.fxReady) return;
  window.fxReady = true;

  function oldCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);
    var copied = false;
    try { copied = document.execCommand("copy"); } catch (error) {}
    area.remove();
    return copied;
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(
        function () { return true; },
        function () { return oldCopy(text); });
    }
    return Promise.resolve(oldCopy(text));
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".fx-copy");
    if (!button) return;
    var label = button.dataset.label || button.textContent;
    button.dataset.label = label;
    copy(button.dataset.copy).then(function (copied) {
      button.textContent = copied ? "تم النسخ ✓" : "ما قدرنا ننسخ";
      setTimeout(function () { button.textContent = label; }, 1800);
    });
  });

  var icon = location.origin + "/app/static/icon.png";
  var pages = [document];
  try { if (window.top !== window) pages.push(window.top.document); } catch (error) {}
  pages.forEach(function (page) {
    ["apple-touch-icon", "icon"].forEach(function (rel) {
      if (page.querySelector('link[data-fx="' + rel + '"]')) return;
      var link = page.createElement("link");
      link.rel = rel;
      link.href = icon;
      link.setAttribute("data-fx", rel);
      page.head.appendChild(link);
    });
  });
})();
</script>
"""

# قاعدة بطاقة القول لكل مذهب. كل بطاقة مفتاحها يبدأ برقم مذهبها،
# والمكتبة تحوّل المفتاح لاسم فئة، فنقدر نلوّن كل بطاقة بحبر مذهبها.
CARD_RULE = """
[class*="st-key-op-m{madhab_id}-"] {{
    border-right: 3px solid var(--ink-{madhab_id});
    background: color-mix(in srgb, var(--ink-{madhab_id}) 6%, transparent);
    border-radius: 2px 10px 10px 2px;
    padding: .9rem 1rem .6rem;
}}
"""

# أقصى طول نعرضه من القول، والباقي يروح لقسم يتفتح بالضغط.
PREVIEW_LENGTH = 700

# أقصى عدد نتائج نعرضه من كل نوع في البحث.
MAX_SHOWN_RESULTS = 50

# باب نقترحه في شاشة الترحيب: صلاة التراويح.
SAMPLE_CHAPTER_ID = 267

# أقصى عدد خطوات يحفظها سجل التنقل لزر الرجوع.
HISTORY_LIMIT = 50

# المكان المفتوح في الصفحة: رقم باب، أو لا شي لشاشة البداية، أو هذي الكلمة للخريطة،
# أو كلمة الإمام ومعها رقم مذهبه لصفحة نبذته.
MAP_PAGE = "map"
IMAM_PAGE_PREFIX = "imam-"

# أسماء الأئمة المختصرة، لأزرار التنقل بين صفحاتهم.
IMAM_SHORT_NAMES = {1: "أبو حنيفة", 2: "مالك", 3: "الشافعي", 4: "أحمد"}


def imam_place(madhab_id: int) -> str:
    return f"{IMAM_PAGE_PREFIX}{madhab_id}"


# رقم المذهب لو المكان صفحة إمام، وإلا لا شي.
def imam_from_place(place) -> int | None:
    if isinstance(place, str) and place.startswith(IMAM_PAGE_PREFIX):
        return int(place.removeprefix(IMAM_PAGE_PREFIX))
    return None

MODES = ["تصفح", "بحث", "مفضلة", "حول"]

DISCLAIMER = (
    "تقسيم الأقوال آلي، والمرجع هو نص الكتاب. "
    "التطبيق للدراسة والمقارنة، وليس بديلاً عن سؤال أهل العلم."
)


# ================================================= متحكم كل مستخدم
# المكتبة تعيد تشغيل الملف كامل مع كل ضغطة زر.
# هذا المزخرف يخلي المتحكم ينشأ مرة وحدة لكل مستخدم، ويُستخدم نفسه في كل مرة.
#
# ليش لكل مستخدم؟ بعد النشر ممكن يفتح التطبيق أكثر من شخص في نفس اللحظة،
# ولو تشاركوا اتصال واحد بقاعدة البيانات ممكن يتزاحمون عليه.
# فكل مستخدم ياخذ اتصاله، ولما يقفل الصفحة نقفل اتصاله معها.
#
# المشكلة: لو عدّلنا ملفات المصدر والتطبيق شغال، يبقى المتحكم القديم في الذاكرة.
# الحل: نعطي الدالة رقم نسخة الكود، وهو آخر وقت تعدّل فيه أي ملف في مجلد المصدر.
# المكتبة تحفظ نسخة لكل قيمة مختلفة، فأي تعديل ينتج متحكم جديد تلقائياً.
SOURCE_DIR = APP_DIR / "src"


def code_version() -> float:
    return max(path.stat().st_mtime for path in SOURCE_DIR.glob("*.py"))


@st.cache_resource(scope="session", on_release=lambda controller: controller.close())
def get_controller(version: float) -> ExplorerController:
    return ExplorerController()


def controller() -> ExplorerController:
    return get_controller(code_version())


# ============================================== أوامر الأزرار
# هذي الدوال تشتغل لما يُضغط زر، قبل ما يُعاد رسم الصفحة.
# حالة الجلسة قاموس يبقى بين مرات التشغيل، نحفظ فيه الباب المفتوح.
#
# وفيها بعد سجل التنقل: قائمة بالأماكن اللي مرّ عليها المستخدم، الأحدث آخرها.
# كل ما فتح مكان جديد نحفظ مكانه الحالي في آخر القائمة،
# وزر الرجوع ياخذ آخر عنصر ويرجعه له. نفس فكرة زر الرجوع في المتصفح.
# المكان رقم الباب، أو لا شي لشاشة البداية، أو كلمة الخريطة،
# ومعه القول المميز لو جا من البحث أو المفضلة.

def go_to(place, highlight=None):
    current = st.session_state.get("place")
    # فتح نفس المكان ما يُحسب خطوة، عشان الرجوع ما يوديك لنفس المكان.
    if place != current:
        history = st.session_state.setdefault("history", [])
        history.append((current, st.session_state.get("highlight")))
        # لو زاد السجل عن الحد، نشيل الأقدم ونخلي آخر خمسين.
        del history[:-HISTORY_LIMIT]
    st.session_state.place = place
    st.session_state.highlight = highlight


# الرجوع: ناخذ آخر مكان من السجل ونفتحه، بدون ما نضيف خطوة جديدة.
def go_back():
    history = st.session_state.get("history", [])
    if history:
        st.session_state.place, st.session_state.highlight = history.pop()


# لما يختار المستخدم إماماً ثانياً من أزرار صفحة النبذة، نفتح صفحته.
def switch_imam(key: str):
    madhab_id = st.session_state.get(key)
    if madhab_id:
        go_to(imam_place(madhab_id))


# رقم الباب المفتوح، أو لا شي لو المفتوح شاشة البداية أو الخريطة أو نبذة إمام.
def open_chapter_id() -> int | None:
    place = st.session_state.get("place")
    return place if isinstance(place, int) else None


def save_bookmark(chapter_id, opinion_id=None, note_key=None):
    note = st.session_state.get(note_key, "") if note_key else ""
    controller().add_bookmark(chapter_id, opinion_id, note)
    if note_key:
        st.session_state[note_key] = ""
    st.toast("أُضيف إلى المفضلة")


def remove_bookmark(bookmark_id):
    controller().remove_bookmark(bookmark_id)
    st.toast("انحذف من المفضلة")


# ======================================================= أدوات صغيرة
# كل نص يجي من الكتاب أو من المستخدم نهرّبه قبل ما نحطه في الصفحة،
# عشان أي رمز خاص فيه ينعرض كنص، وما يتنفذ كجزء من الصفحة.
def esc(text) -> str:
    return html.escape(str(text))


def star(madhab_id=None) -> str:
    ink = f' style="--ink: var(--ink-{madhab_id})"' if madhab_id else ""
    return f'<span class="fx-star"{ink}></span>'


def book_text(text: str, css_class: str = "fx-book") -> str:
    body = esc(text.strip()).replace("\n", "<br>")
    return f'<div class="{css_class}">{body}</div>'


def html_block(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


# زر النسخ: النص كامل محفوظ داخل الزر نفسه، والسكربت فوق يتولى النسخ لما ينضغط.
# النسخ يصير في المتصفح مباشرة، فما يعيد رسم الصفحة ولا يكلم المتحكم.
def copy_button(text: str, label: str = "نسخ القول"):
    st.html(f'<button type="button" class="fx-copy" data-copy="{esc(text)}">{label}</button>',
            width="content")


# عدد الأقوال بصيغة عربية صحيحة: قول واحد، قولان، ثلاثة أقوال، أحد عشر قولاً.
def count_label(count: int) -> str:
    if count == 1:
        return "قول واحد"
    if count == 2:
        return "قولان"
    if 3 <= count <= 10:
        return f"{to_arabic_digits(count)} أقوال"
    return f"{to_arabic_digits(count)} قولاً"


# ===================================================== رسم الخريطة
# الخريطة الأساسية، يعني البحر واليابسة، يحمّلها المتصفح من موقع مكتبة الرسوم.
# فقبل ما نرسم، نفحص هل الجهاز يوصل للموقع. وهذا الفحص الوحيد للشبكة في الواجهة.
# نحفظ النتيجة نص دقيقة، عشان ما نفحص مع كل ضغطة زر.
@st.cache_data(ttl=30, show_spinner=False)
def map_service_reachable() -> bool:
    try:
        with socket.create_connection(("cdn.plot.ly", 443), timeout=2):
            return True
    except OSError:
        return False


# نقسم النص الطويل لأسطر قصيرة، لأن صندوق التلميح في الخريطة ما يقسم لحاله.
def short_lines(text: str, width: int = 42) -> list[str]:
    return textwrap.wrap(text, width)


# نرسم بمكتبة الرسوم، بإسقاط الكرة الأرضية: تدور بالسحب وتكبر بعجلة الفأرة.
# كل مذهب طبقة بلونه. والدول المقسومة طبقة ثانية من حدود المحافظات، فوق الدول.
# والدول اللي ما لها بيانات تاخذ لون اليابسة، وهو نفسه اللون الخامس.
# الاستيراد داخل الدالة: لو المكتبة مو مثبتة، باقي التطبيق يشتغل عادي.
def map_figure(madhab_map, colors: dict, palette: dict, hover):
    import plotly.graph_objects as go

    figure = go.Figure()
    for madhab_id, color in colors.items():
        regions = [r for r in madhab_map.regions if r.madhab_id == madhab_id]
        whole = [r for r in regions if not r.is_partial()]
        parts = [(unit, r) for r in regions for unit in r.units]
        # نفس الشكل للطبقتين: لون واحد ثابت، وبدون مقياس ألوان جنب الخريطة.
        style = dict(colorscale=[[0, color], [1, color]], showscale=False,
                     marker_line_color=palette["border"], marker_line_width=0.6,
                     hovertemplate="%{text}<extra></extra>")
        if whole:
            figure.add_trace(go.Choropleth(
                locations=[r.country for r in whole], locationmode="ISO-3",
                z=[1] * len(whole), text=[hover(r) for r in whole], **style))
        if parts and madhab_map.shapes:
            figure.add_trace(go.Choropleth(
                geojson=madhab_map.shapes, locations=[unit for unit, _ in parts],
                z=[1] * len(parts), text=[hover(r) for _, r in parts], **style))

    # نبدأ والجزيرة العربية في وسط الكرة.
    figure.update_geos(
        projection_type="orthographic", projection_rotation={"lon": 40, "lat": 20},
        showland=True, landcolor=palette["other"],
        showocean=True, oceancolor=palette["ocean"],
        showcountries=True, countrycolor=palette["border"], countrywidth=0.5,
        showcoastlines=False, showlakes=False, showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )
    # آخر خيار يخلي الكرة على نفس الزاوية والتكبير لو انرسمت الصفحة من جديد.
    figure.update_layout(
        height=620, margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)", dragmode="pan",
        hoverlabel={"align": "right", "font": {"family": "IBM Plex Sans Arabic, sans-serif",
                                               "size": 14}},
        uirevision="madhab-map",
    )
    return figure


# ======================================================= الواجهة
class AppView:

    def __init__(self, controller: ExplorerController):
        self._controller = controller
        self._madhabs = {m.madhab_id: m for m in controller.get_madhabs()}

    # نقطة البداية: ترسم الشريط الجانبي، ثم الباب المفتوح أو شاشة الترحيب.
    def render(self):
        self._apply_style()
        # أول تشغيل على جهاز جديد: نبني قاعدة البيانات تلقائياً من ملفات الكتاب.
        if not self._controller.is_ready():
            self._build_database()
            return
        selected = self.render_sidebar()
        self.render_back_button("back")
        place = st.session_state.get("place")
        if place == MAP_PAGE:
            self.render_map()
        elif imam_from_place(place):
            self.render_imam(imam_from_place(place))
        elif place is None:
            self.render_welcome()
        else:
            self.render_chapter(place, selected)

    # تعبّي التنسيق بألوان الوضع الحالي، فاتح أو داكن.
    def _apply_style(self):
        theme = "dark" if st.context.theme.type == "dark" else "light"
        inks = INKS[theme]
        ornament = ORNAMENTS[theme]
        card_rules = "".join(CARD_RULE.format(madhab_id=i) for i in inks)
        star = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
                f'<polygon points="{svg_points(star_outline(10, 10, 9.5))}" '
                f'fill="{ornament["gold"]}"/></svg>')
        st.html(STYLE.format(
            ink1=inks[1], ink2=inks[2], ink3=inks[3], ink4=inks[4], card_rules=card_rules,
            pattern=svg_url(pattern_svg(ornament["line"], ornament["alpha"])),
            # نقش أصغر في الشريط الجانبي، لأنه أضيق.
            pattern_small=svg_url(pattern_svg(ornament["line"], ornament["alpha"] * 0.8, 72, 13)),
            band=svg_url(band_svg(ornament["gold"])), gold=ornament["gold"], star=svg_url(star),
        ))
        # الخيار الأخير يسمح للسكربت يشتغل. آمن هنا لأنه كودنا، ما فيه شي من المستخدم.
        with st.container(key="fx_script"):
            st.html(SCRIPT, unsafe_allow_javascript=True)

    def _build_database(self):
        try:
            with st.spinner("أول تشغيل: نجهّز قاعدة البيانات من ملفات الكتاب..."):
                ImportController().run(report=lambda message: None)
        except Exception as error:
            st.error("ما قدرنا نجهّز قاعدة البيانات. تأكد إن مجلد البيانات موجود مع المشروع، "
                     "أو إن الجهاز متصل بالإنترنت أول مرة. تفاصيل الخطأ:")
            st.code(str(error))
            return
        # نعيد رسم الصفحة، والمرة الجاية بتلقى قاعدة البيانات جاهزة.
        st.rerun()

    # ================================================== زر الرجوع
    # زران بنفس العمل: واحد فوق الصفحة، وواحد فوق قائمة الأبواب في الشريط الجانبي،
    # لأن المستخدم يتنقل من هناك. الزر ظاهر دائماً عشان يعرف مكانه،
    # ويكون معطّل لو ما فيه مكان سابق. ولو وقفت عليه، يقول لك وين بيرجعك.
    def render_back_button(self, key: str, width="content"):
        history = st.session_state.get("history") or []
        hint = (f"يرجعك إلى: {self._place_title(history[-1][0])}" if history
                else "ما فيه مكان سابق للحين")
        st.button("رجوع", key=key, icon=":material/arrow_forward:", on_click=go_back,
                  disabled=not history, help=hint, width=width)

    # اسم المكان بالعربي، للتلميح على زر الرجوع.
    def _place_title(self, place) -> str:
        if place is None:
            return "شاشة البداية"
        if place == MAP_PAGE:
            return "خريطة المذاهب"
        if imam_from_place(place):
            return f"نبذة الإمام {IMAM_SHORT_NAMES[imam_from_place(place)]}"
        path = self._controller.get_path(place)
        return path[-1].title if path else "الباب السابق"

    # =============================================== الشريط الجانبي
    # يرجع أرقام المذاهب المختارة، مرتبة.
    def render_sidebar(self) -> list[int]:
        with st.sidebar:
            html_block(f'<div class="fx-brand">{star()}<b>المستكشف الفقهي</b></div>{BAND}')
            # مدخل الخريطة فوق كل شي، لأنها صفحة كبيرة ومستقلة عن الكتاب.
            st.button("خريطة انتشار المذاهب", key="open_map", icon=":material/public:",
                      on_click=go_to, args=(MAP_PAGE,), width="stretch")
            selected = st.pills(
                "المذاهب المعروضة",
                options=list(self._madhabs),
                selection_mode="multi",
                default=list(self._madhabs),
                format_func=lambda madhab_id: self._madhabs[madhab_id].name,
                key="madhab_pills",
            )
            selected = sorted(selected or [])
            mode = st.segmented_control(
                "القسم", MODES, default=MODES[0], required=True,
                label_visibility="collapsed", key="mode", width="stretch",
            )
            if mode == "تصفح":
                self.render_browser()
            elif mode == "بحث":
                self.render_search(selected)
            elif mode == "مفضلة":
                self.render_bookmarks()
            else:
                self.render_about()
        return selected

    # ======================================================= التصفح
    # مثل مستكشف الملفات: فوق مسار الباب الحالي، وتحته الأبواب اللي داخله.
    # ولو الباب ما تحته شي، نعرض الأبواب اللي جنبه عشان تتنقل بينها.
    def render_browser(self):
        self.render_back_button("back_sidebar", width="stretch")
        current = open_chapter_id()
        path = self._controller.get_path(current) if current else []

        if path:
            st.button("الكتاب كامل", key="crumb_root", on_click=go_to, args=(None,),
                      type="tertiary")
            for chapter in path[:-1]:
                st.button(f"↑ {chapter.title}", key=f"crumb_{chapter.chapter_id}",
                          on_click=go_to, args=(chapter.chapter_id,), type="tertiary")

        children = self._controller.browse(current)
        if current is not None and not children:
            children = self._controller.browse(path[-1].parent_id)
            heading = "الأبواب المجاورة"
        elif current is None:
            heading = "أقسام الكتاب"
        else:
            heading = "داخل هذا الباب"
        html_block(f'<div class="fx-section">{heading}</div>')

        for chapter in children:
            is_current = chapter.chapter_id == current
            st.button(
                chapter.title,
                key=f"{'navcur' if is_current else 'nav'}_{chapter.chapter_id}",
                on_click=go_to,
                args=(chapter.chapter_id,),
                type="tertiary",
                width="stretch",
            )

    # ======================================================== البحث
    def render_search(self, selected: list[int]):
        query = st.text_input("ابحث في العناوين والأقوال", key="query",
                              placeholder="مثال: صلاة التراويح")
        if not query.strip():
            html_block('<div class="fx-note">البحث يتجاهل الحركات، '
                       'ويعامل الهمزات والتاء المربوطة كحرف واحد.</div>')
            return

        results = self._controller.receive_query(query, selected)
        # حالة لا توجد نتائج: التوسيع اللي في مخطط حالات الاستخدام.
        if results.is_empty():
            st.info("لا توجد نتائج. جرّب كلمة أقل، أو صيغة ثانية للكلمة، "
                    "أو تأكد إن المذاهب المختارة فوق تشمل اللي تدور عليه.")
            return

        if results.chapters:
            html_block(f'<div class="fx-section">أبواب ({to_arabic_digits(len(results.chapters))})</div>')
            for chapter in results.chapters[:MAX_SHOWN_RESULTS]:
                st.button(chapter.title, key=f"result_chapter_{chapter.chapter_id}",
                          on_click=go_to, args=(chapter.chapter_id,),
                          type="tertiary", width="stretch")

        if results.opinions:
            html_block(f'<div class="fx-section">أقوال ({to_arabic_digits(len(results.opinions))})</div>')
            for opinion in results.opinions[:MAX_SHOWN_RESULTS]:
                who = "، ".join(self._madhabs[i].name for i in opinion.madhab_ids)
                title = results.titles.get(opinion.chapter_id, "")
                st.button(f"{who}: {title}", key=f"result_opinion_{opinion.opinion_id}",
                          on_click=go_to, args=(opinion.chapter_id, opinion.opinion_id),
                          type="tertiary", width="stretch")

        if max(len(results.chapters), len(results.opinions)) > MAX_SHOWN_RESULTS:
            html_block(f'<div class="fx-note">نعرض أول {to_arabic_digits(MAX_SHOWN_RESULTS)} '
                       'نتيجة من كل نوع. حدد البحث أكثر.</div>')

    # ====================================================== المفضلة
    def render_bookmarks(self):
        items = self._controller.get_bookmarks()
        if not items:
            st.info("ما عندك مفضلة للحين. افتح أي باب، وأضفه هو أو أي قول منه.")
            return
        self._export_menu("تصدير المفضلة", "export_bookmarks",
                          make_file=self._controller.export_bookmarks,
                          file_name=lambda fmt: f"مفضلتي.{fmt}", width="stretch")
        for bookmark, title in items:
            with st.container(border=True):
                kind = "قول محدد" if bookmark.opinion_id else "الباب كامل"
                note = f"<div>{esc(bookmark.note)}</div>" if bookmark.note else ""
                html_block(f"<b>{esc(title)}</b>"
                           f'<div class="fx-note">{kind}، حُفظ في {bookmark.created_at:%Y-%m-%d}</div>'
                           f"{note}")
                left, right = st.columns(2)
                left.button("افتح", key=f"bookmark_open_{bookmark.bookmark_id}",
                            on_click=go_to, args=(bookmark.chapter_id, bookmark.opinion_id),
                            width="stretch")
                right.button("احذف", key=f"bookmark_remove_{bookmark.bookmark_id}",
                             on_click=remove_bookmark, args=(bookmark.bookmark_id,),
                             width="stretch")

    # ================================================== قائمة التصدير
    # زر واحد اسمه تصدير، يفتح قائمة صغيرة فيها زر لكل صيغة: وورد و PDF.
    # الصيغ تجي من المتحكم، فلو أضفنا صيغة جديدة تظهر هنا لحالها.
    # نعطي كل زر دالة بدل الملف نفسه، فما ينبني الملف إلا لما ينضغط زره.
    # والخيار الأخير في الزر يمنع إعادة رسم الصفحة بعد التحميل.
    def _export_menu(self, label, key, make_file, file_name, disabled=False, width="content"):
        icons = {"docx": ":material/description:", "pdf": ":material/picture_as_pdf:"}
        with st.popover(label, icon=":material/download:", disabled=disabled, width=width):
            html_block('<div class="fx-note">اختر صيغة الملف:</div>')
            for fmt, writer in self._controller.export_formats().items():
                ready = writer.available()
                st.download_button(
                    writer.label,
                    # القيمة الافتراضية تثبّت الصيغة لكل زر، وإلا كل الأزرار تاخذ آخر صيغة.
                    data=lambda fmt=fmt: make_file(fmt),
                    file_name=file_name(fmt),
                    mime=writer.mime,
                    key=f"{key}_{fmt}",
                    icon=icons.get(fmt),
                    on_click="ignore",
                    disabled=not ready,
                    help=None if ready else "مكتبة هذي الصيغة غير مثبتة على هذا الجهاز",
                    width="stretch",
                )

    # ================================================== حول التطبيق
    def render_about(self):
        stats = self._controller.get_stats()
        n = to_arabic_digits
        html_block(
            # كل جزء من المصدر في سطر، واسم المؤلف ما ينقسم أبداً.
            '<div class="fx-section">المصدر</div>'
            "<div>كتاب الفقه على المذاهب الأربعة،"
            '<br><span class="fx-nowrap">لعبد الرحمن الجزيري،</span>'
            "<br>دار الكتب العلمية، الطبعة الثانية.</div>"
            '<div class="fx-note">النسخة الرقمية من موقع تراث، وهي مطابقة لنسخة المكتبة الشاملة.</div>'
            '<div class="fx-section">المحتوى</div>'
            f"<div>{n(stats['chapters'])} عنواناً، و{n(stats['opinions'])} قولاً، "
            f"و{n(stats['evidence'])} دليلاً، من {n(stats['pages'])} صفحة.</div>"
            '<div class="fx-section">تنبيه</div>'
            f'<div class="fx-note">{DISCLAIMER}</div>'
            '<div class="fx-section">الأئمة الأربعة</div>'
        )
        for madhab_id, name in IMAM_SHORT_NAMES.items():
            st.button(f"نبذة عن الإمام {name}", key=f"about_imam_{madhab_id}", type="tertiary",
                      on_click=go_to, args=(imam_place(madhab_id),))

    # ===================================================== الترحيب
    # الخط الزمني للأئمة الأربعة هو أول شي يشوفه المستخدم:
    # المذاهب بألوانها، مرتبة حسب وفاة أئمتها.
    def render_welcome(self):
        html_block(
            '<section class="fx-hero">'
            f"<h1>المستكشف الفقهي المقارن</h1>{BAND}"
            "<p>اقرأ أقوال المذاهب الأربعة في المسألة الواحدة جنباً إلى جنب، "
            "كما نقلها الجزيري في كتابه الفقه على المذاهب الأربعة، "
            "ومع كل قول مكانه في الكتاب.</p>"
            "</section>"
        )
        # الخط الزمني أعمدة من المكتبة، عشان يصير اسم كل إمام زراً يفتح نبذته.
        with st.container(key="timeline"):
            for column, madhab in zip(st.columns(4), self._madhabs.values()):
                with column:
                    html_block(f'<div class="fx-tl" style="--ink: var(--ink-{madhab.madhab_id})">'
                               f"{star(madhab.madhab_id)}<b>{esc(madhab.name)}</b></div>")
                    st.button(madhab.imam, key=f"imam_{madhab.madhab_id}", type="tertiary",
                              on_click=go_to, args=(imam_place(madhab.madhab_id),),
                              help="نبذة عن سيرته")
                    html_block('<em class="fx-tl-year">ت '
                               f"{to_arabic_digits(IMAM_DEATH_YEARS[madhab.madhab_id])}هـ</em>")
        html_block('<p class="fx-hint">اضغط على اسم أي إمام لعرض نبذة عن سيرته وطريقته في الاستنباط.</p>')
        st.button("ابدأ بمثال: صلاة التراويح", on_click=go_to, args=(SAMPLE_CHAPTER_ID,),
                  type="primary")
        # بطاقة كبيرة للخريطة، عشان تبان من أول نظرة.
        with st.container(border=True, key="map_card"):
            html_block(
                '<div class="fx-card-title">خريطة انتشار المذاهب</div>'
                "<p>كرة أرضية تدوّرها وتكبّرها بنفسك، وكل منطقة ملونة بمذهبها الغالب، "
                "ومعها كلام المصدر ورقم صفحته.</p>"
            )
            st.button("افتح الخريطة", key="welcome_map", icon=":material/public:",
                      on_click=go_to, args=(MAP_PAGE,))
        stats = self._controller.get_stats()
        n = to_arabic_digits
        html_block(
            DIVIDER +
            '<ol class="fx-steps">'
            "<li>اختر المذاهب اللي تبي تقارن بينها من الشريط الجانبي.</li>"
            "<li>تصفح أبواب الكتاب، أو ابحث عن مسألة.</li>"
            "<li>قارن الأقوال، واضغط على عرض الدليل تحت أي قول.</li>"
            "</ol>"
            f'<p class="fx-note">في التطبيق {n(stats["opinions"])} قولاً من '
            f'{n(stats["chapters"])} عنواناً و{n(stats["pages"])} صفحة. {DISCLAIMER}</p>'
        )

    # ================================================ خريطة المذاهب
    def render_map(self):
        madhab_map = self._controller.get_madhab_map()
        taymur, ashqar = madhab_map.sources["taymur"], madhab_map.sources["ashqar"]
        n = to_arabic_digits
        theme = "dark" if st.context.theme.type == "dark" else "light"
        palette = MAP_COLORS[theme]
        html_block(
            f'<h1 class="fx-title">انتشار المذاهب الأربعة</h1>{BAND}'
            f'<p class="fx-map-lead">كما وصفه {esc(taymur.author)} '
            f"(ت {n(taymur.author_death_year)}هـ) في خاتمة كتابه "
            f"«{esc(taymur.title)}»، وأضفنا ما زاده {esc(ashqar.author)} في كتابه "
            f"«{esc(ashqar.title)}». دوّر الكرة بالسحب، وكبّرها بعجلة الفأرة، "
            "ووقف على أي منطقة عشان تشوف كلام المؤلف.</p>"
            + self._map_legend(palette)
        )

        if not map_service_reachable():
            st.warning("الخريطة تحتاج إلى إنترنت. باقي التطبيق يشتغل عادي بدونه.",
                       icon=":material/wifi_off:")
        else:
            # ألوان المذاهب نفسها في الأعمدة، والخامس لغير الأربعة.
            colors = {**INKS[theme], OTHER_MADHAB_ID: palette["other"]}
            try:
                figure = map_figure(madhab_map, colors, palette,
                                    lambda region: self._region_hover(region, madhab_map.sources))
            except ImportError:
                st.warning("مكتبة الرسوم غير مثبتة. ثبّتها بهذا الأمر، ثم أعد تشغيل البرنامج:")
                st.code("pip install plotly")
            else:
                # بدون تنسيق المكتبة عشان تبقى ألواننا، والتكبير بعجلة الفأرة مسموح.
                st.plotly_chart(figure, theme=None, key="madhab_map",
                                config={"scrollZoom": True, "displayModeBar": False})

        if madhab_map.shapes is None:
            st.info("حدود المحافظات في مصر والسعودية والعراق ما تحمّلت بعد، فهذي الدول "
                    "ما انقسمت على الخريطة. شغّل ملف الاستيراد مرة والجهاز متصل بالإنترنت.")

        html_block(
            DIVIDER +
            '<p class="fx-note">'
            "الألوان تبين مذهب أهل السنة الغالب في المنطقة، لا نسبتهم من السكان، "
            "والوصف لزمان المؤلف قبل نحو مئة سنة. "
            "والمؤلف نفسه قال إنه اعتمد في كثير منه على مصادر أجنبية لقلة المصادر العربية "
            f'(<a href="{taymur.page_url(86)}" target="_blank">ص{n(86)}</a>). '
            "وتقسيم مصر والسعودية والعراق اجتهاد منا في ربط كلامه بالمحافظات اليوم، "
            "وسببه مكتوب عند كل منطقة. "
            'حدود المحافظات من <a href="https://www.geoboundaries.org" target="_blank">'
            "جيو باوندريز</a>، وأصلها من "
            '<a href="https://www.openstreetmap.org/copyright" target="_blank">'
            "خرائط الشارع المفتوحة</a>.</p>"
        )
        with st.expander("المناطق ومصادرها"):
            html_block(self._map_table(madhab_map))

    # المذاهب بألوانها ونجومها، مثل شريط المذاهب فوق المقارنة، ومعها اللون الخامس.
    def _map_legend(self, palette: dict) -> str:
        chips = "".join(
            f'<span style="--ink: var(--ink-{m.madhab_id})">{star(m.madhab_id)}{esc(m.name)}</span>'
            for m in self._madhabs.values()
        )
        chips += (f'<span><i class="fx-swatch" style="background:{palette["other"]}"></i>'
                  "غير الأربعة، أو لم يذكره المؤلف</span>")
        return f'<div class="fx-legend">{chips}</div>'

    def _madhab_label(self, madhab_id: int) -> str:
        if madhab_id == OTHER_MADHAB_ID:
            return "غير الأربعة، أو لم يذكره المؤلف"
        return self._madhabs[madhab_id].name

    # اللي يطلع لما توقف على منطقة: اسمها، ومذهبها، وكلام المؤلف ومصدره وصفحته.
    def _region_hover(self, region, sources: dict) -> str:
        lines = [f"<b>{esc(region.name)}</b>", self._madhab_label(region.madhab_id)]
        if region.quote:
            lines += short_lines(f"«{esc(region.quote)}»")
            lines.append(sources[region.source_id].short_citation(region.page))
        elif region.note:
            lines += short_lines(esc(region.note))
        return "<br>".join(lines)

    # جدول كل المناطق: المذهب، وكلام المؤلف، ورابط الصفحة في الشاملة، وتفسيرنا.
    # وتحته المناطق اللي ذكرها المؤلف وما لوّناها، مع السبب.
    def _map_table(self, madhab_map) -> str:
        def page_link(page: int, source_id: str) -> str:
            if not page:
                return ""
            source = madhab_map.sources[source_id]
            return (f'<a href="{source.page_url(page)}" target="_blank">'
                    f"{source.short_citation(page)}</a>")

        regions = sorted(madhab_map.regions, key=lambda r: (r.madhab_id or 9, r.name))
        rows = "".join(
            f"<tr><td>{esc(r.name)}</td><td>{self._madhab_label(r.madhab_id)}</td>"
            f'<td class="fx-q">{esc(r.quote)}</td><td>{page_link(r.page, r.source_id)}</td>'
            f'<td class="fx-n">{esc(r.note)}</td></tr>'
            for r in regions
        )
        mentions = "".join(
            f"<tr><td>{esc(m.name)}</td><td>{self._madhab_label(m.madhab_id)}</td>"
            f'<td class="fx-q">{esc(m.quote)}</td><td>{page_link(m.page, m.source_id)}</td>'
            f'<td class="fx-n">{esc(m.reason)}</td></tr>'
            for m in madhab_map.mentions
        )
        head = ("<tr><th>المنطقة</th><th>المذهب</th><th>كلام المؤلف</th>"
                "<th>المصدر</th><th>ملاحظتنا</th></tr>")
        return (
            f'<div class="fx-table-wrap"><table class="fx-table">{head}{rows}</table></div>'
            '<div class="fx-section">ذكرها المؤلف ولم نلوّنها</div>'
            f'<div class="fx-table-wrap"><table class="fx-table">{head}{mentions}</table></div>'
        )

    # ================================================== نبذة الإمام
    def render_imam(self, madhab_id: int):
        view = self._controller.get_imam(madhab_id)
        if view is None:
            st.info("ما لقينا هذا الإمام.")
            return
        profile, source, madhab = view.profile, view.source, view.madhab
        n = to_arabic_digits

        # أزرار للتنقل بين الأئمة الأربعة بدون الرجوع لشاشة البداية.
        # المفتاح يتغير مع كل إمام، عشان الاختيار يبدأ على الإمام المفتوح.
        key = f"imam_switch_{madhab_id}"
        st.segmented_control(
            "الأئمة الأربعة", options=list(IMAM_SHORT_NAMES), default=madhab_id,
            format_func=IMAM_SHORT_NAMES.get, key=key, on_change=switch_imam, args=(key,),
            label_visibility="collapsed", width="stretch",
        )

        life = f"ولد سنة {n(profile.born)}هـ"
        life += f" في {esc(profile.born_in)}" if profile.born_in else ""
        life += f"، وتوفي سنة {n(profile.died)}هـ"
        life += f" في {esc(profile.died_in)}" if profile.died_in else ""
        sections = "".join(
            f'<div class="fx-profile-title">{esc(section.title)}</div><ul class="fx-points">'
            + "".join(
                f"<li>{esc(point.text)} "
                f'<a class="fx-cite" href="{source.page_url(point.page)}" target="_blank">'
                f"{source.short_citation(point.page)}</a></li>"
                for point in section.points
            )
            + "</ul>"
            for section in profile.sections
        )
        html_block(
            f'<div class="fx-imam-head" style="--ink: var(--ink-{madhab_id})">'
            f"{star(madhab_id)}<span>{esc(madhab.name)}</span></div>"
            f'<h1 class="fx-title">{esc(profile.name)}</h1>{BAND}'
            f'<p class="fx-map-lead">{life}.</p>'
            f"{sections}"
        )
        st.button("شوف انتشار المذاهب على الخريطة", key="imam_to_map",
                  icon=":material/public:", on_click=go_to, args=(MAP_PAGE,))
        html_block(
            DIVIDER +
            f'<p class="fx-note">المصدر: {esc(source.author)} (ت {n(source.author_death_year)}هـ)، '
            f"«{esc(source.title)}»، {esc(source.edition)}. "
            "النقاط ملخصة بكلامنا، وكل نقطة معها رقم صفحتها في المطبوع، "
            "والرابط يفتح الصفحة نفسها في نسخة إلكترونية من الكتاب.</p>"
        )

    # ========================================================= الباب
    def render_chapter(self, chapter_id: int, selected: list[int]):
        view = self._controller.open_chapter(chapter_id, selected)
        if view is None:
            st.warning("هذا الباب غير موجود.")
            return

        crumbs = " ‹ ".join(esc(c.title) for c in view.path[:-1])
        html_block(
            (f'<div class="fx-crumbs">{crumbs}</div>' if crumbs else "")
            + f'<h1 class="fx-title">{esc(view.chapter.title)}</h1>'
            + '<div class="fx-meta">'
            + f'<span class="fx-cite">{view.page.citation()}</span>'
            + f'<a href="{view.page.shamela_url()}" target="_blank">افتح في الشاملة</a>'
            + "</div>" + BAND
        )

        # زرين جنب بعض: الإضافة للمفضلة، والتصدير.
        with st.container(horizontal=True):
            with st.popover("إضافة الباب إلى المفضلة"):
                note_key = f"note_{chapter_id}"
                st.text_input("ملاحظة، اختيارية", key=note_key)
                st.button("أضف", key=f"save_chapter_{chapter_id}",
                          on_click=save_bookmark, args=(chapter_id, None, note_key))
            self._export_menu(
                "تصدير", f"export_{chapter_id}",
                make_file=lambda fmt: self._controller.export(chapter_id, selected, fmt),
                file_name=lambda fmt: self._controller.export_file_name(view.chapter.title, fmt),
                disabled=not selected,
            )

        comparison, text = st.tabs(["مقارنة المذاهب", "نص الباب"])
        with comparison:
            self._render_comparison(view, selected)
        with text:
            if view.chapter.content:
                html_block(book_text(view.chapter.content))
            else:
                st.info("كل نص هذا الباب أقوال مذاهب، وتلقاها في تبويب المقارنة.")

    # أعمدة المقارنة: عمود لكل مذهب مختار، وفوقها شريط يلخص عدد الأقوال.
    def _render_comparison(self, view, selected: list[int]):
        if not selected:
            st.warning("اختر مذهب واحد على الأقل من الشريط الجانبي.")
            return
        if not view.chapter.opinions:
            # بعض العناوين تجمع أبواباً تحتها، والأقوال موجودة داخل هذي الأبواب.
            children = self._controller.browse(view.chapter.chapter_id)
            if children:
                html_block('<div class="fx-note">هذا عنوان يجمع أبواباً تحته، '
                           "والأقوال داخلها. افتح واحداً منها:</div>")
                for child in children:
                    st.button(child.title, key=f"child_{child.chapter_id}",
                              on_click=go_to, args=(child.chapter_id,))
            else:
                st.info("ما فيه أقوال مذاهب مفصلة في هذا الباب. اقرأ تبويب نص الباب.")
            return

        legend = []
        for madhab_id in selected:
            count = len(view.opinions_by_madhab.get(madhab_id, []))
            label = count_label(count) if count else "ما له قول مفصّل هنا"
            empty = "" if count else ' class="fx-empty"'
            legend.append(f"<span{empty}>{star(madhab_id)}{esc(self._madhabs[madhab_id].name)}، {label}</span>")
        html_block(f'<div class="fx-legend">{"".join(legend)}</div>')

        columns = st.columns(len(selected), gap="medium")
        for column, madhab_id in zip(columns, selected):
            with column:
                madhab = self._madhabs[madhab_id]
                opinions = view.opinions_by_madhab.get(madhab_id, [])
                html_block(
                    f'<div class="fx-col-head" style="--ink: var(--ink-{madhab_id})">'
                    f"{star(madhab_id)}<div><h3>{esc(madhab.name)}</h3>"
                    f"<small>{esc(madhab.imam)}</small></div></div>"
                )
                if not opinions:
                    html_block('<div class="fx-note">ما استُخرج قول مفصّل لهذا المذهب في '
                               "هذا الباب. راجع نص الباب، فالمؤلف يذكر فيه المتفق عليه.</div>")
                for opinion in opinions:
                    self._render_opinion(opinion, madhab_id, view.chapter)
        html_block(f'{DIVIDER}<p class="fx-note">{DISCLAIMER}</p>')

    # بطاقة قول واحد. مفتاحها يبدأ برقم المذهب، عشان تاخذ حبره من التنسيق.
    def _render_opinion(self, opinion, madhab_id: int, chapter):
        with st.container(key=f"op-m{madhab_id}-{opinion.opinion_id}"):
            others = [i for i in opinion.madhab_ids if i != madhab_id]
            notes = []
            if st.session_state.get("highlight") == opinion.opinion_id:
                notes.append("<span>هذا القول اللي فتحته</span>")
            if others:
                shared = "".join(f"<span>{star(i)}{esc(self._madhabs[i].name)}</span>"
                                 for i in others)
                notes.append(f"<span>مشترك مع</span>{shared}")
            if notes:
                html_block(f'<div class="fx-shared">{"".join(notes)}</div>')

            # نقص النص عند آخر مسافة قبل الحد، عشان ما تنقطع كلمة بالنص.
            text = opinion.text
            cut = text.rfind(" ", 0, PREVIEW_LENGTH) if len(text) > PREVIEW_LENGTH else len(text)
            html_block(book_text(text[:cut]))
            if cut < len(text):
                with st.expander("تكملة القول"):
                    html_block(book_text(text[cut:]))

            page = self._controller.get_page(opinion.page_id)
            place = "في الحاشية" if opinion.location == "footnote" else "في المتن"
            html_block(
                f'<div class="fx-foot"><span>{page.citation()}، {place}</span>'
                f'<a href="{page.shamela_url()}" target="_blank">الشاملة</a></div>'
            )

            # زر عرض الدليل يظهر بس لو فيه دليل.
            if opinion.evidence:
                with st.expander(f"عرض الدليل ({to_arabic_digits(len(opinion.evidence))})"):
                    for evidence in opinion.evidence:
                        label = "آية" if evidence.kind == "quran" else "حديث"
                        html_block(f'<div class="fx-kind">{label}</div>'
                                   + book_text(evidence.text, "fx-evidence"))

            # زرين في سطر واحد تحت القول: الإضافة للمفضلة، ونسخ القول مع مصدره.
            with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
                st.button("إضافة إلى المفضلة", key=f"save_{opinion.opinion_id}_{madhab_id}",
                          on_click=save_bookmark, args=(chapter.chapter_id, opinion.opinion_id),
                          type="tertiary")
                copy_button(self._controller.quote_opinion(opinion, chapter.title))


# ======================================================= التشغيل
AppView(controller()).render()
