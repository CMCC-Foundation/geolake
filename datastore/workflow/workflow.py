import json
from typing import Generator, Hashable, Callable, Literal, Any
from functools import partial
import logging

import networkx as nx
from geokube.core.datacube import DataCube
from geoquery.geoquery import GeoQuery
from geoquery.task import TaskList
from datastore.datastore import Datastore

AggregationFunctionName = (
    Literal["max"]
    | Literal["nanmax"]
    | Literal["min"]
    | Literal["nanmin"]
    | Literal["mean"]
    | Literal["nanmean"]
    | Literal["sum"]
    | Literal["nansum"]
)


_LOG = logging.getLogger("geokube.workflow")

TASK_ATTRIBUTE = "task"


class _WorkflowTask:
    __slots__ = ("id", "dependencies", "operator")

    id: Hashable
    dependencies: list[Hashable] | None
    operator: Callable[..., DataCube]

    def __init__(
        self,
        id: Hashable,
        operator: Callable[..., DataCube],
        dependencies: list[Hashable] | None = None,
    ) -> None:
        self.operator = operator
        self.id = id
        if dependencies is None:
            dependencies = []
        self.dependencies = dependencies

    def compute(self, kube: DataCube | None) -> DataCube:
        return self.operator(kube)


class Workflow:
    __slots__ = ("graph", "present_nodes_ids", "is_verified")

    graph: nx.DiGraph
    present_nodes_ids: set[Hashable]
    is_verified: bool

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.present_nodes_ids = set()
        self.is_verified = False

    @classmethod
    def from_tasklist(cls, task_list: TaskList) -> "Workflow":
        workflow = cls()
        for task in task_list.tasks:
            match task.op:
                case "subset":
                    workflow.subset(task.id, **task.args)
                case "resample":
                    workflow.resample(
                        task.id, dependencies=task.use, **task.args
                    )
                case "average":
                    workflow.average(
                        task.id, dependencies=task.use, **task.args
                    )
                case "to_regular":
                    workflow.to_regular(
                        task.id, dependencies=task.use, **task.args
                    )
                case _:
                    raise ValueError(
                        f"task operator: {task.op} is not defined"
                    )
        return workflow

    def _add_computational_node(self, task: _WorkflowTask):
        node_id = task.id
        assert (
            node_id not in self.present_nodes_ids
        ), "worflow task IDs need to be unique!"
        self.present_nodes_ids.add(node_id)
        self.graph.add_node(node_id, **{TASK_ATTRIBUTE: task})
        for dependend_node in task.dependencies:
            self.graph.add_edge(dependend_node, node_id)
        self.is_verified = False

    def subset(
        self,
        id: Hashable,
        dataset_id: str,
        product_id: str,
        query: GeoQuery | dict,
    ) -> "Workflow":
        def _subset(kube: DataCube | None = None) -> DataCube:
            return Datastore().query(
                dataset_id=dataset_id,
                product_id=product_id,
                query=(
                    query if isinstance(query, GeoQuery) else GeoQuery(**query)
                ),
                compute=False,
            )

        task = _WorkflowTask(id=id, operator=_subset)
        self._add_computational_node(task)
        return self

    def resample(
        self,
        id: Hashable,
        freq: str,
        agg: Callable[..., DataCube] | AggregationFunctionName,
        resample_kwargs: dict[str, Any] | None,
        *,
        dependencies: list[Hashable],
    ) -> "Workflow":
        def _resample(kube: DataCube | None = None) -> DataCube:
            assert kube is not None, "`kube` cannot be `None` for resampling"
            return kube.resample(
                operator=agg,
                frequency=freq,
                **resample_kwargs,
            )

        task = _WorkflowTask(
            id=id, operator=_resample, dependencies=dependencies
        )
        self._add_computational_node(task)
        return self

    def average(
        self, id: Hashable, dim: str, *, dependencies: list[Hashable]
    ) -> "Workflow":
        def _average(kube: DataCube | None = None) -> DataCube:
            assert kube is not None, "`kube` cannot be `None` for averaging"
            return kube.average(dim=dim)

        task = _WorkflowTask(
            id=id, operator=_average, dependencies=dependencies
        )
        self._add_computational_node(task)
        return self

    def to_regular(
        self, id: Hashable, *, dependencies: list[Hashable]
    ) -> "Workflow":
        def _to_regular(kube: DataCube | None = None) -> DataCube:
            assert (
                kube is not None
            ), "`kube` cannot be `None` for `to_regular``"
            return kube.to_regular()

        task = _WorkflowTask(
            id=id, operator=_to_regular, dependencies=dependencies
        )
        self._add_computational_node(task)
        return self

    def add_task(
        self,
        id: Hashable,
        func: Callable[..., DataCube],
        dependencies: list[str] | None = None,
        **func_kwargs,
    ) -> "Workflow":
        task = _WorkflowTask(
            id=id,
            operator=partial(func, **func_kwargs),
            dependencies=dependencies,
        )
        self._add_computational_node(task)
        return self

    def verify(self) -> "Workflow":
        if self.is_verified:
            return
        assert nx.is_directed_acyclic_graph(
            self.graph
        ), "the workflow contains cycles!"
        for u, v in self.graph.edges:
            if TASK_ATTRIBUTE not in self.graph.nodes[u].keys():
                _LOG.error(
                    "task with id `%s` is not defined for the workflow", u
                )
                raise ValueError(
                    f"task with id `{u}` is not defined for the workflow"
                )
            if TASK_ATTRIBUTE not in self.graph.nodes[v].keys():
                _LOG.error(
                    "task with id `%s` is not defined for the workflow", v
                )
                raise ValueError(
                    f"task with id `{v}` is not defined for the workflow"
                )
        self.is_verified = True

    def traverse(self) -> Generator[_WorkflowTask, None, None]:
        for node_id in nx.topological_sort(self.graph):
            _LOG.debug("computing task for the node: %s", node_id)
            yield self.graph.nodes[node_id][TASK_ATTRIBUTE]

    def compute(self) -> DataCube:
        self.verify()
        result = None
        for task in self.traverse():
            result = task.compute(result)
        return result

    def __len__(self):
        return len(self.graph.nodes)

    def __getitem__(self, idx: Hashable):
        return self.graph.nodes[idx]
