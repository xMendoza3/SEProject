"""
اختبارات نبذة الأئمة: هل كل إمام موجود، وكل نقطة معها صفحتها؟
"""

import json
from pathlib import Path

import pytest

from src.map_data import MapRepository
from src.models import ImamProfile
from src.profiles import ProfileRepository

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def profiles():
    return ProfileRepository()


# الأئمة الأربعة كلهم موجودين، ولكل واحد أقسام فيها نقاط.
def test_all_four_imams_have_sections(profiles):
    for madhab_id in (1, 2, 3, 4):
        profile = profiles.get_profile(madhab_id)
        assert profile is not None
        assert profile.sections and all(section.points for section in profile.sections)


# كل إمام فيه قسم لطريقته في الاستنباط، وقسم لانتشار مذهبه، لأنها طلبات محمد.
def test_every_imam_has_method_and_spread(profiles):
    for madhab_id in (1, 2, 3, 4):
        titles = [section.title for section in profiles.get_profile(madhab_id).sections]
        assert "طريقته في الاستنباط" in titles
        assert "انتشار مذهبه" in titles


# سنوات الوفاة تطابق الخط الزمني في شاشة البداية.
def test_death_years_match_timeline(profiles):
    expected = {1: 150, 2: 179, 3: 204, 4: 241}
    assert {m: profiles.get_profile(m).died for m in expected} == expected


# نقطة بدون صفحة مرفوضة.
def test_point_without_page_is_rejected(profiles):
    profile = profiles.get_profile(1)
    section = profile.sections[0]
    broken = type(section)(section.title, (type(section.points[0])("نص", 0),))
    with pytest.raises(ValueError):
        ImamProfile(1, profile.name, 80, 150, "ashqar", (broken,))


# كتاب الأشقر مذكور في ملفين: الخريطة والنبذة. لازم بياناته نفسها في الاثنين.
def test_shared_source_is_identical(profiles):
    assert MapRepository().get_sources()["ashqar"] == profiles.get_source()
