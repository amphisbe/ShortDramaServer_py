from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from app.db.database import initialize_database

P = ParamSpec("P")
R = TypeVar("R")


def with_db_connection(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        db = initialize_database()
        with db.connection_context():
            return func(*args, **kwargs)

    wrapper.__peewee_connection_wrapped__ = True
    return wrapper
