"""
اختبارات خريطة المذاهب: هل كل لون له مصدر، وكل محافظة لها منطقة وحدة؟
"""

import json
from pathlib import Path

import pytest

from src.map_data import MapRepository, rewind, signed_area
from src.models import OTHER_MADHAB_ID, MapRegion
from src.scraper import BoundaryScraper

# نص خاتمة كتاب أحمد تيمور، من الصفحة ٨٦ إلى ٨٩، منسوخ من الشاملة.
SOURCE_PAGES = Path(__file__).resolve().parent.parent / "data" / "raw" / "taymur_96605_conclusion.json"


@pytest.fixture
def atlas():
    return MapRepository()


# أهم اختبار: كل كلام منسوب لتيمور موجود حرفياً في الصفحة المذكورة معه.
# كتاب تيمور قديم ونصه متاح، فحفظنا صفحاته. كتاب الأشقر حديث وله حقوق،
# فما حفظنا نصه، وكلامه في الخريطة جملة وحدة تأكدنا منها يدوياً من صفحتها.
def test_every_quote_is_in_its_page(atlas):
    pages = json.loads(SOURCE_PAGES.read_text(encoding="utf-8"))["pages"]
    items = [region for region in atlas.get_regions() if region.quote] + atlas.get_mentions()
    for item in items:
        if item.source_id == "taymur":
            assert item.quote in pages[str(item.page)], item.name


# كل منطقة ومذكورة مصدرها معروف.
def test_every_item_has_a_known_source(atlas):
    sources = atlas.get_sources()
    for item in atlas.get_regions() + atlas.get_mentions():
        assert item.source_id in sources, item.name


# كل محافظة في الدول المقسومة تابعة لمنطقة وحدة بس.
def test_each_unit_belongs_to_one_region(atlas):
    owner = {}
    for region in atlas.get_regions():
        for unit in region.units:
            assert unit not in owner, f"{unit}: {owner.get(unit)} / {region.name}"
            owner[unit] = region.name


# الدولة إما كاملة بلون واحد، أو مقسومة. ما يصير الاثنين مع بعض.
def test_country_is_whole_or_split(atlas):
    whole = {code for region in atlas.get_regions() if not region.is_partial()
             for code in region.countries()}
    assert whole.isdisjoint(atlas.split_countries())


# كل منطقة تظهر في جدول المصادر مرة وحدة، وكل دولة لها لون واحد.
def test_regions_and_countries_are_not_repeated(atlas):
    names = [region.name for region in atlas.get_regions()]
    assert len(names) == len(set(names))
    codes = [code for region in atlas.get_regions() if not region.is_partial()
             for code in region.countries()]
    assert len(codes) == len(set(codes))


# لون بدون مصدر مرفوض. والمنطقة بدون مذهب ما تحتاج مصدر.
def test_madhab_without_quote_is_rejected():
    with pytest.raises(ValueError):
        MapRegion("مكان", "XXX", 3)
    MapRegion("مكان", "XXX", OTHER_MADHAB_ID)


# المستودع يعطي كل محافظة معرّفها، ويرجع لا شي لو ملف دولة ناقص.
def test_shapes_get_ids_and_missing_file_gives_none(tmp_path):
    assert MapRepository(shapes_dir=tmp_path).get_shapes() is None
    atlas = MapRepository(shapes_dir=tmp_path)
    for country in atlas.split_countries():
        feature = {"type": "Feature", "properties": {"shapeISO": f"{country}-1"}, "geometry": None}
        atlas.shapes_file(country).write_text(json.dumps({"features": [feature]}), encoding="utf-8")
    ids = [feature["id"] for feature in atlas.get_shapes()["features"]]
    assert ids == [f"{country}-1" for country in atlas.split_countries()]


# لما تتحمّل ملفات الحدود الحقيقية: رموز المحافظات عندنا لازم تطابق الملفات تماماً.
# لو الملفات ما تحمّلت بعد، الاختبار يتخطى نفسه.
def _boundaries_downloaded() -> bool:
    atlas = MapRepository()
    return all(atlas.shapes_file(country).exists() for country in atlas.split_countries())


@pytest.mark.skipif(not _boundaries_downloaded(), reason="boundary files not downloaded yet")
def test_units_match_boundary_files(atlas):
    codes = {feature["id"] for feature in atlas.get_shapes()["features"]}
    units = {unit for region in atlas.get_regions() for unit in region.units}
    assert units == codes


# الساحب ما يتصل بالإنترنت أبداً لو الملف موجود.
def test_boundary_scraper_skips_existing_file(tmp_path, monkeypatch):
    target = tmp_path / "EGY_regions.geojson"
    target.write_text("{}", encoding="utf-8")

    def no_network(*args, **kwargs):
        raise AssertionError("network was used")

    monkeypatch.setattr("src.scraper.requests.get", no_network)
    assert BoundaryScraper().fetch_regions("EGY", target) == target


# الساحب يسأل الموقع عن رابط الملف المبسط، ثم يحمّله ويحفظه.
def test_boundary_scraper_follows_simplified_link(tmp_path, monkeypatch):
    class Response:
        def __init__(self, payload):
            self._payload = payload
            self.content = json.dumps(payload).encode("utf-8")

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    asked = []

    def fake_get(url, **kwargs):
        asked.append(url)
        if "/api/" in url:
            return Response({"simplifiedGeometryGeoJSON": "https://files.example/egy.geojson"})
        return Response({"type": "FeatureCollection", "features": []})

    monkeypatch.setattr("src.scraper.requests.get", fake_get)
    monkeypatch.setattr("src.scraper.time.sleep", lambda seconds: None)
    target = tmp_path / "boundaries" / "EGY_regions.geojson"
    BoundaryScraper().fetch_regions("EGY", target)
    assert asked[1] == "https://files.example/egy.geojson"
    assert json.loads(target.read_text(encoding="utf-8"))["type"] == "FeatureCollection"


# مربع مرسوم عكس عقارب الساعة، وفيه فتحة مرسومة معها: الاثنين بالاتجاه الغلط للمكتبة.
# بعد التصحيح: الحدود الخارجية مع عقارب الساعة، والفتحة عكسها.
def test_rewind_fixes_ring_directions():
    outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[2, 2], [2, 4], [4, 4], [4, 2], [2, 2]]
    fixed = rewind({"type": "Polygon", "coordinates": [outer, hole]})["coordinates"]
    assert signed_area(fixed[0]) < 0
    assert signed_area(fixed[1]) > 0
    # الشكل الصحيح من البداية ما يتغير.
    assert rewind({"type": "Polygon", "coordinates": fixed})["coordinates"] == fixed


# في الملفات الحقيقية: بعد التحميل، كل الحدود الخارجية مع عقارب الساعة.
@pytest.mark.skipif(not _boundaries_downloaded(), reason="boundary files not downloaded yet")
def test_real_boundaries_are_clockwise(atlas):
    for feature in atlas.get_shapes()["features"]:
        geometry = feature["geometry"]
        polygons = ([geometry["coordinates"]] if geometry["type"] == "Polygon"
                    else geometry["coordinates"])
        for polygon in polygons:
            assert signed_area(polygon[0]) < 0, feature["id"]
