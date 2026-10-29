# Provenance

Manifests, verification, bundles and ODD skeletons behind `modelly run`, `modelly verify`,
`modelly bundle` and `modelly odd`. How to use them to publish a study is in
[Publishing a reproducible study](../provenance.md).

```{eval-rst}
.. automodule:: modelly.provenance
```

```{eval-rst}
.. automodule:: modelly.provenance.manifest
   :members:
```

```{eval-rst}
.. automodule:: modelly.provenance.runner
   :members: RunSpec, run_study, read_scenario
```

```{eval-rst}
.. automodule:: modelly.provenance.verify
   :members: Verification, verify
```

```{eval-rst}
.. automodule:: modelly.provenance.compare
   :members:
```

```{eval-rst}
.. automodule:: modelly.provenance.bundle
   :members: BundleError, bundle, bundle_entries
```

```{eval-rst}
.. automodule:: modelly.provenance.llm
   :members:
```

```{eval-rst}
.. automodule:: modelly.provenance.odd
   :members: odd_markdown
```
