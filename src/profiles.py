"""
ملف نبذة الأئمة: مستودع يقرأ سير الأئمة الأربعة من ملف في المشروع.

السير مكتوبة باختصار بكلامنا، ملخصة من كتاب عمر سليمان الأشقر،
المدخل إلى دراسة المدارس والمذاهب الفقهية. وكل نقطة معها رقم الصفحة اللي لخصناها منها.
ما ننقل كلامه حرفياً، لأن الكتاب حديث وله حقوق، والتلخيص مع التوثيق يكفي القارئ.
"""

import json
from pathlib import Path

from src.models import ImamProfile, ProfilePoint, ProfileSection, Source

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILES_FILE = PROJECT_ROOT / "data" / "imam_profiles.json"


class ProfileRepository:

    def __init__(self, profiles_file: Path = DEFAULT_PROFILES_FILE):
        data = json.loads(Path(profiles_file).read_text(encoding="utf-8"))
        self._source = Source(**data["source"])
        self._profiles = {item["madhab_id"]: self._to_profile(item) for item in data["imams"]}

    def get_source(self) -> Source:
        return self._source

    def get_profile(self, madhab_id: int) -> ImamProfile | None:
        return self._profiles.get(madhab_id)

    # الملف فيه قوائم وقواميس، والنموذج يبي صفوف ثابتة من كائنات، فنحوّل طبقة طبقة.
    @staticmethod
    def _to_profile(item: dict) -> ImamProfile:
        sections = tuple(
            ProfileSection(
                title=section["title"],
                points=tuple(ProfilePoint(**point) for point in section["points"]),
            )
            for section in item["sections"]
        )
        return ImamProfile(**{**item, "sections": sections})
