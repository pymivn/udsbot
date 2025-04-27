from pydantic import BaseModel
from typing import Literal, Union


class SqlStorage(BaseModel):
    backend: Literal["sql"]
    database_file: str


class JsonStorage(BaseModel):
    backend: Literal["json"]
    file_path: str


class Config(BaseModel):
    storage: Union[SqlStorage, JsonStorage]
