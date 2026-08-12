"""Index-backed taxonomy — reads real Module and Container tiers from Epic 1.

The preferred provider.  Used when ``structure_overview.json`` carries genuine
tier-2 and tier-3 data rather than the ``"MainContainer"`` placeholder Epic 1
currently emits.  Selection is automatic; see
:func:`ai_analysis.taxonomy.provider.resolve_provider`.

The expected input shape is specified in ``docs/designs/taxonomy-input-contract.md``::

    {
      "modules": [
        {
          "name": "billing",
          "path": "billing",
          "containers": [
            {
              "name": "payment-service",
              "path": "billing/payment-service",
              "marker_file": "billing/payment-service/pom.xml"
            }
          ]
        }
      ]
    }

Only Module and Container are read from the overview.  Components, classes and
methods are always rebuilt from ``repository_index.json``, which is richer and
authoritative for tiers 4–6.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ai_analysis.ir_models import RepositoryIndex, StructureOverview
from ai_analysis.taxonomy.base import BaseTaxonomyProvider, ContainerSpec

logger = logging.getLogger(__name__)


class IndexTaxonomyProvider(BaseTaxonomyProvider):
    """Reads Module and Container tiers directly from ``structure_overview.json``."""

    name = "index"

    def discover(
        self,
        index: RepositoryIndex,
        overview: Optional[StructureOverview] = None,
    ) -> List[ContainerSpec]:
        if overview is None or not overview.modules:
            raise ValueError(
                "IndexTaxonomyProvider requires a structure_overview.json with real "
                "module/container tiers. Use resolve_provider() to select automatically."
            )

        specs: List[ContainerSpec] = []

        for module in overview.modules:
            if not isinstance(module, dict):
                continue
            module_name = module.get("name") or index.repository_name
            module_path = module.get("path") or "."

            for container in module.get("containers", []) or []:
                if not isinstance(container, dict):
                    continue
                directory = container.get("path")
                if not directory:
                    # resolve_provider() should have prevented this, but a
                    # pathless container cannot own any symbols.
                    logger.warning(
                        "Container '%s' in module '%s' has no path; skipping",
                        container.get("name"),
                        module_name,
                    )
                    continue

                specs.append(
                    ContainerSpec(
                        directory=directory.replace("\\", "/").rstrip("/"),
                        name=container.get("name") or directory.split("/")[-1],
                        module_name=module_name,
                        module_path=module_path,
                        marker_file=container.get("marker_file"),
                    )
                )

        logger.info("Read %d container(s) from structure_overview.json", len(specs))
        return specs
