from typing import List
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    pass


class Vacancy(Base):
    __tablename__ = "vacancy"

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(256))
    carrier_position: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(String())
    internal_id: Mapped[int] = mapped_column(unique=True)

    skills: Mapped[List["Skill"]] = relationship(
        back_populates="vacancy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Vacancy(id={self.id!r}, title={self.company!r}, carrier_position={self.carrier_position!r}, internal_id={self.internal_id!r})"


class Skill(Base):
    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancy.id"))

    vacancy: Mapped["Vacancy"] = relationship(back_populates="skills")

    def __repr__(self) -> str:
        return f"Skill(id={self.id!r}, name={self.name!r})"
