from pydantic import BaseModel, Field

class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    anime: str = Field(min_length=1, max_length=100)

    hp: int = Field(ge=1, le=1000)
    attack: int = Field(ge=1, le=100)
    defense: int = Field(ge = 0, le=300)
    speed: int = Field(ge=1, le=100)

    abilities: list[str] = Field(default_factory=list)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    anime: str | None = Field(default=None, min_length=1, max_length=100)

    hp: int | None = Field(default=None, ge=1, le=1000)
    attack: int | None= Field(default=None, ge=1, le=100)
    defense: int | None = Field(default=None, ge = 0, le=300)
    speed: int | None = Field(default=None, ge=1, le=100)

    abilities: list[str] | None = None


class CharacterResponse(CharacterCreate):
    id: int
    source:  str