# ==============================================================================
# Copyright (C) 2019 - Philip Paquette
#
#  This program is free software: you can redistribute it and/or modify it under
#  the terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any
#  later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
#  details.
#
#  You should have received a copy of the GNU Affero General Public License along
#  with this program.  If not, see <https://www.gnu.org/licenses/>.
# ==============================================================================
"""Agent definition -- metadata for any agent in the system."""


class AgentDef:
    """Immutable descriptor for an agent.

    This is a data-only container. It does NOT contain behavior -- behavior
    lives in BaseAgent subclasses. AgentDef is metadata that can be attached
    to any agent instance for logging, identification, and post-game analysis.

    Attributes:
        creator:       Human-readable name of who created this agent.
        model_id:      Identifier for the underlying model. 'random' for DumbBot,
                       'gpt-4o' / 'claude-sonnet' etc. for future LLM agents.
        instructions:  Freeform string. Empty for DumbBot. System prompt for
                       future LLM agents.
        description:   Short human-readable description of the agent.
        version:       Version string for the agent implementation.
        metadata:      Arbitrary dict for post-game analysis.
    """
    __slots__ = ['creator', 'model_id', 'instructions', 'description', 'version', 'metadata']

    def __init__(self, creator, model_id, instructions='', description='',
                 version='0.1.0', metadata=None):
        self.creator = creator
        self.model_id = model_id
        self.instructions = instructions
        self.description = description
        self.version = version
        self.metadata = metadata if metadata is not None else {}

    def to_dict(self):
        """Serialize to plain dict for JSON logging / post-game analysis."""
        return {slot: getattr(self, slot) for slot in self.__slots__}

    def __repr__(self):
        return (f"AgentDef(creator={self.creator!r}, model_id={self.model_id!r}, "
                f"description={self.description!r})")
