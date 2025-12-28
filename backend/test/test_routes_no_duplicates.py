# test/test_routes_no_duplicates.py

def test_no_duplicate_routes():
    """
    契約テスト:
    同一 (path, methods) のルートが複数登録されていないこと。
    監査系APIの意図しない上書き/優先順依存を防ぐ。
    """
    from app.main import app

    seen: dict[tuple[str, tuple[str, ...]], object] = {}
    dups: list[tuple[tuple[str, tuple[str, ...]], object, object]] = []

    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)

        # FastAPI内部のMount等を除外
        if not path or not methods:
            continue

        key = (path, tuple(sorted(methods)))

        endpoint = getattr(r, "endpoint", None)

        if key in seen:
            dups.append((key, seen[key], endpoint))
        else:
            seen[key] = endpoint

    assert not dups, f"Duplicate routes found: {dups}"