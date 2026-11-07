"""
تجهيزات مشتركة لكل الاختبارات.

مكتبة الاختبارات تقرأ هذا الملف تلقائياً.
أي دالة فوقها مزخرف التجهيز، أي اختبار يقدر يطلبها بكتابة اسمها بين قوسيه،
والمكتبة تشغّلها وتعطيه الناتج. وكل اختبار ياخذ نسخة جديدة، فما يأثر اختبار على ثاني.
"""

import pytest

from src.controllers import ExplorerController
from src.database import DatabaseManager
from tests.book import make_book


# قاعدة بيانات في الذاكرة، فيها الكتاب الصغير.
# اللي قبل كلمة التسليم تجهيز، واللي بعدها تنظيف بعد ما يخلص الاختبار.
@pytest.fixture
def db():
    database = DatabaseManager(":memory:")
    database.replace_book(*make_book())
    yield database
    database.close()


# متحكم المستكشف، موصول بقاعدة البيانات اللي فوق بدل الملف الحقيقي.
@pytest.fixture
def controller(db):
    return ExplorerController(db=db)
