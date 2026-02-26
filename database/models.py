from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    Boolean,
    ForeignKey,
    TIMESTAMP,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


# -------------------
# Franchisee
# -------------------

class Franchisee(Base):
    __tablename__ = "franchisee"
    __table_args__ = {"schema": "special"}

    uuid: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    group_uuid: Mapped[Optional[str]] = mapped_column(String(200))
    country: Mapped[Optional[str]] = mapped_column(String(10))


# -------------------
# Units
# -------------------

class Unit(Base):
    __tablename__ = "units"
    __table_args__ = {"schema": "special"}

    uuid: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    timezone: Mapped[Optional[int]] = mapped_column(Integer)
    latitude: Mapped[Optional[str]] = mapped_column(String(50))
    longitude: Mapped[Optional[str]] = mapped_column(String(50))
    country: Mapped[Optional[str]] = mapped_column(String(10))

    subscribes: Mapped[List["Subscribe"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
    )


# -------------------
# Users
# -------------------

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "special"}

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    username: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[Optional[str]] = mapped_column(String)
    platform: Mapped[Optional[str]] = mapped_column(String(20))

    accounts: Mapped[List["UserAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    settings: Mapped[List["Settings"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# -------------------
# Accounts
# -------------------

class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "special"}

    id: Mapped[int] = mapped_column(primary_key=True)
    sub: Mapped[Optional[str]] = mapped_column(String(100))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    properties: Mapped[Optional[str]] = mapped_column(String(100))
    active: Mapped[Optional[bool]] = mapped_column(Boolean)
    email: Mapped[Optional[str]] = mapped_column(String(150))

    users: Mapped[List["UserAccount"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    tokens: Mapped[List["Token"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


# -------------------
# UserAccount (m2m)
# -------------------

class UserAccount(Base):
    __tablename__ = "user_account"
    __table_args__ = {"schema": "special"}

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("special.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("special.accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="accounts")
    account: Mapped["Account"] = relationship(back_populates="users")


# -------------------
# Applications
# -------------------

class Application(Base):
    __tablename__ = "applications"
    __table_args__ = {"schema": "special"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    client_id: Mapped[Optional[str]] = mapped_column(String(200))
    secret: Mapped[Optional[str]] = mapped_column(String(200))
    redirect_io: Mapped[Optional[str]] = mapped_column(String(200))
    redirect_com: Mapped[Optional[str]] = mapped_column(String(200))
    challenge: Mapped[Optional[str]] = mapped_column(String(200))
    verifier: Mapped[Optional[str]] = mapped_column(String(200))
    scope: Mapped[Optional[str]] = mapped_column(String)

    tokens: Mapped[List["Token"]] = relationship(
        back_populates="application"
    )


# -------------------
# Tokens
# -------------------

class Token(Base):
    __tablename__ = "tokens"
    __table_args__ = {"schema": "special"}

    id: Mapped[int] = mapped_column(primary_key=True)
    access: Mapped[Optional[str]] = mapped_column(String)
    refresh: Mapped[Optional[str]] = mapped_column(String)
    last_update: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)

    account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("special.accounts.id")
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("special.applications.id")
    )

    account: Mapped[Optional["Account"]] = relationship(back_populates="tokens")
    application: Mapped[Optional["Application"]] = relationship(back_populates="tokens")

    subscribes: Mapped[List["Subscribe"]] = relationship(
        back_populates="token",
        cascade="all, delete-orphan",
    )


# -------------------
# Subscribes (composite PK)
# -------------------

class Subscribe(Base):
    __tablename__ = "subscribes"
    __table_args__ = (
        PrimaryKeyConstraint("uuid", "token_id"),
        {"schema": "special"},
    )

    id: Mapped[int] = mapped_column(Integer, autoincrement=True)

    uuid: Mapped[str] = mapped_column(
        ForeignKey("special.units.uuid", ondelete="CASCADE"),
        nullable=False,
    )
    token_id: Mapped[int] = mapped_column(
        ForeignKey("special.tokens.id", ondelete="CASCADE"),
        nullable=False,
    )

    expires: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    alias: Mapped[Optional[str]] = mapped_column(String(50))

    unit: Mapped["Unit"] = relationship(back_populates="subscribes")
    token: Mapped["Token"] = relationship(back_populates="subscribes")


# -------------------
# Settings
# -------------------

class Settings(Base):
    __tablename__ = "settings"
    __table_args__ = {"schema": "special"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("special.users.id"),
        nullable=False
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    user = relationship("User", back_populates="settings")
