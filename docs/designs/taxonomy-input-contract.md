# RepoAtlas — Taxonomy Input Contract (Epic 1 → Epic 3)

> **Status:** Proposed. A ~20-line addition to the Core Indexing Engine that lets
> the AI Analysis Engine delete a workaround.
> **Owner:** Epic 1 (Core Indexing). **Requested by:** Epic 3 (AI Analysis).

## 1. The problem

ADR-010 and US-3.5 are built on a 6-tier taxonomy:

```
Repository → Module → Container → Component → Class → Method
```

Tiers 4–6 come free from the AST — every symbol already carries its package and
its parent. Tiers 2 and 3 do not: **Module** is a directory grouping and
**Container** is a deployable unit marked by a build file. Neither is expressible
in source syntax, so the AST parsers cannot see them.

`ir_generator.py::_build_skeleton_modules` currently emits placeholders:

```python
return [{
    "name": self.index.repository_name,
    "containers": [{
        "name": "MainContainer",
        "components": component_list,
    }]
}]
```

One module named after the repository. One container hardcoded to
`"MainContainer"`. So the ladder Epic 3 receives is:

```
Repository → (placeholder) → (placeholder) → Component → Class → Method
```

US-3.3 and US-3.4 both require modules to be *"identified automatically"*, and
the 6-tier claim in ADR-010 cannot be demonstrated against placeholder nodes.

## 2. Why this belongs in Epic 1

`scanner.py::scan_structure` **already walks the entire repository tree**,
directory by directory, applying `.gitignore` rules. Recording which directories
contain a build file is a handful of lines inside a loop that already exists.

Epic 3 currently re-walks the whole filesystem a second time to recover the same
information — work Epic 1 has already done and thrown away.

## 3. Requested output shape

`indexes/structure_overview.json`, `modules[]` array:

```json
{
  "repository": "EnterpriseFintech",
  "languages": ["java", "csharp"],
  "total_symbols": 1284,
  "modules": [
    {
      "name": "billing",
      "path": "billing",
      "containers": [
        {
          "name": "payment-service",
          "path": "billing/payment-service",
          "marker_file": "billing/payment-service/pom.xml",
          "components": [ ... unchanged ... ]
        },
        {
          "name": "invoice-service",
          "path": "billing/invoice-service",
          "marker_file": "billing/invoice-service/pom.xml",
          "components": [ ... ]
        }
      ]
    },
    {
      "name": "identity",
      "path": "identity",
      "containers": [
        {
          "name": "Identity.Api",
          "path": "identity/Identity.Api",
          "marker_file": "identity/Identity.Api/Identity.Api.csproj",
          "components": [ ... ]
        }
      ]
    }
  ]
}
```

### Field requirements

| Field                   | Required | Meaning |
| ----------------------- | -------- | ------- |
| `modules[].name`        | yes      | Directory name of the module |
| `modules[].path`        | yes      | Repository-relative path, forward slashes, `"."` at root |
| `containers[].name`     | yes      | Directory name of the container |
| **`containers[].path`** | **yes**  | **Repository-relative path. This is the field Epic 3 keys on.** |
| `containers[].marker_file` | no    | The build file that identified it — rendered by Epic 4 |
| `containers[].components`  | yes   | Unchanged from today |

**`path` is load-bearing.** Epic 3 decides whether real tiers are present by
checking that every container declares a non-empty `path` and that none is named
`"MainContainer"`. A container without a path corresponds to no directory and
cannot own any symbols.

## 4. Detection rules

**Container** — a directory containing any of:

| Marker | Toolchain |
| ------ | --------- |
| `pom.xml` | Maven |
| `build.gradle`, `build.gradle.kts` | Gradle |
| `*.csproj`, `*.fsproj`, `*.vbproj` | .NET |

A `*.sln` file is **not** a container marker. A solution lists projects; the
containers are the `.csproj` directories beneath it.

**Module** — the parent directory of a container, relative to the repository
root. A container sitting directly at the root belongs to a single module named
after the repository.

```
billing/payment-service  →  module "billing",     path "billing"
a/b/c                    →  module "b",           path "a/b"
payment-service          →  module <repo name>,   path "."
.                        →  module <repo name>,   path "."
```

Directories to skip while scanning: `.git`, `.svn`, `.hg`, `.idea`, `.vscode`,
`node_modules`, `bin`, `obj`, `target`, `build`, `.gradle`, `dist`. Note that
`target/` and `obj/` matter — build output frequently contains copies of build
files, which would otherwise be detected as phantom containers.

## 5. Before / after

Given this repository:

```
EnterpriseFintech/
├── billing/
│   ├── payment-service/pom.xml
│   └── invoice-service/pom.xml
└── identity/
    ├── Identity.sln
    └── Identity.Api/Identity.Api.csproj
```

**Before** — 1 module, 1 container, both placeholders:

```json
{"modules": [{"name": "EnterpriseFintech",
              "containers": [{"name": "MainContainer", "components": [...]}]}]}
```

**After** — 2 modules, 3 containers, all real:

```json
{"modules": [
  {"name": "billing",  "path": "billing",  "containers": [
     {"name": "payment-service", "path": "billing/payment-service",
      "marker_file": "billing/payment-service/pom.xml", "components": [...]},
     {"name": "invoice-service", "path": "billing/invoice-service",
      "marker_file": "billing/invoice-service/pom.xml", "components": [...]}]},
  {"name": "identity", "path": "identity", "containers": [
     {"name": "Identity.Api", "path": "identity/Identity.Api",
      "marker_file": "identity/Identity.Api/Identity.Api.csproj", "components": [...]}]}
]}
```

## 6. Definition of done

- [ ] `scan_structure` records build-file locations during its existing walk
- [ ] `structure_overview.json` emits real `modules[]` and `containers[]`
- [ ] Every container declares `path`; no container is named `"MainContainer"`
- [ ] `*.sln` does not by itself create a container
- [ ] Build output directories produce no phantom containers
- [ ] A single-project repository yields one module named after the repository

## 7. Migration — nothing breaks

Epic 3 already handles both shapes and picks between them at runtime
(`ai_analysis/taxonomy/provider.py::resolve_provider`):

- **Real tiers present** → `IndexTaxonomyProvider` reads them directly
- **Placeholders or file absent** → `HeuristicTaxonomyProvider` detects them itself

The day this contract ships, Epic 3 starts using the real data with **no code
change on either side**. The heuristic fallback can then be deleted.

The heuristic is a faithful stand-in in the meantime: a test
(`test_taxonomy.py::test_index_and_heuristic_agree_on_the_fixture`) asserts that
both providers produce an identical tree for the same repository, so switching
over will not change output.
