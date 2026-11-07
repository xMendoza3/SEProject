"""
ملف النماذج: طبقة النموذج في المشروع.

كل كلاس هنا وظيفته يحفظ بيانات ويجاوب على أسئلة بسيطة عن نفسه.
ما يعرف شي عن قاعدة البيانات ولا الإنترنت ولا الواجهة،
وهذا اللي يخليه سهل في الاختبار وسهل نستخدمه في كل الطبقات.
"""

# نجيب أداة جاهزة تكتب لنا كود الكلاسات تلقائياً،
# ومعها أداة صغيرة نحتاجها لحالة خاصة في المفضلة تحت.
from dataclasses import dataclass, field

# نوع التاريخ والوقت، نستخدمه لوقت حفظ المفضلة.
from datetime import datetime


# ====================================================== الثوابت
# الاسم اللي كله حروف كبيرة عُرف معناه: ثابت، لا تغيّرني.
# فايدته: لو تغيّر الرابط، نعدّل هنا سطر واحد بس.
SHAMELA_BOOK_URL = "https://shamela.ws/book/9849"

# أنواع الأدلة المسموحة: آية أو حديث.
EVIDENCE_KINDS = ("quran", "hadith")

# أماكن القول المسموحة: في المتن أو في الحاشية.
OPINION_LOCATIONS = ("main", "footnote")


# ================================================ تحويل الأرقام
# جدول تحويل: كل رقم إنجليزي ومقابله العربي.
# الشرطة السفلية في أول الاسم معناها: هذا للاستخدام داخل الملف بس.
_ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


# دالة تاخذ رقم وترجع نص بأرقام الكتاب المطبوع.
# الكلام بعد النقطتين وبعد السهم اسمه تلميحات الأنواع:
# بايثون ما يجبرك عليه، لكنه يوضّح للقارئ ويخلي المحرر ينبهك لو غلطت.
def to_arabic_digits(number: int) -> str:
    # نحوّل الرقم لنص، ثم نبدّل كل خانة فيه حسب الجدول.
    return str(number).translate(_ARABIC_DIGITS)


# ================================================== كلاس المذهب
# السطر اللي يبدأ بعلامة الآت اسمه مزخرف، يضيف قدرات للكلاس اللي تحته.
# هذا بالذات يكتب لنا دالة الإنشاء والطباعة والمقارنة تلقائياً.
# والتجميد يمنع تعديل أي حقل بعد ما ينشأ الكائن.
# الكلاس كله يعادل في الجافا: حقول خاصة ودالة إنشاء ودوال قراءة.
@dataclass(frozen=True)
class Madhab:
    # كل سطر حقل ونوعه.
    madhab_id: int
    # الاسم مثل ما يكتبه الكتاب بالضبط.
    name: str
    imam: str
    # علامة يساوي معناها قيمة افتراضية: تقدر تنشئ مذهب بدون سيرة.
    # قاعدة: الحقول اللي لها قيمة افتراضية لازم تجي بعد اللي ما لها.
    # السيرة فاضية للحين، وبنعبيها لاحقاً من مصدر موثّق.
    biography: str = ""
    regions: str = ""


# المذاهب الأربعة، مرتبة حسب وفاة الأئمة.
# هذا المصدر الوحيد للحقيقة: قاعدة البيانات بتاخذ المذاهب من هنا،
# فما يصير عندنا نسختين ممكن تختلف عن بعض.
MADHABS = (
    Madhab(1, "الحنفية", "أبو حنيفة النعمان بن ثابت"),
    Madhab(2, "المالكية", "مالك بن أنس"),
    Madhab(3, "الشافعية", "محمد بن إدريس الشافعي"),
    Madhab(4, "الحنابلة", "أحمد بن حنبل"),
)

# قاموس يوصلك من اسم المذهب للمذهب نفسه.
# المستخرج بيلقى كلمة الحنفية في النص، ويحتاج يعرف رقمها.
# هذي صيغة مختصرة لحلقة تمر على المذاهب وتضيف كل واحد للقاموس.
MADHAB_BY_NAME = {madhab.name: madhab for madhab in MADHABS}

# مجموعة الأرقام الصحيحة من واحد إلى أربعة، نستخدمها في الفحص تحت.
VALID_MADHAB_IDS = {madhab.madhab_id for madhab in MADHABS}


# =================================================== كلاس الدليل
@dataclass(frozen=True)
class Evidence:
    # النوع: آية أو حديث.
    kind: str
    # نص الدليل منقول من الكتاب حرفياً، ما نعيد صياغته أبداً.
    text: str

    # دالة يناديها بايثون تلقائياً بعد الإنشاء مباشرة، فنستغلها للفحص.
    def __post_init__(self):
        # إذا النوع مو من الأنواع المسموحة، نطلق خطأ يوقف كل شي.
        # الفكرة: لو المستخرج غلط، نعرف فوراً وقت الاستيراد،
        # بدل ما يوصل للشاشة شي غلط.
        if self.kind not in EVIDENCE_KINDS:
            raise ValueError(f"unknown evidence kind: {self.kind!r}")


