
import json
from contextlib import asynccontextmanager
import random


from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, SessionLocal, engine, get_db
from app.models import Battle, Character, Team, TeamMember, TeamBattle, Tournament
from app.schemas import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    TeamCreate,
    TeamMemberCreate,
    TeamBattleRequest,
    TournamentCreate
)
from app.tournament_engine import simulate_tournament


from app.battle_engine import simulate_battle
from app.schemas import BattleRequest



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


@app.get(
    "/characters",
    response_model=list[CharacterResponse],
)
async def list_characters(
    search: str | None = None,
    anime: str | None = None,
    min_hp: int | None = None,
    source: str | None = None,
    sort_by: str = "id",
    order: str = "asc",
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Character)

    # Search character names, anime names, and abilities
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Character.name.ilike(term),
                Character.anime.ilike(term),
                Character.abilities.ilike(term),
            )
        )

    # Filter by anime universe
    if anime:
        query = query.where(
            Character.anime.ilike(f"%{anime.strip()}%")
        )

    # Filter by minimum health
    if min_hp is not None:
        query = query.where(Character.hp >= min_hp)

    # Filter built-in or user-created characters
    if source is not None:
        if source not in {"system", "user"}:
            raise HTTPException(
                status_code=400,
                detail="Source must be 'system' or 'user'",
            )

        query = query.where(Character.source == source)

    # Allow sorting only by approved fields
    sortable_fields = {
        "id": Character.id,
        "name": Character.name,
        "hp": Character.hp,
        "attack": Character.attack,
        "defense": Character.defense,
        "speed": Character.speed,
    }

    if sort_by not in sortable_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by. Choose from: {', '.join(sortable_fields)}",
        )

    if order not in {"asc", "desc"}:
        raise HTTPException(
            status_code=400,
            detail="order must be 'asc' or 'desc'",
        )

    sort_column = sortable_fields[sort_by]

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination validation
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="offset cannot be negative",
        )

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    characters = result.scalars().all()

    return [to_response(character) for character in characters]


@app.post("/battles", status_code=201)
async def create_battle(
    request: BattleRequest,
    db: AsyncSession = Depends(get_db),
):
    if request.fighter1_id == request.fighter2_id:
        raise HTTPException(
            status_code=400,
            detail="A character cannot battle itself",
        )

    result = await db.execute(
        select(Character).where(
            Character.id.in_(
                [request.fighter1_id, request.fighter2_id]
            )
        )
    )

    characters = {
        character.id: character
        for character in result.scalars().all()
    }

    fighter1 = characters.get(request.fighter1_id)
    fighter2 = characters.get(request.fighter2_id)

    if fighter1 is None or fighter2 is None:
        raise HTTPException(
            status_code=404,
            detail="One or both characters were not found",
        )

    battle_result = simulate_battle(
        to_response(fighter1),
        to_response(fighter2),
        seed=request.seed,
    )

    battle = Battle(
        fighter1_id=fighter1.id,
        fighter2_id=fighter2.id,
        winner_id=battle_result["winner_id"],
        seed=request.seed,
        turns=battle_result["turns"],
        result_json=json.dumps(battle_result),
    )

    db.add(battle)
    await db.commit()
    await db.refresh(battle)

    return {
        "battle_id": battle.id,
        **battle_result,
    }



@app.get("/battles")
async def list_battles(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="offset cannot be negative",
        )

    result = await db.execute(
        select(Battle)
        .order_by(Battle.id.desc())
        .offset(offset)
        .limit(limit)
    )

    battles = result.scalars().all()

    return [
        {
            "battle_id": battle.id,
            "fighter1_id": battle.fighter1_id,
            "fighter2_id": battle.fighter2_id,
            "winner_id": battle.winner_id,
            "seed": battle.seed,
            "turns": battle.turns,
        }
        for battle in battles
    ]


@app.get("/battles/{battle_id}")
async def get_battle(
    battle_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Battle).where(Battle.id == battle_id)
    )

    battle = result.scalar_one_or_none()

    if battle is None:
        raise HTTPException(
            status_code=404,
            detail="Battle not found",
        )

    return {
        "battle_id": battle.id,
        **json.loads(battle.result_json),
    }


