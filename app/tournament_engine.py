
import random

from app.battle_engine import simulate_battle
from app.schemas import CharacterResponse


def simulate_tournament(
    characters: list[CharacterResponse],
    seed: int,
) -> dict:
    if len(characters) != 64:
        raise ValueError("A tournament requires exactly 64 characters")

    rng = random.Random(seed)
    competitors = characters.copy()
    rng.shuffle(competitors)

    rounds = []
    round_number = 1

    while len(competitors) > 1:
        round_results = []
        winners = []

        for index in range(0, len(competitors), 2):
            fighter1 = competitors[index]
            fighter2 = competitors[index + 1]

            battle_seed = seed + round_number * 1000 + index

            result = simulate_battle(
                fighter1,
                fighter2,
                seed=battle_seed,
            )

            if result["winner_id"] is None:
                tie_rng = random.Random(battle_seed + 1)
                winner_id = tie_rng.choice(
                    [fighter1.id, fighter2.id]
                )
                result["winner_id"] = winner_id
                result["winner"] = (
                    fighter1.name
                    if winner_id == fighter1.id
                    else fighter2.name
                )

            winner = (
                fighter1
                if result["winner_id"] == fighter1.id
                else fighter2
            )

            winners.append(winner)

            round_results.append(
                {
                    "fighter1": fighter1.name,
                    "fighter2": fighter2.name,
                    "winner": winner.name,
                    "winner_id": winner.id,
                    "battle": result,
                }
            )

        rounds.append(
            {
                "round": round_number,
                "matches": round_results,
            }
        )

        competitors = winners
        round_number += 1

    champion = competitors[0]

    return {
        "seed": seed,
        "participant_count": len(characters),
        "total_battles": sum(
            len(round_data["matches"])
            for round_data in rounds
        ),
        "champion": {
            "id": champion.id,
            "name": champion.name,
            "anime": champion.anime,
        },
        "rounds": rounds,
    }
