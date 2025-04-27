from typing import TypedDict, Literal


class Storage(TypedDict):
    backend: Literal["sql"] | Literal["json"]
    sql: dict[Literal["database_file"], str]
    json: dict[Literal["file_path"], str]


class Config(TypedDict):
    storage: Storage
