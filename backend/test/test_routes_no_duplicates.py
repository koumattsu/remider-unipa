def test_no_duplicate_routes():
    from app.main import app

    seen = {}
    dups = []

    for r in app.routes:
        path = getattr(r, "path", None)
        methods = tuple(sorted(getattr(r, "methods", []) or []))
        if not path or not methods:
            continue
        key = (path, methods)
        if key in seen:
            dups.append((key, seen[key], getattr(r, "endpoint", None)))
        else:
            seen[key] = getattr(r, "endpoint", None)

    assert not dups, f"Duplicate routes found: {dups}"