@app.get("/characters/{character_id}/stats")
async def get_character_stats(
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

    result = await db.execute(
        select(Battle).where(
            (Battle.fighter1_id == character_id)
            | (Battle.fighter2_id == character_id)
        )
    )
    battles = result.scalars().all()

    total_battles = len(battles)
    wins = sum(
        battle.winner_id == character_id
        for battle in battles
    )
    losses = sum(
        battle.winner_id is not None
        and battle.winner_id != character_id
        for battle in battles
    )
    draws = total_battles - wins - losses

    win_rate = (
        round(wins / total_battles * 100, 2)
        if total_battles
        else 0.0
    )

    return {
        "character_id": character.id,
        "name": character.name,
        "anime": character.anime,
        "total_battles": total_battles,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
    }



@app.get("/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    result = await db.execute(
        select(Character).order_by(Character.id.asc())
    )
    characters = result.scalars().all()

    result = await db.execute(select(Battle))
    battles = result.scalars().all()

    rankings = []

    for character in characters:
        character_battles = [
            battle
            for battle in battles
            if (
                battle.fighter1_id == character.id
                or battle.fighter2_id == character.id
            )
        ]

        total = len(character_battles)
        wins = sum(
            battle.winner_id == character.id
            for battle in character_battles
        )

        losses = sum(
            battle.winner_id is not None
            and battle.winner_id != character.id
            for battle in character_battles
        )

        draws = total - wins - losses

        win_rate = (
            round(wins / total * 100, 2)
            if total
            else 0.0
        )

        rankings.append(
            {
                "character_id": character.id,
                "name": character.name,
                "anime": character.anime,
                "total_battles": total,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": win_rate,
            }
        )

    rankings.sort(
        key=lambda item: (
            item["wins"],
            item["win_rate"],
            item["total_battles"],
        ),
        reverse=True,
    )

    for rank, character in enumerate(rankings, start=1):
        character["rank"] = rank

    return rankings[:limit]



@app.post("/teams", status_code=201)
async def create_team(
    request: TeamCreate,
    db: AsyncSession = Depends(get_db),
):
    name = request.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Team name cannot be blank",
        )

    result = await db.execute(
        select(Team).where(Team.name.ilike(name))
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="A team with this name already exists",
        )

    team = Team(name=name)
    db.add(team)

    await db.commit()
    await db.refresh(team)

    return {
        "id": team.id,
        "name": team.name,
        "members": [],
    }


@app.post("/teams/{team_id}/members", status_code=201)
async def add_team_member(
    team_id: int,
    request: TeamMemberCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found",
        )

    result = await db.execute(
        select(Character).where(
            Character.id == request.character_id
        )
    )
    character = result.scalar_one_or_none()

    if character is None:
        raise HTTPException(
            status_code=404,
            detail="Character not found",
        )

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.character_id == request.character_id,
        )
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Character is already in this team",
        )

    member = TeamMember(
        team_id=team_id,
        character_id=request.character_id,
    )

    db.add(member)
    await db.commit()

    return {
        "message": f"{character.name} added to {team.name}",
        "team_id": team_id,
        "character_id": character.id,
    }


@app.get("/teams/{team_id}")
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Team not found",
        )

    result = await db.execute(
        select(Character)
        .join(
            TeamMember,
            TeamMember.character_id == Character.id,
        )
        .where(TeamMember.team_id == team_id)
        .order_by(Character.id)
    )

    characters = result.scalars().all()

    return {
        "id": team.id,
        "name": team.name,
        "members": [
            to_response(character).model_dump()
            for character in characters
        ],
        "member_count": len(characters),
    }



@app.delete(
    "/teams/{team_id}/members/{character_id}",
    status_code=204,
)
async def remove_team_member(
    team_id: int,
    character_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.character_id == character_id,
        )
    )

    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=404,
            detail="Team membership not found",
        )

    await db.delete(member)
    await db.commit()

    return None



@app.get("/teams")
async def list_teams(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Team).order_by(Team.id)
    )
    teams = result.scalars().all()

    output = []

    for team in teams:
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team.id
            )
        )
        members = result.scalars().all()

        output.append(
            {
                "id": team.id,
                "name": team.name,
                "member_count": len(members),
            }
        )

    return output


@app.post("/team-battles", status_code=201)
async def create_team_battle(
    request: TeamBattleRequest,
    db: AsyncSession = Depends(get_db),
):
    if request.team1_id == request.team2_id:
        raise HTTPException(
            status_code=400,
            detail="A team cannot battle itself",
        )

    # Find both teams.
    result = await db.execute(
        select(Team).where(
            Team.id.in_([request.team1_id, request.team2_id])
        )
    )
    teams = {team.id: team for team in result.scalars().all()}

    team1 = teams.get(request.team1_id)
    team2 = teams.get(request.team2_id)

    if team1 is None or team2 is None:
        raise HTTPException(
            status_code=404,
            detail="One or both teams were not found",
        )

    # Fetch each team's characters in a stable order.
    async def get_team_characters(team_id: int):
        result = await db.execute(
            select(Character)
            .join(
                TeamMember,
                TeamMember.character_id == Character.id,
            )
            .where(TeamMember.team_id == team_id)
            .order_by(Character.id)
        )
        return [
            to_response(character)
            for character in result.scalars().all()
        ]

    fighters1 = await get_team_characters(team1.id)
    fighters2 = await get_team_characters(team2.id)

    if not fighters1 or not fighters2:
        raise HTTPException(
            status_code=400,
            detail="Both teams must have at least one character",
        )

    if len(fighters1) != len(fighters2):
        raise HTTPException(
            status_code=400,
            detail="Both teams must have the same number of characters",
        )

    # Generate a seed if the caller did not supply one.
    battle_seed = (
        request.seed
        if request.seed is not None
        else random.SystemRandom().randrange(1, 2**31 - 1)
    )

    individual_battles = []
    team1_wins = 0
    team2_wins = 0
    total_turns = 0

    # Pair characters by their roster order.
    for index, (fighter1, fighter2) in enumerate(
        zip(fighters1, fighters2)
    ):
        match_seed = battle_seed + index

        result = simulate_battle(
            fighter1,
            fighter2,
            seed=match_seed,
        )

        individual_battles.append(result)
        total_turns += result["turns"]

        if result["winner_id"] == fighter1.id:
            team1_wins += 1
        elif result["winner_id"] == fighter2.id:
            team2_wins += 1

    if team1_wins > team2_wins:
        winner_team_id = team1.id
        winner_name = team1.name
    elif team2_wins > team1_wins:
        winner_team_id = team2.id
        winner_name = team2.name
    else:
        winner_team_id = None
        winner_name = None

    battle_result = {
        "seed": battle_seed,
        "team1": {
            "id": team1.id,
            "name": team1.name,
            "wins": team1_wins,
        },
        "team2": {
            "id": team2.id,
            "name": team2.name,
            "wins": team2_wins,
        },
        "winner_team_id": winner_team_id,
        "winner": winner_name,
        "individual_battles": individual_battles,
        "total_turns": total_turns,
    }

    saved_battle = TeamBattle(
        team1_id=team1.id,
        team2_id=team2.id,
        winner_team_id=winner_team_id,
        seed=battle_seed,
        total_turns=total_turns,
        result_json=json.dumps(battle_result),
    )

    db.add(saved_battle)
    await db.commit()
    await db.refresh(saved_battle)

    return {
        "team_battle_id": saved_battle.id,
        **battle_result,
    }



