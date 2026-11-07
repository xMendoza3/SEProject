"""
ملف السحب: كل اتصال بالإنترنت في المشروع موجود هنا، في كلاسين.

ساحب الكتاب يجيب بيانات الكتاب الخام من موقع تراث.
وساحب الحدود يجيب حدود المحافظات للدول اللي قسمناها في خريطة المذاهب.

الاثنين يحمّلون مرة وحدة بس. لو الملفات موجودة في مجلد البيانات،
يقرؤونها من الجهاز وما يتصلون بالإنترنت أبداً.
"""

import json
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"

BOOK_ID = 9849
HEADERS = {
    "User-Agent": "FiqhExplorer-StudentProject/0.1 "
                  "(university software engineering project)"
}


class FiqhScraper:

    def __init__(self, raw_dir: Path = DEFAULT_RAW_DIR, book_id: int = BOOK_ID):
        self._api_url = "https://api.turath.io/book"
        self._files_url = "https://files.turath.io/books-v3"
        self._raw_dir = Path(raw_dir)
        self._book_id = book_id

    # الفهرس وخريطة الصفحات.
    def fetch_index(self) -> dict:
        path = self._download(
            self._api_url,
            {"id": self._book_id, "include": "indexes", "ver": 3},
            self._raw_dir / f"turath_{self._book_id}_info.json",
        )
        return self._read_json(path)

    # نص كل صفحات الكتاب.
    def fetch_book(self) -> dict:
        path = self._download(
            f"{self._files_url}/{self._book_id}.json",
            None,
            self._raw_dir / f"turath_{self._book_id}_book.json",
        )
        return self._read_json(path)

    # تحمّل ملف واحد، إلا لو كان موجود.
    # تكتب في ملف مؤقت أول، ثم تعيد تسميته، فما يبقى ملف ناقص لو انقطع النت.
    def _download(self, url: str, params: dict | None, target: Path) -> Path:
        if target.exists() and target.stat().st_size > 0:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".part")
        with requests.get(url, params=params, headers=HEADERS,
                          stream=True, timeout=60) as response:
            # تطلق خطأ لو الموقع رد بأي شي غير نجاح.
            response.raise_for_status()
            with open(temporary, "wb") as file:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    file.write(chunk)
        temporary.replace(target)
        # نهدّي شوي قبل الطلب الجاي، احتراماً للموقع.
        time.sleep(1.5)
        return target

    # تقرأ الملف، ولو كان تالف تحذفه عشان المرة الجاية يتحمّل من جديد.
    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            path.unlink()
            raise ValueError(f"{path.name} was corrupted and has been deleted, run again")


# ===================================================== ساحب الحدود
# حدود المحافظات من مشروع جيو باوندريز المفتوح، ومصدره خرائط الشارع المفتوحة.
# الطلب الأول يرجع معلومات الملف، وفيها رابط النسخة المبسطة من الحدود،
# والطلب الثاني يحمّل الملف نفسه. المبسطة أصغر بكثير، وكافية لخريطة العالم.
BOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/{country}/ADM1/"


class BoundaryScraper:

    # يحمّل حدود محافظات دولة وحدة، ويحفظها في المكان اللي يعطيه المستودع.
    # لو الملف موجود من قبل، يرجعه على طول بدون إنترنت.
    def fetch_regions(self, country: str, target: Path) -> Path:
        target = Path(target)
        if target.exists() and target.stat().st_size > 0:
            return target
        info = requests.get(BOUNDARIES_API.format(country=country),
                            headers=HEADERS, timeout=60)
        info.raise_for_status()
        response = requests.get(info.json()["simplifiedGeometryGeoJSON"],
                                headers=HEADERS, timeout=120)
        response.raise_for_status()
        # نتأكد إن الملف سليم قبل ما نحفظه. لو تالف، هذا السطر يطلق خطأ.
        response.json()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".part")
        temporary.write_bytes(response.content)
        temporary.replace(target)
        time.sleep(1.5)
        return target
