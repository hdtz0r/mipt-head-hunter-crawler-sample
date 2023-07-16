from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.vacancy import Base

engine = create_engine("sqlite:///vacancies.db")


def initialize():
    try:
        for table in reversed(Base.metadata.sorted_tables):
            table.drop(engine)
    except:
        pass
    Base.metadata.create_all(engine)


def save_all(models: List[Base]):
    with Session(engine) as session:
        try:
            session.add_all(models)
            session.commit()
        except Exception as ex:
            session.rollback()
            raise ex
