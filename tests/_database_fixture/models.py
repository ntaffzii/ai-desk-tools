from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"
