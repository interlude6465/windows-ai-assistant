# GUI Startup Compatibility Audit Report (CustomTkinter)

Date: 2026-01-05

## Summary
This audit focused on **startup-stopping errors** and other **high-risk GUI issues** in `src/jarvis/gui/` and `src/jarvis/app.py`.

Primary root cause of the reported crash was an unsupported Tk option (`highlightthickness`) being passed to `customtkinter.CTkTextbox`.

In addition, a significant stability risk was identified: **Tk/CustomTkinter widgets were being updated from background threads**, which can raise `TclError`/`RuntimeError` during normal use (streaming output + sandbox callbacks). These updates are now routed onto the UI thread via `after()`.

---

## Issues Found & Fixed (with file, line, severity)

### 1) Unsupported Tkinter parameter on CTkTextbox (startup crash)
- **Severity:** CRITICAL
- **File:** `src/jarvis/gui/live_code_editor.py`
- **Line(s):** 107–113
- **Issue:** `highlightthickness` is a Tk `Text` option, but **not supported** by `customtkinter.CTkTextbox`.
- **Fix:** Removed `highlightthickness=0` from the constructor.

- **Severity:** CRITICAL
- **File:** `src/jarvis/gui/execution_console.py`
- **Line(s):** 63–69
- **Issue:** Same unsupported `highlightthickness` usage.
- **Fix:** Removed `highlightthickness=0` from the constructor.

### 2) Thread-unsafe GUI updates (crashes during basic interaction)
- **Severity:** HIGH
- **File:** `src/jarvis/app.py`
- **Line(s):** 283–323
- **Issue:** `_command_thread()` ran in a background thread and directly called `.insert()/.configure()` on Tk widgets.
- **Fix:** Routed all widget updates through `_run_on_ui_thread()` which uses `after(0, ...)` when not on the main thread.

- **Severity:** HIGH
- **File:** `src/jarvis/app.py`
- **Line(s):** 222–248
- **Issue:** `get_gui_callback()` returned a callback that could be invoked from non-UI threads (sandbox execution / interactive executor) and directly called `SandboxViewer.handle_gui_callback()`.
- **Fix:** Callback now copies event data and schedules `handle_gui_callback()` onto the UI thread via `_run_on_ui_thread()`.

### 3) Type hint mismatch for voice callback
- **Severity:** MEDIUM
- **File:** `src/jarvis/app.py`
- **Line(s):** 30–38, 431–439
- **Issue:** `voice_callback` was annotated as `Callable[[str], None]`, but the CLI passes a `lambda: ...` (no args) and the GUI calls it with no args.
- **Fix:** Updated typing to `Optional[Callable[[], None]]`.

### 4) Type mismatch in SandboxViewer test id mapping
- **Severity:** LOW
- **File:** `src/jarvis/gui/sandbox_viewer.py`
- **Line(s):** 56
- **Issue:** `test_id_map` was annotated as `dict[str, int]`, but values are actually `str` test ids.
- **Fix:** Corrected to `dict[str, str]`.

### 5) Additional thread-safe wrappers for status/action updates
- **Severity:** MEDIUM
- **File:** `src/jarvis/app.py`
- **Line(s):** 353–413
- **Issue:** These methods mutate UI widgets and may be called from non-UI contexts in the future.
- **Fix:** `update_memory_status()`, `update_tool_status()`, `add_action()`, and `remove_action()` now schedule their work via `_run_on_ui_thread()`.

---

## Audit Checks Performed (and results)

### CustomTkinter compatibility scan (gui/ + app.py)
Searched for common unsupported Tk options (examples: `highlightthickness`, `highlightbackground`, `highlightcolor`, `relief`, `bd`, `bg`, `padx/pady` passed to constructors).
- **Result:** Only `highlightthickness` was found (fixed).

### Recursive/circular logic scan
Searched for custom widget `configure()` overrides that call `self.configure()` and can recurse.
- **Result:** All `configure()` overrides in `src/jarvis/gui/*.py` use `super().configure(**kwargs)` and do not recurse.

### Imports/dependencies
Reviewed imports for GUI modules.
- **Result:** No missing/typo imports found in `src/jarvis/gui/` or `src/jarvis/app.py`.

### File/path issues
Reviewed GUI file operations (deployment open/copy operations).
- **Result:** OS-specific `open`/`xdg-open`/`os.startfile` calls exist (expected) but are not part of the startup path.

### Integration/callback wiring
Reviewed `gui_callback` flow used by `SandboxExecutionSystem`/`InteractiveExecutor`.
- **Result:** Callback is now safe to call from background threads (scheduled onto the UI thread).

---

## Known Systemic Issues Flagged (not changed in this ticket)

These were identified during the audit as **future mega-task candidates**, but are not directly responsible for the current startup crash.

1) **Plan generation fallback can be non-actionable**
   - **File:** `src/jarvis/reasoning.py`
   - **Lines:** ~209–211 (fallback trigger), ~516–538 (fallback steps)
   - If planning response parsing fails, the fallback plan uses generic steps like "Execute requested action", which may be too abstract for downstream executors.

2) **Conversational fallback responses can be generic**
   - **File:** `src/jarvis/response_generator.py`
   - **Line:** ~194
   - When no LLM client is configured or on LLM failure, the rule-based default response can be context-light.

3) **Safety flag completeness depends on plan generation quality**
   - **File:** `src/jarvis/reasoning.py`
   - Fallback plans contain no `safety_flags`, and safety checks currently evaluate only declared flags (so under-flagging is possible when the plan generator fails).
