"""SQLAlchemy ORM models for the compatibility tracker."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


class Software(Base):
    """A software application tracked across phones."""

    __tablename__ = "software"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    phone_entries = relationship(
        "PhoneSoftware", back_populates="software", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Software(id={self.id}, name='{self.name}')>"


class Phone(Base):
    """A mobile-phone model with OS and release year."""

    __tablename__ = "phones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    os = Column(String, nullable=False)
    released = Column(String, nullable=False)

    software_entries = relationship(
        "PhoneSoftware", back_populates="phone", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", "os", name="uq_phone_name_os"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Phone(id={self.id}, name='{self.name}', os='{self.os}')>"


class PhoneSoftware(Base):
    """Association table linking a phone to a software version."""

    __tablename__ = "phone_software"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_id = Column(Integer, ForeignKey("phones.id"), nullable=False)
    software_id = Column(Integer, ForeignKey("software.id"), nullable=False)
    version = Column(String, nullable=True)

    phone = relationship("Phone", back_populates="software_entries")
    software = relationship("Software", back_populates="phone_entries")

    __table_args__ = (
        UniqueConstraint("phone_id", "software_id", name="uq_phone_software"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PhoneSoftware(phone_id={self.phone_id}, "
            f"software_id={self.software_id}, version='{self.version}')>"
        )
