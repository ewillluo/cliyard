## Plugin System Implementation - 2026-07-16

### Files Created
- src/cliyard/plugin/__init__.py — PluginRegistry + decorators
- src/cliyard/plugin/discovery.py — Entry points + directory scanning

### Files Modified
- src/cliyard/client/auth.py — plugin: step type handling
- src/cliyard/validate/types.py — Plugin field type fallback lookup
- src/cliyard/engine/loader.py — plugins: YAML section parsing

### Results
- All 123 tests pass. Imports, registration, discovery verified.
