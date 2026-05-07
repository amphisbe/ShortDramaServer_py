from app.models.drama import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    EpisodeComment,
    EpisodeShare,
    User,
    UserDramaFavorite,
    UserEpisodeLike,
    UserEpisodeProgress,
    UserFollow,
)

ALL_MODELS = [
    User,
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    UserFollow,
    UserEpisodeLike,
    UserDramaFavorite,
    UserEpisodeProgress,
    EpisodeComment,
    EpisodeShare,
]

__all__ = [
    "ALL_MODELS",
    "User",
    "Drama",
    "DramaEpisode",
    "DramaEpisodeStat",
    "UserFollow",
    "UserEpisodeLike",
    "UserDramaFavorite",
    "UserEpisodeProgress",
    "EpisodeComment",
    "EpisodeShare",
]
