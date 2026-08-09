from pathlib import Path
TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


def test_path(name: str) -> Path:
    TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TEST_TEMP_ROOT / name
