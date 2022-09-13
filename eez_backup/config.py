from typing import Dict, Optional, Any, Mapping

from pydantic import Field

from eez_backup.common import BaseModel
from eez_backup.profile import InProfile, ProfileGenerator
from eez_backup.repository import InRepository, Repository, RepositoryGenerator


class Config(BaseModel):
    repositories: Dict[str, InRepository] = Field(default_factory=dict)
    globals_: Optional[InProfile] = Field(alias="globals")
    profiles: Dict[str, InProfile] = Field(default_factory=dict)

    def compile_repositories(
        self, defaults: Mapping[str, Any] | None = None
    ) -> RepositoryGenerator:
        defaults = defaults | {}
        for tag, repository in self.repositories.items():
            yield Repository(tag=tag, **(defaults | repository.dict()))

    def compile_profiles(
        self,
        repository_defaults: Mapping[str, Any] | None = None,
        profile_defaults: Mapping[str, Any] | None = None,
    ) -> ProfileGenerator:
        repositories = {r.tag: r for r in self.compile_repositories(repository_defaults)}
        default_profile = InProfile(**profile_defaults) if profile_defaults else None

        match (default_profile, self.globals_):
            case (d, None):
                default_profile = d
            case (None, g):
                default_profile = g
            case (d, g):
                default_profile = InProfile.merge(d, g)

        for tag, in_profile in self.profiles.items():
            yield from in_profile.generate_profiles(repositories, default_profile, tag=tag)
