from __future__ import annotations

from collections.abc import Callable

from pydantic.main import BaseModel

from octopoes.models import Reference
from octopoes.models.types import OOIType


class ReferenceNode(BaseModel):
    reference: Reference
    children: dict[str, list[ReferenceNode]]

    def filter_children(self, filter_fn: Callable[[ReferenceNode], bool]) -> bool:
        """
        Mutable filter function to evict any children from the tree that do not adhere to the provided callback
        """
        self.children = {
            attr_name: [child for child in children if child.filter_children(filter_fn)]
            for attr_name, children in self.children.items()
        }
        self.children = {key: value for key, value in self.children.items() if value}
        if self.children:
            return True
        return filter_fn(self)

    def collect_references(self) -> set[Reference]:
        child_references: set[Reference] = set()
        for child_name, children in self.children.items():
            child_references_ = [child.collect_references() for child in children]
            # merge list of sets
            child_references_merged = set().union(*child_references_)
            child_references = child_references.union(child_references_merged)

        return {self.reference}.union(child_references)


ReferenceNode.model_rebuild()


class ReferenceTree(BaseModel):
    """A tree-like structure of OOIs representing a subgraph of the objects graph, starting from a `root` ooi.The
    conversion from graph to tree happens through "unfolding" the graph during traversal and allowing duplication of
    nodes in the tree to avoidcycles. Because of the duplication the structure includes a unique, flattened list of OOIs
    present in the tree, the `store`, for convenience."""

    root: ReferenceNode
    store: dict[str, OOIType]
