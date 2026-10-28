XY Studio Windows editor setup (2026-10-10)

This folder configures VS Code for this workspace only. User settings and application package files were preserved.

Python: .venv/Scripts/python.exe (existing Python 3.12.14).
TypeScript: frontend/node_modules/typescript/lib (existing 5.9.3).
Select "Use Workspace Version 5.9.3" if VS Code asks after a fresh checkout.
Vue / TypeScript / JavaScript / JSON / CSS / HTML: Prettier formatting on save.
Python: Ruff formatting and safe fixes/import organization on explicit save; Pylance basic type checking.
Frontend checks: ESLint with Vue 3 essential rules, TypeScript recommended rules, and formatting rules disabled by eslint-config-prettier.
Existing source files were not reformatted as part of setup.

Editor-only npm dependencies live under .vscode/tooling. Root node_modules is a Windows junction to that directory, so ESLint can resolve its library without changing frontend/package.json or frontend/package-lock.json. The root junction is ignored locally in .git/info/exclude; .vscode/tooling/node_modules is ignored by .vscode/.gitignore.

On reinstall, use the VS Code task "XY Studio: Install editor tooling", which installs locked editor packages and then recreates the junction. Alternatively, from the repository root:
  npm.cmd ci --prefix .vscode/tooling --ignore-scripts --no-audit --no-fund
  node .vscode/tooling/link.cjs

Other tasks: Vue + TypeScript check, ESLint check, Prettier check (no writes), and Python tests. The Python desktop launch configuration is available under Run and Debug.

The machine's global python.exe resolves to a Microsoft Store alias. This setup reuses the working project environment instead of installing another interpreter or changing system PATH. New Python terminals automatically activate .venv.

Official configuration references:
https://vuejs.org/guide/scaling-up/tooling
https://eslint.vuejs.org/user-guide/
https://docs.astral.sh/ruff/editors/setup/
https://code.visualstudio.com/docs/python/settings-reference
