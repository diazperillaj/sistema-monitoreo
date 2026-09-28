from pydantic import BaseModel


class Salud(BaseModel):
    ok: bool
    version: str
