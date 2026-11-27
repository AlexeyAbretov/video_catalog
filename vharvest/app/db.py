from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    false,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.config import settings


class Base(DeclarativeBase):
    pass


movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True)

    movies: Mapped[list["Movie"]] = relationship(
        secondary=movie_genres,
        back_populates="genres",
    )


class Actor(Base):
    __tablename__ = "actors"
    __table_args__ = (Index("ix_actors_name", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tmdb_person_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    popularity: Mapped[float | None] = mapped_column(Float)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("share_name", "relative_path", name="uq_movie_file"),
        Index("ix_movies_status", "status"),
        Index("ix_movies_year", "year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_name: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_mtime: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    title_ru: Mapped[str | None] = mapped_column(Text)
    title_en: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    overview_ru: Mapped[str | None] = mapped_column(Text)
    poster_path: Mapped[str | None] = mapped_column(Text)
    rating_tmdb: Mapped[float | None] = mapped_column(Float)
    rating_kp: Mapped[float | None] = mapped_column(Float)
    tmdb_id: Mapped[int | None] = mapped_column(Integer)
    kp_id: Mapped[int | None] = mapped_column(Integer)
    kp_checked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    confidence: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    genres: Mapped[list[Genre]] = relationship(
        secondary=movie_genres,
        back_populates="movies",
    )
    cast_entries: Mapped[list["MovieActor"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )


class MovieActor(Base):
    __tablename__ = "movie_actors"

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    billing_order: Mapped[int] = mapped_column(Integer, nullable=False)
    character_name: Mapped[str | None] = mapped_column(Text)
    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    movie: Mapped[Movie] = relationship(back_populates="cast_entries")
    actor: Mapped[Actor] = relationship()


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
