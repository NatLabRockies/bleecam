# API reference

This reference is generated automatically from the docstrings in `src/bleecam`. It
documents the reusable **core engine** — the shared machinery that the rare-earth
and gallium cases (and any case you add) build on. Case-specific modules are
described narratively in the [case studies](../cases/rare_earth).

:::{admonition} Beta API
:class: warning
Public APIs may change between beta releases. Pin a released tag
(`v0.1.0-beta.1`) if you depend on internals.
:::

## Core engine

```{eval-rst}
.. automodule:: bleecam.core.case_config
   :members:

.. automodule:: bleecam.core.schema
   :members:

.. automodule:: bleecam.core.data_loader
   :members:

.. automodule:: bleecam.core.network
   :members:

.. automodule:: bleecam.core.objectives
   :members:

.. automodule:: bleecam.core.solve
   :members:

.. automodule:: bleecam.core.scenario
   :members:

.. automodule:: bleecam.core.multiobjective
   :members:

.. automodule:: bleecam.core.sensitivity
   :members:

.. automodule:: bleecam.core.lca_import
   :members:
```

## Criticality constraint library

The no-code lever catalogue (see [The criticality constraint library](../criticality_library)).

```{eval-rst}
.. automodule:: bleecam.core.criticality.library
   :members:

.. automodule:: bleecam.core.criticality.catalog
   :members:
```
