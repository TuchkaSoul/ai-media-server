from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


metadata = MetaData(schema="mediahub")


class Base(DeclarativeBase):
    metadata = metadata
