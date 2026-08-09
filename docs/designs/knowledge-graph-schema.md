# RepoAtlas Knowledge Graph Schema

## Purpose

Epic 2 converts the Intermediate Representation produced by `core_indexing`
into a persistent, self-contained `graphs/graph.json`. The graph is fully
regenerated on every build and can optionally include Epic 3 summaries and wiki
content.

## Inputs

- Required: `repository_index.json`, supplied either directly or through its
  containing directory.
- Optional: a sibling `structure_overview.json`, used for structural taxonomy
  nodes when no analysis result is supplied.
- Optional: `summaries.json`, supplied explicitly with `--analysis`. Its
  repository name and path must match the repository index.

## Top-Level Contract

```json
{
  "schema_version": "1.0",
  "repository": {
    "name": "sample_repo",
    "path": "/path/to/sample_repo",
    "languages": ["csharp", "java"]
  },
  "nodes": [],
  "edges": [],
  "content": []
}
```

Output is sorted deterministically and contains no timestamp. Writing is atomic:
the complete new graph replaces the previous file only after serialization
succeeds.

## Nodes

Every node has `id`, `type`, `name`, and a `metadata` object. Language, source
path, and source range are included where applicable.

Node types include:

- Structural: `REPOSITORY`, `MODULE`, `CONTAINER`, `COMPONENT`, and `FILE`.
- Code symbols: the Epic 1 kinds such as `CLASS`, `INTERFACE`, `METHOD`,
  `CONSTRUCTOR`, `FIELD`, and `PROPERTY`.
- `EXTERNAL`: an unresolved relationship endpoint, ensuring every edge points
  to a node.

IDs use these rules:

- AST symbols retain their `symbol_id` unchanged.
- Repository IDs begin with `repository:`.
- Taxonomy IDs begin with `taxonomy:`.
- File IDs begin with `file:`.

Symbol metadata includes modifiers, annotations, docstrings, signatures,
property accessors, field types, declared dependencies, inheritance metadata,
and optional Epic 3 summaries. File metadata includes package/namespace and
imports. Epic 3 content sections are copied to the top-level `content` array.

## Edges

Each directed edge has:

```json
{
  "source": "com.example.OrderService",
  "target": "com.example.OrderRepository",
  "kind": "uses_field",
  "line": 12,
  "origin": "index"
}
```

Epic 1 relationships are preserved, including `extends`, `implements`,
`uses_field`, `contains`, `calls`, and `instantiates` when present. Epic 2 adds
`contains` taxonomy edges and `declares` file-to-symbol edges. `origin` is one
of `index`, `taxonomy`, or `graph_builder`.

## Python API

```python
from knowledge_graph import GraphQuery, build_from_paths, load_graph, write_graph

graph = build_from_paths("indexes", analysis_path="analysis")
write_graph(graph, "graphs")

query = GraphQuery(load_graph("graphs"))
dependencies = query.dependencies("com.example.OrderService")
dependents = query.dependents("com.example.OrderRepository")
path = query.shortest_path(
    "com.example.OrderService",
    "com.example.OrderRepository",
)
```

`GraphQuery` also provides `get_node`, `outgoing`, `incoming`, and `query`.
Relationship kinds can be supplied to every relationship operation as a
filter. Path traversal is directed.

## CLI

```bash
python -m knowledge_graph build indexes/ -o graphs/
python -m knowledge_graph build indexes/ --analysis analysis/ -o graphs/

python -m knowledge_graph query graphs/ <node-id> --direction both
python -m knowledge_graph dependencies graphs/ <node-id> --kind calls
python -m knowledge_graph dependents graphs/ <node-id>
python -m knowledge_graph path graphs/ <source-id> <target-id>
```

Query commands emit JSON. Missing or invalid artifacts return exit code 1;
unknown node IDs return exit code 2. A valid query with no connecting path
returns an empty path with a successful exit status.

## Known Upstream Limitation

The Java and C# parsers currently calculate `calls` and `instantiates` edges,
but Epic 1 does not propagate those parser-local edges into
`repository_index.json`. Epic 2 supports both kinds whenever they are present;
repairing their Epic 1 propagation is outside this implementation.
