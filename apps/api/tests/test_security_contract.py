from pathlib import Path


def test_no_header_trust_contract():
    source=(Path(__file__).resolve().parents[1]/'app'/'main.py').read_text()
    assert '/api/v1/auth/login' in source
    assert '/api/v1/auth/me' in source
    assert '/api/v1/platform/lodges' in source
    assert 'X-Lodge-Id' not in source
    assert 'X-Platform-Role' not in source
