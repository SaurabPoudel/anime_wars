
import random

from app.schemas import CharacterResponse


def simulate_battle(
    fighter1: CharacterResponse,
    fighter2: CharacterResponse,
    seed: int | None = None,
) -> dict:
    rng = random.Random(seed)

    hp = {
        fighter1.id: fighter1.hp,
        fighter2.id: fighter2.hp,
    }

    fighters = [fighter1, fighter2]

    if fighter2.speed > fighter1.speed:
        fighters.reverse()
    elif fighter1.speed == fighter2.speed:
        rng.shuffle(fighters)

    battle_log = []
    turn = 0
    max_turns = 100

    while all(hp[fighter.id] > 0 for fighter in fighters):
        if turn >= max_turns:
            break

        attacker = fighters[turn % 2]
        defender = fighters[(turn + 1) % 2]

        special_move = (
            bool(attacker.abilities)
            and rng.random() < 0.35
        )

        move_name = "Basic Attack"
        multiplier = 1.0

        if special_move:
            move_name = rng.choice(attacker.abilities)
            multiplier = 1.35

        critical = rng.random() < 0.10
        critical_multiplier = 1.5 if critical else 1.0

        damage = max(
            1,
            round(
                attacker.attack
                * multiplier
                * critical_multiplier
                / (1 + defender.defense / 100)
            ),
        )

        hp[defender.id] = max(0, hp[defender.id] - damage)

        battle_log.append(
            {
                "turn": turn + 1,
                "attacker": attacker.name,
                "defender": defender.name,
                "move": move_name,
                "damage": damage,
                "critical": critical,
                "remaining_hp": hp[defender.id],
            }
        )

        turn += 1

    if hp[fighter1.id] > hp[fighter2.id]:
        winner = fighter1
    elif hp[fighter2.id] > hp[fighter1.id]:
        winner = fighter2
    else:
        winner = None

    return {
        "seed": seed,
        "winner": winner.name if winner else None,
        "winner_id": winner.id if winner else None,
        "fighters": [
            {
                "id": fighter1.id,
                "name": fighter1.name,
                "starting_hp": fighter1.hp,
                "remaining_hp": hp[fighter1.id],
            },
            {
                "id": fighter2.id,
                "name": fighter2.name,
                "starting_hp": fighter2.hp,
                "remaining_hp": hp[fighter2.id],
            },
        ],
        "turns": len(battle_log),
        "battle_log": battle_log,
    }
