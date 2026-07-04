import os


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_pg_dsn() -> str:
    return (
        f"postgresql://{_require('POSTGRES_USER')}:"
        f"{_require('POSTGRES_PASSWORD')}@"
        f"{_require('POSTGRES_HOST')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{_require('POSTGRES_DB')}"
    )