# ================================================== كلاس الصفحة
@dataclass(frozen=True)
class Page:
    # ترتيب الصفحة في النسخة الرقمية، مثل ٣٠٨. يُستخدم للرابط.
    page_id: int
    # رقم الجزء من واحد إلى خمسة.
    volume: int
    # رقم الصفحة في الكتاب الورقي، مثل ٣١٠. يُستخدم للتوثيق.
    printed_page: int
    # النص اللي فوق الخط.
    main_text: str
    # النص اللي تحت الخط.
    footnote_text: str

    # تبني التوثيق بأسلوب الكتاب، مثل: ج١ ص٣١٠
    # أول كلمة بين القوسين معناها: الكائن نفسه.
    def citation(self) -> str:
        return f"ج{to_arabic_digits(self.volume)} ص{to_arabic_digits(self.printed_page)}"

    # تبني رابط نفس الصفحة في الشاملة، عشان القارئ يتحقق بنفسه.
    # لاحظ إننا نحسب الرابط بدل ما نخزنه:
    # لو تغيّر شكل الروابط، نعدّل سطر واحد وكلها تتصلح.
    def shamela_url(self) -> str:
        return f"{SHAMELA_BOOK_URL}/{self.page_id}"


# ================================================= كلاس قطعة النص
# قطعة من نص الكتاب، ومعروف بابها وصفحتها ومكانها.
# المحلل يقطّع الكتاب لقطع، والمستخرج يدوّر فيها على أقوال المذاهب.
# فايدتها: الحاشية الطويلة ممكن تمتد على صفحات كثيرة،
# والقطعة تحفظ لنا إنها تابعة لباب معيّن حتى لو المتن انتقل لباب ثاني.
@dataclass(frozen=True)
class TextBlock:
    chapter_id: int
    page_id: int
    # متن أو حاشية.
    location: str
    # النص بالحرف، بعد شيل وسوم صفحات الويب بس.
    text: str

    def __post_init__(self):
        if self.location not in OPINION_LOCATIONS:
            raise ValueError(f"unknown location: {self.location!r}")


# =================================================== كلاس القول
@dataclass(frozen=True)
class Opinion:
    opinion_id: int
    # رقم الباب ورقم الصفحة: هذي الحقول تنفّذ الأسهم اللي في المخطط.
    chapter_id: int
    page_id: int
    # صف أرقام بأي طول: مذهب واحد أو أكثر،
    # لأن المؤلف يجمع المذاهب المتفقة في عبارة وحدة.
    # استخدمنا صف بدل قائمة: التجميد يحمي الحقل،
    # لكن القائمة تقبل إضافة عناصر عليها، والصف ما يقبل.
    madhab_ids: tuple[int, ...]
    # متن أو حاشية.
    location: str
    # كلام المؤلف بالحرف.
    text: str
    # الآيات والأحاديث اللي داخل القول.
    # الصف الفاضي قيمة افتراضية، يعني قول بدون أدلة.
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self):
        # الفحص الأول: المكان لازم يكون متن أو حاشية.
        if self.location not in OPINION_LOCATIONS:
            raise ValueError(f"unknown location: {self.location!r}")
        # الفحص الثاني: الصف الفاضي يُحسب خطأ في الشروط،
        # فهذا معناه: ما فيه ولا مذهب.
        if not self.madhab_ids:
            raise ValueError("an opinion must belong to at least one madhab")
        # الفحص الثالث: نحوّل الأرقام لمجموعة،
        # وعلامة أصغر أو يساوي بين مجموعتين معناها: محتواة في.
        # يعني كل الأرقام لازم تكون من المذاهب الأربعة.
        if not set(self.madhab_ids) <= VALID_MADHAB_IDS:
            raise ValueError(f"invalid madhab ids: {self.madhab_ids}")
        # الفحص الرابع: المجموعة تحذف التكرار تلقائياً.
        # لو نقص العدد بعد التحويل، معناه فيه رقم مكرر.
        if len(set(self.madhab_ids)) != len(self.madhab_ids):
            raise ValueError(f"repeated madhab ids: {self.madhab_ids}")

    # سؤال بسيط: هل هذا القول للمذهب الفلاني؟
    def belongs_to(self, madhab_id: int) -> bool:
        return madhab_id in self.madhab_ids


