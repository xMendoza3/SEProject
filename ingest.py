"""
ملف الاستيراد: يبني قاعدة البيانات من بيانات الكتاب، بأمر واحد.

شغّله مرة وحدة، أو كل ما تحسّن المحلل أو المستخرج.
المفضلة ما تنمسح.
"""

import time

from src.controllers import ImportController

if __name__ == "__main__":
    start = time.perf_counter()
    stats = ImportController().run()
    print(f"done in {time.perf_counter() - start:.1f}s:", stats)
