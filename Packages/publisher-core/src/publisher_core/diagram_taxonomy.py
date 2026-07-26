"""Versioned medical-diagram taxonomy shared by Intent and Visual Grammar."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from publisher_core.models import (
    DiagramIntentType,
    FrozenModel,
    ProfileStatus,
    SemanticVersion,
    ShortText,
    StableKey,
)


class TaxonomyNodeStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class DiagramTaxonomyNode(FrozenModel):
    """One stable node in an adjacency-list taxonomy."""

    taxonomy_id: StableKey
    parent_taxonomy_id: StableKey | None = None
    canonical_name: ShortText
    aliases: tuple[ShortText, ...] = Field(default=(), max_length=50)
    intent_type: DiagramIntentType | None = None
    status: TaxonomyNodeStatus = TaxonomyNodeStatus.ACTIVE
    replacement_taxonomy_id: StableKey | None = None

    @model_validator(mode="after")
    def keep_lifecycle_consistent(self) -> Self:
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("taxonomy node aliases must be unique")
        if self.parent_taxonomy_id == self.taxonomy_id:
            raise ValueError("taxonomy node cannot be its own parent")
        if self.replacement_taxonomy_id == self.taxonomy_id:
            raise ValueError("taxonomy node cannot replace itself")
        if self.status == TaxonomyNodeStatus.ACTIVE and self.replacement_taxonomy_id is not None:
            raise ValueError("active taxonomy node cannot have a replacement")
        return self


class DiagramTaxonomyProfile(FrozenModel):
    """Independent, versioned classification dictionary for medical diagrams."""

    schema_version: Literal["1.0"]
    profile_id: StableKey
    version: SemanticVersion
    name: ShortText
    status: ProfileStatus
    nodes: tuple[DiagramTaxonomyNode, ...] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_hierarchy(self) -> Self:
        node_ids = tuple(item.taxonomy_id for item in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("taxonomy_id values must be unique")
        by_id = {item.taxonomy_id: item for item in self.nodes}
        for node in self.nodes:
            if node.parent_taxonomy_id is None:
                if node.intent_type is None:
                    raise ValueError("taxonomy root requires intent_type")
            elif node.parent_taxonomy_id not in by_id:
                raise ValueError(f"taxonomy node references unknown parent: {node.taxonomy_id}")
            elif node.intent_type is not None:
                raise ValueError("only taxonomy roots can declare intent_type")
            if (
                node.replacement_taxonomy_id is not None
                and node.replacement_taxonomy_id not in by_id
            ):
                raise ValueError("taxonomy replacement references an unknown node")
        for node_id in node_ids:
            self._lineage_ids(node_id, by_id)
        return self

    def node(self, taxonomy_id: str) -> DiagramTaxonomyNode:
        node = next((item for item in self.nodes if item.taxonomy_id == taxonomy_id), None)
        if node is None:
            raise KeyError(f"taxonomy node is not registered: {taxonomy_id}")
        return node

    def lineage_ids(self, taxonomy_id: str) -> tuple[str, ...]:
        return self._lineage_ids(
            taxonomy_id,
            {item.taxonomy_id: item for item in self.nodes},
        )

    def root_intent_type(self, taxonomy_id: str) -> DiagramIntentType:
        root = self.node(self.lineage_ids(taxonomy_id)[0])
        if root.intent_type is None:  # protected by model validation
            raise ValueError("taxonomy root does not define intent_type")
        return root.intent_type

    def is_ancestor_or_self(self, ancestor_id: str, descendant_id: str) -> bool:
        return ancestor_id in self.lineage_ids(descendant_id)

    @staticmethod
    def _lineage_ids(
        taxonomy_id: str,
        by_id: dict[str, DiagramTaxonomyNode],
    ) -> tuple[str, ...]:
        if taxonomy_id not in by_id:
            raise KeyError(f"taxonomy node is not registered: {taxonomy_id}")
        lineage: list[str] = []
        visited: set[str] = set()
        current: str | None = taxonomy_id
        while current is not None:
            if current in visited:
                raise ValueError(f"taxonomy hierarchy contains a cycle: {taxonomy_id}")
            visited.add(current)
            lineage.append(current)
            current = by_id[current].parent_taxonomy_id
        return tuple(reversed(lineage))