# ==================================================== كلاس الباب
@dataclass(frozen=True)
class Chapter:
    # رقم العنوان في فهرس الكتاب، من واحد إلى ٩٤٠.
    chapter_id: int
    title: str
    # عمق العنوان في الشجرة: ١ للجزء، ٢ لمثل كتاب الطهارة، وتحتها المباحث.
    level: int
    # رقم العنوان اللي فوقه.
    # الخط العمودي معناه أو: يا رقم يا لا شي، لأن الجزء ما فوقه شي.
    parent_id: int | None
    # الصفحة اللي يبدأ فيها العنوان.
    page_id: int
    # كلام المؤلف في الباب، بدون أقوال المذاهب.
    content: str = ""
    # أقوال الباب. هذا التركيب اللي في المخطط: الأقوال جزء من الباب.
    opinions: tuple[Opinion, ...] = ()

    # من الإصدار الأول وخليناها: ترجع ملخص الباب كقاموس.
    def get_details(self) -> dict:
        return {
            "id": self.chapter_id,
            "title": self.title,
            "level": self.level,
            "page_id": self.page_id,
            # عدد الأقوال بدل الأقوال نفسها، لأنه ملخص.
            "opinions": len(self.opinions),
        }

    # قلب فكرة المقارنة: ترجع أقوال المذاهب اللي اختارها المستخدم بس.
    # مثال: اخترت الحنفية بس، والقول للمالكية والشافعية والحنابلة،
    # فالتقاطع فاضي والقول ما يظهر.
    def get_opinions(self, madhab_ids) -> list[Opinion]:
        # المذاهب المختارة، كمجموعة.
        wanted = set(madhab_ids)
        # التقاطع: المذاهب المشتركة بين المختارة ومذاهب القول.
        # لو اشتركوا ولو في مذهب واحد، القول يظهر.
        # هذي صيغة مختصرة لحلقة تمر على الأقوال وتضيف المطابق لقائمة.
        return [opinion for opinion in self.opinions
                if wanted.intersection(opinion.madhab_ids)]


# ================================================== كلاس المفضلة
@dataclass(frozen=True)
class Bookmark:
    chapter_id: int
    # لا شي معناها حفظت الباب كامل، ورقم معناه حفظت قول محدد.
    opinion_id: int | None = None
    note: str = ""
    # هنا نعطيه الدالة نفسها بدون أقواس، وهو يناديها كل مرة ننشئ مفضلة.
    # لو كتبناها بأقواس، تنحسب مرة وحدة وقت تحميل الملف،
    # وكل المفضلات تاخذ نفس الوقت.
    created_at: datetime = field(default_factory=datetime.now)
    # رقم المفضلة تعطيه قاعدة البيانات وقت الحفظ، فقبله يكون لا شي.
    # وحطيناه آخر حقل لأن له قيمة افتراضية.
    bookmark_id: int | None = None


# ============================================ المصادر خارج كتاب الجزيري
# الخريطة ونبذة الأئمة لها مصادرها: كتب نوثّق منها بالصفحة، مثل الكتاب الأصلي.
@dataclass(frozen=True)
class Source:
    # معرف قصير نربط به المناطق والسير بمصدرها.
    source_id: str
    title: str
    author: str
    # سنة وفاة المؤلف بالهجري، عشان القارئ يعرف زمن الكلام.
    author_death_year: int
    # رابط أي صفحة في الكتاب، ومكان رقم الصفحة فيه بين قوسين معقوفين.
    url_pattern: str
    # الفرق بين رقم الصفحة المطبوع ورقمها في الموقع، لأن بعض المواقع تعدّ المقدمات.
    page_offset: int = 0
    # اسم مختصر للمؤلف في التوثيق القصير، مثل: تيمور، الأشقر.
    short_name: str = ""
    # الناشر والطبعة، لو نعرفها بثقة.
    edition: str = ""

    def page_url(self, page: int) -> str:
        return self.url_pattern.format(page=page - self.page_offset)

    def citation(self, page: int) -> str:
        return f"{self.author}، {self.title}، ص{to_arabic_digits(page)}"

    def short_citation(self, page: int) -> str:
        return f"{self.short_name or self.author}، ص{to_arabic_digits(page)}"


# ================================================ نماذج خريطة المذاهب
# رقم صفر في الخريطة معناه: مذهب غير الأربعة، أو منطقة ما ذكرها المصدر.
OTHER_MADHAB_ID = 0