@app.get("/team-battles")
async def list_team_battles(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="offset cannot be negative",
        )

    result = await db.execute(
        select(TeamBattle)
        .order_by(TeamBattle.id.desc())
        .offset(offset)
        .limit(limit)
    )

    battles = result.scalars().all()

    return [
        {
            "team_battle_id": battle.id,
            "team1_id": battle.team1_id,
            "team2_id": battle.team2_id,
            "winner_team_id": battle.winner_team_id,
            "seed": battle.seed,
            "total_turns": battle.total_turns,
        }
        for battle in battles
    ]


@app.get("/team-battles/{battle_id}")
async def get_team_battle(
    battle_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TeamBattle).where(TeamBattle.id == battle_id)
    )

    battle = result.scalar_one_or_none()

    if battle is None:
        raise HTTPException(
            status_code=404,
            detail="Team battle not found",
        )

    return {
        "team_battle_id": battle.id,
        **json.loads(battle.result_json),
    }


@app.post("/tournaments", status_code=201)
async def create_tournament(
    request: TournamentCreate,
    db: AsyncSession = Depends(get_db),
):
    name = request.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Tournament name cannot be blank",
        )

    if request.character_ids is not None:
        if len(request.character_ids) != 64:
            raise HTTPException(
                status_code=400,
                detail="Exactly 64 character IDs are required",
            )

        if len(set(request.character_ids)) != 64:
            raise HTTPException(
                status_code=400,
                detail="Character IDs must be unique",
            )

        result = await db.execute(
            select(Character).where(
                Character.id.in_(request.character_ids)
            )
        )
        found = {
            character.id: character
            for character in result.scalars().all()
        }

        if len(found) != 64:
            raise HTTPException(
                status_code=404,
                detail="One or more characters were not found",
            )
        characters = [
            found[character_id]
            for character_id in request.character_ids
        ]
    else:
        result = await db.execute(
            select(Character)
            .order_by(Character.id)
            .limit(64)
        )
        characters = result.scalars().all()

        if len(characters) != 64:
            raise HTTPException(
                status_code=400,
                detail="At least 64 characters are required",
            )

    tournament_seed = (
        request.seed
        if request.seed is not None
        else random.SystemRandom().randrange(1, 2**31 - 1)
    )

    tournament_result = simulate_tournament(
        [to_response(character) for character in characters],
        seed=tournament_seed,
    )

    tournament = Tournament(
        name=name,
        seed=tournament_seed,
        champion_id=tournament_result["champion"]["id"],
        result_json=json.dumps(tournament_result),
    )

    db.add(tournament)
    await db.commit()
    await db.refresh(tournament)

    return {
        "tournament_id": tournament.id,
        "name": tournament.name,
        **tournament_result,
    }



@app.get("/tournaments")
async def list_tournaments(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="offset cannot be negative",
        )

    result = await db.execute(
        select(Tournament)
        .order_by(Tournament.id.desc())
        .offset(offset)
        .limit(limit)
    )

    tournaments = result.scalars().all()

    return [
        {
            "id": tournament.id,
            "name": tournament.name,
            "seed": tournament.seed,
            "champion_id": tournament.champion_id,
        }
        for tournament in tournaments
    ]


@app.get("/tournaments/{tournament_id}")
async def get_tournament(
    tournament_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Tournament).where(
            Tournament.id == tournament_id
        )
    )
    tournament = result.scalar_one_or_none()

    if tournament is None:
        raise HTTPException(
            status_code=404,
            detail="Tournament not found",
        )

    return {
        "tournament_id": tournament.id,
        "name": tournament.name,
        **json.loads(tournament.result_json),
    }
