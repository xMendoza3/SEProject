"""
ملف بيانات الخريطة: مستودع يقرأ مناطق المذاهب وحدودها من ملفات المشروع.

المناطق مكتوبة يدوياً في ملف واحد، أغلبها من خاتمة كتاب أحمد تيمور باشا،
والباقي من كتاب عمر الأشقر. وكل منطقة معها كلام المؤلف حرفياً ورقم صفحته،
عشان أي أحد يراجعها.
وحدود المحافظات للدول المقسومة تتحمّل مرة وحدة وقت الاستيراد،
وبعدها المستودع يقرأها من الجهاز، مثل ملفات الكتاب بالضبط.

ليش مستودع منفصل عن قاعدة البيانات؟
لأن هذي بيانات صغيرة ومكتوبة باليد، والأسهل إنها تبقى ملف نص يقدر أي أحد يقرأه ويصححه.
والمتحكم ما يفرق معه: يطلب المناطق من المستودع، وما يعرف هي محفوظة وين.
"""

import json
from pathlib import Path

from src.models import MapMention, MapRegion, Source

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP_FILE = PROJECT_ROOT / "data" / "madhab_map.json"
DEFAULT_SHAPES_DIR = PROJECT_ROOT / "data" / "raw" / "boundaries"


class MapRepository:

    def __init__(self, map_file: Path = DEFAULT_MAP_FILE, shapes_dir: Path = DEFAULT_SHAPES_DIR):
        self._shapes_dir = Path(shapes_dir)
        data = json.loads(Path(map_file).read_text(encoding="utf-8"))
        # النجمتين تفكان القاموس: كل مفتاح فيه يصير اسم حقل في الكائن.
        self._sources = {item["source_id"]: Source(**item) for item in data["sources"]}
        # المحافظات تجي من الملف قائمة، والنموذج يبيها صف ثابت، فنحوّلها.
        self._regions = [MapRegion(**{**item, "units": tuple(item.get("units", ()))})
                         for item in data["regions"]]
        self._mentions = [MapMention(**item) for item in data["mentions"]]
        # الحدود ملفات كبيرة شوي، فنقرأها مرة وحدة ونحفظها هنا.
        self._shapes = None

    # المصادر كلها، بمعرفاتها. كل منطقة تعرف معرف مصدرها.
    def get_sources(self) -> dict[str, Source]:
        return dict(self._sources)

    def get_regions(self) -> list[MapRegion]:
        return list(self._regions)

    def get_mentions(self) -> list[MapMention]:
        return list(self._mentions)

    # الدول اللي قسمناها لمحافظات، وتحتاج ملف حدود.
    def split_countries(self) -> list[str]:
        return sorted({region.country for region in self._regions if region.is_partial()})

    # مكان ملف حدود الدولة. المستودع هو اللي يقرر أسماء الملفات،
    # والساحب يحفظ في المكان اللي يعطيه إياه.
    def shapes_file(self, country: str) -> Path:
        return self._shapes_dir / f"{country}_regions.geojson"

    # حدود محافظات الدول المقسومة كلها في مجموعة وحدة.
    # كل محافظة نعطيها معرّف هو رمزها الدولي، عشان الخريطة تربطها بمنطقتها.
    # ترجع لا شي لو ملف أي دولة ناقص، والواجهة وقتها تنبه المستخدم.
    def get_shapes(self) -> dict | None:
        if self._shapes is not None:
            return self._shapes
        features = []
        for country in self.split_countries():
            path = self.shapes_file(country)
            if not path.exists():
                return None
            collection = json.loads(path.read_text(encoding="utf-8"))
            for feature in collection["features"]:
                code = feature.get("properties", {}).get("shapeISO")
                if code:
                    features.append({**feature, "id": code,
                                     "geometry": rewind(feature.get("geometry"))})
        self._shapes = {"type": "FeatureCollection", "features": features}
        return self._shapes


# ===================================================== اتجاه الحدود
# مكتبة الرسوم ترسم على كرة، والكرة ما لها داخل وخارج واضح مثل الورقة:
# أي خط مقفل يقسمها قسمين. فالمكتبة تعرف أي قسم هو المحافظة من اتجاه رسم حدودها:
# الحدود الخارجية لازم تمشي مع عقارب الساعة، والفتحات داخلها عكسها.
# ملفات الحدود مرسومة بالاتجاه المعاكس، حسب المعيار العام لهذي الملفات،
# فكانت المكتبة تفهم كل محافظة إنها العالم كله ما عدا المحافظة، وتغطي الكرة كاملة.
# الحل: نقلب أي حلقة مرسومة بالعكس قبل ما نعطيها للخريطة.

# مساحة الحلقة بصيغة رباط الحذاء: موجبة لو الرسم عكس عقارب الساعة، وسالبة لو معها.
# النجمة تتجاهل الارتفاع لو كان مع النقطة رقم ثالث.
def signed_area(ring: list) -> float:
    return sum(x1 * y2 - x2 * y1
               for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:])) / 2


# المضلع قائمة حلقات: الأولى حدوده الخارجية، وما بعدها فتحات داخله.
def clockwise_polygon(rings: list) -> list:
    fixed = []
    for index, ring in enumerate(rings):
        wants_clockwise = index == 0
        is_clockwise = signed_area(ring) < 0
        fixed.append(ring if is_clockwise == wants_clockwise else ring[::-1])
    return fixed


# المحافظة إما مضلع واحد، أو عدة مضلعات مثل الجزر. وأي شكل ثاني يرجع مثل ما هو.
def rewind(geometry: dict | None) -> dict | None:
    if not geometry:
        return geometry
    if geometry["type"] == "Polygon":
        return {**geometry, "coordinates": clockwise_polygon(geometry["coordinates"])}
    if geometry["type"] == "MultiPolygon":
        return {**geometry, "coordinates": [clockwise_polygon(polygon)
                                            for polygon in geometry["coordinates"]]}
    return geometry
