from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class Character(Base):
    __tablename__ =  "characters"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key = True,
        index = True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable = False,
    )

    anime: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    hp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    attack: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    defense: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    speed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    abilities: Mapped[str] = mapped_column(
        String,
        default="",
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="user",
    )


class Battle(Base):
    __tablename__ = "battles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    fighter1_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    fighter2_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    winner_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    seed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    turns: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    result_json: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
