
import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, SessionLocal, engine, get_db
from app.models import Character
from app.schemas import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
)


BUILT_IN_CHARACTERS = [
    {
        "name": "Naruto Uzumaki",
        "anime": "Naruto",
        "hp": 100,
        "attack": 85,
        "defense": 60,
        "speed": 90,
        "abilities": ["Rasengan", "Shadow Clone"],
    },
    {
        "name": "Monkey D. Luffy",
        "anime": "One Piece",
        "hp": 120,
        "attack": 90,
        "defense": 65,
        "speed": 85,
        "abilities": ["Gum-Gum Pistol", "Gear Second"],
    },
    {
        "name": "Son Goku",
        "anime": "Dragon Ball",
        "hp": 110,
        "attack": 100,
        "defense": 70,
        "speed": 95,
        "abilities": ["Kamehameha", "Instant Transmission"],
    },
]


def to_response(character: Character) -> CharacterResponse:
    return CharacterResponse(
        id=character.id,
        name=character.name,
        anime=character.anime,
        hp=character.hp,
        attack=character.attack,
        defense=character.defense,
        speed=character.speed,
        abilities=json.loads(character.abilities),
        source=character.source,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        result = await db.execute(select(Character.id).limit(1))
        has_characters = result.scalar_one_or_none() is not None

        if not has_characters:
            for data in BUILT_IN_CHARACTERS:
                db.add(
                    Character(
                        **{
                            **data,
                            "abilities": json.dumps(data["abilities"]),
                            "source": "system",
                        }
                    )
                )

            await db.commit()

    yield

    await engine.dispose()


app = FastAPI(
    title="Anime Wars",
    description="An anime character battle simulator",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/")
async def home():
    return {
        "message": "Welcome to Anime Wars!",
        "status": "online",
    }


@app.post(
    "/characters",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_character(
    character: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    data = character.model_dump()
    data["abilities"] = json.dumps(data["abilities"])

    new_character = Character(
        **data,
        source="user",
    )

    db.add(new_character)
    await db.commit()
    await db.refresh(new_character)

    return to_response(new_character)


@app.get(
    "/characters",
    response_model=list[CharacterResponse],
)
async def list_characters(
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Character)

    if source is not None:
        if source not in {"system", "user"}:
            raise HTTPException(
                status_code=400,
                detail="Source must be 'system' or 'user'",
            )

        query = query.where(Character.source == source)

    result = await db.execute(query)
    characters = result.scalars().all()

    return [to_response(character) for character in characters]


@app.get(
    "/characters/{character_id}",
    response_model=CharacterResponse,
)
async def get_character(
    character_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()

    if character is None:
        raise HTTPException(
            status_code=404,
            detail="Character not found",
        )

    return to_response(character)


@app.patch(
    "/characters/{character_id}",
    response_model=CharacterResponse,
)
async def update_character(
    character_id: int,
    updates: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()

    if character is None:
        raise HTTPException(
            status_code=404,
            detail="Character not found",
        )

    if character.source == "system":
        raise HTTPException(
            status_code=403,
            detail="Built-in characters cannot be edited",
        )

    update_data = updates.model_dump(exclude_unset=True)

    if any(value is None for value in update_data.values()):
        raise HTTPException(
            status_code=422,
            detail="Fields cannot be set to null",
        )

    for field, value in update_data.items():
        if field == "abilities":
            value = json.dumps(value)

        setattr(character, field, value)

    await db.commit()
    await db.refresh(character)

    return to_response(character)


@app.delete(
    "/characters/{character_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_character(
    character_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()

    if character is None:
        raise HTTPException(
            status_code=404,
            detail="Character not found",
        )

    if character.source == "system":
        raise HTTPException(
            status_code=403,
            detail="Built-in characters cannot be deleted",
        )

    await db.delete(character)
    await db.commit()

    return None
