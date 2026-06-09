"""テスト用: Settings の必須 API キーを回避する."""
import os

os.environ.setdefault("DRY_RUN", "true")
