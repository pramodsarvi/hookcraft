import asyncio
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("GraphRuntime")

try:
    from langgraph.graph import END, StateGraph
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    END = "__end__"

    class CompiledGraph:
        """Lightweight native StateGraph execution engine (zero-dependency fallback)."""

        def __init__(self, graph: "StateGraph"):
            self.graph = graph

        async def ainvoke(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
            state = dict(initial_state)
            current = self.graph.entry_point

            visited_count = 0
            max_steps = 100

            while current and current != END and visited_count < max_steps:
                visited_count += 1
                node_fn = self.graph.nodes.get(current)
                if not node_fn:
                    logger.error("Node '%s' not found in graph.", current)
                    break

                if asyncio.iscoroutinefunction(node_fn):
                    delta = await node_fn(state)
                else:
                    delta = node_fn(state)

                if isinstance(delta, dict):
                    state.update(delta)

                if current in self.graph.conditional_edges:
                    cond_fn, mapping = self.graph.conditional_edges[current]
                    target = cond_fn(state)
                    if mapping and target in mapping:
                        current = mapping[target]
                    else:
                        current = target
                elif current in self.graph.edges:
                    current = self.graph.edges[current]
                else:
                    break

            return state

        def invoke(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
            return asyncio.run(self.ainvoke(initial_state))

    class StateGraph:
        """Zero-overhead fallback for LangGraph StateGraph when langgraph is not installed."""

        def __init__(self, state_schema: Any = None):
            self.state_schema = state_schema
            self.nodes: Dict[str, Callable] = {}
            self.edges: Dict[str, str] = {}
            self.conditional_edges: Dict[str, tuple] = {}
            self.entry_point: Optional[str] = None

        def add_node(self, name: str, func: Callable) -> None:
            self.nodes[name] = func

        def set_entry_point(self, name: str) -> None:
            self.entry_point = name

        def add_edge(self, start: str, end: str) -> None:
            self.edges[start] = end

        def add_conditional_edges(
            self,
            start: str,
            condition_func: Callable,
            mapping: Optional[Dict[str, str]] = None,
        ) -> None:
            self.conditional_edges[start] = (condition_func, mapping)

        def compile(self) -> CompiledGraph:
            return CompiledGraph(self)

__all__ = ["StateGraph", "END", "HAS_LANGGRAPH"]
