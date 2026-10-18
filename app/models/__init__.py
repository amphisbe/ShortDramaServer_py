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

from app.models.tag import Tag, TagTranslation, TagAlias, UserTagWeight, TAG_MODELS

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
] + TAG_MODELS

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
    "Tag",
    "TagTranslation",
    "TagAlias",
    "UserTagWeight",
]
