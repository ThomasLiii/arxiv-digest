from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def feed_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()