# منطقة ملونة على الخريطة: دولة كاملة، أو جزء من دولة.
@dataclass(frozen=True)
class MapRegion:
    # الاسم اللي يظهر للمستخدم.
    name: str
    # رمز الدولة الدولي من ثلاثة حروف.
    country: str
    madhab_id: int
    # كلام المؤلف حرفياً، ورقم صفحته في كتابه.
    # المناطق اللي ما ذكرها المؤلف: الكلام فاضي والصفحة صفر.
    quote: str = ""
    page: int = 0
    # تفسيرنا لاسم المنطقة لو احتاج، مثل: طرابلس الغرب هي ليبيا اليوم.
    note: str = ""
    # رموز المحافظات لو المنطقة جزء من دولة. فاضية معناها الدولة كاملة.
    units: tuple[str, ...] = ()
    # مصدر الكلام. أغلب المناطق من كتاب تيمور.
    source_id: str = "taymur"

    def __post_init__(self):
        if self.madhab_id != OTHER_MADHAB_ID and self.madhab_id not in VALID_MADHAB_IDS:
            raise ValueError(f"unknown madhab id {self.madhab_id} in {self.name}")
        # كل لون له مصدر: لو المنطقة ملونة بمذهب، لازم معها كلام المؤلف وصفحته.
        if self.madhab_id != OTHER_MADHAB_ID and not (self.quote and self.page):
            raise ValueError(f"{self.name} has a madhab but no quote or page")

    def is_partial(self) -> bool:
        return bool(self.units)


# منطقة ذكرها المؤلف لكن ما لوّناها، ومعها السبب.
# مثل بلاد القوقاز: إقليم تاريخي يتوزع اليوم على أكثر من دولة.
@dataclass(frozen=True)
class MapMention:
    name: str
    madhab_id: int
    quote: str
    page: int
    reason: str
    source_id: str = "taymur"


# ================================================== نماذج نبذة الأئمة
# النبذة أقسام، مثل نسبه وعصره، وكل قسم نقاط قصيرة.
# النقطة كلامنا نحن، نلخص فيه المصدر، ومعها رقم الصفحة اللي لخصناها منها.
@dataclass(frozen=True)
class ProfilePoint:
    text: str
    page: int


@dataclass(frozen=True)
class ProfileSection:
    title: str
    points: tuple[ProfilePoint, ...]


@dataclass(frozen=True)
class ImamProfile:
    madhab_id: int
    # الاسم الكامل مع الكنية.
    name: str
    # سنة المولد والوفاة بالهجري.
    born: int
    died: int
    source_id: str
    sections: tuple[ProfileSection, ...]
    # مكان المولد والوفاة، ونتركه فاضي لو المصدر ما ذكره صراحة.
    born_in: str = ""
    died_in: str = ""

    def __post_init__(self):
        if self.madhab_id not in VALID_MADHAB_IDS:
            raise ValueError(f"unknown madhab id {self.madhab_id}")
        # كل نقطة لازم معها صفحة، عشان القارئ يرجع للمصدر.
        for section in self.sections:
            for point in section.points:
                if point.page <= 0:
                    raise ValueError(f"point without page in {self.name}: {point.text[:30]}")


# ======================================================= التجربة
# هالشرط يتحقق بس لما تشغّل هذا الملف مباشرة.
# لو ملف ثاني استورد النماذج، الكود اللي تحته ما يشتغل.
if __name__ == "__main__":
    # صفحة حقيقية من الكتاب: الصفحة ٣٠٨ في النسخة الرقمية،
    # وهي الجزء الأول صفحة ٣١٠ في المطبوع.
    page = Page(
        page_id=308, volume=1, printed_page=310,
        main_text="... وخالف الشافعية. فانظر مذهبهم تحت الخط (٤) .",
        footnote_text="(٤) الشافعية قالوا: إن خرج وقتها قضيت مطلقًا",
    )
    # قول الشافعية من حاشية نفس الصفحة. رقم المذهب ٣ هو الشافعية.
    opinion = Opinion(
        opinion_id=1, chapter_id=267, page_id=page.page_id,
        madhab_ids=(3,), location="footnote",
        text="الشافعية قالوا: إن خرج وقتها قضيت مطلقًا",
    )
    # العنوان رقم ٢٦٧ في فهرس الكتاب، ويبدأ في الصفحة ٣٠٧.
    chapter = Chapter(
        chapter_id=267, title="صلاة التراويح: حكمها، ووقتها", level=4,
        parent_id=None, page_id=307, opinions=(opinion,),
    )

    print("citation:      ", page.citation())
    print("shamela link:  ", page.shamela_url())
    print("chapter:       ", chapter.get_details())
    print("shafii only:   ", len(chapter.get_opinions([3])), "opinion(s)")
    print("hanafi only:   ", len(chapter.get_opinions([1])), "opinion(s)")

    # نجرب نعدّل نص القول، ونتوقع إن التجميد يرفض.
    # الكلمة الأولى معناها جرّب،
    # والثانية معناها: لو طلع هذا الخطأ، سوّ كذا بدل ما يطيح البرنامج.
    try:
        opinion.text = "نص آخر"
    except AttributeError as error:
        print("edit refused:  ", type(error).__name__)

    # نجرب ننشئ قول لمذهب رقم ٧، ونتوقع إن الفحص يرفض.
    try:
        Opinion(2, 267, 308, madhab_ids=(7,), location="footnote", text="...")
    except ValueError as error:
        print("bad data:      ", error)
