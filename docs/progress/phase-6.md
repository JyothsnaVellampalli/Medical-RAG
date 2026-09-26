# Phase 6: UI
Status: done   Date: 2026-09-23

## What was built
A full React+TypeScript frontend with a navbar and five pages (Home, Chunk, Retrieve, Ask, Evaluate), five reusable common components, and live wiring to the two APIs that exist (`/get_chunks`, `/retrieve`). Ask and Evaluate are complete UI shells per the roadmap's explicit allowance ("if any of the apis are not added, just do the UI") — their submit actions show a clear "not yet available" notice instead of calling nonexistent endpoints.

## Files created / changed
- `frontend/src/index.css`: added shared CSS custom properties (`--color-*`, `--radius`, `--spacing-*`) so every component/page draws from one palette.
- `frontend/src/CommonComponents/`:
  - `Button`, `Dropdown` (native `<select>` wrapper), `Loader`, `Navbar`, `Table` (generic, columns-driven), `Modal` (Escape-to-close), `CollapsiblePanel` (built for Ask's future citations panel)
- `frontend/src/Pages/`:
  - `Chunk`: "Show chunks" button → `/get_chunks` → `Table`
  - `Retrieve`: strategy `Dropdown`, weight slider (shown only for Hybrid(Weighted), displays both semantic and computed complementary BM25 weight), search box with Enter-to-submit, `Table` of results
  - `Ask`: heading, placeholder LLM-name subheading, search box, "not yet available" notice on submit
  - `Evaluate`: header with top-right "Evaluate" button opening a `Modal` (test data size input, retrieval-mechanism checkboxes, "Start evaluation"), empty-state message, "not yet available" notice on submit
  - `Landing` (Phase 0, unchanged) now wrapped by the shared layout
- `frontend/src/App.tsx`: added a `Layout` component (`Navbar` + `<Outlet />`) wrapping all five routes
- `frontend/src/api/client.ts`: added `getChunks()`, `retrieve()`, and their request/response types (`ChunkResult`, `RetrieveResult`, `RetrieveRequest`, `SearchType`)

## Key decisions and why
- **Dropdown wraps native `<select>`**: gets keyboard accessibility (arrow keys, type-to-select, Enter/Escape) for free, satisfying the UI Design's keyboard-handling rule more robustly than a hand-rolled div-based dropdown.
- **Navbar includes Ask and Evals**: confirmed with you — the UI Design doc's navbar rule was updated to explicitly list all four (Chunk, Retrieve, Ask, Evals) during this phase's planning.
- **Weight slider shows the computed complement, not two independent inputs**: guarantees semantic + BM25 weights always sum to 1, matching `hybrid_weighted_search`'s single-`weight` signature — no way to submit an invalid combination.
- **No speculative API stubs**: `client.ts` only has methods for endpoints that exist. Ask/Evaluate's "not yet available" notices are a deliberate, honest UI state rather than a silent failure or a fake mocked response.
- **Landing kept as Home**: your call — "/" still shows the Phase 0 connectivity-check landing page rather than redirecting straight into a feature page.

## How to run / test
- No pytest-equivalent (standing instruction extends to frontend too). Verified with a headless-browser (Playwright) click-through of all five routes against the live backend and the real (partial, ~23,200/40,221-row) corpus:
  - Landing: confirmed "Backend: connected"
  - Chunk: "Show chunks" → 10 real rows rendered
  - Retrieve: BM25 search → 10 results; switched to Hybrid(Weighted), confirmed the weight slider appears and both weight values display, re-searched → 10 results, screenshotted
  - Ask: submitted a query → confirmed the "not yet available" notice appears
  - Evaluate: opened the config modal, screenshotted, confirmed Escape closes it
  - Zero browser console errors across the whole run
- `npm run lint` — clean.
- `npm run build` (`tsc -b && vite build`) — clean, no type errors.

## Known issues / tech debt
- Ask and Evaluate are not functionally complete — by design, pending Phase 7 and Phase 8's backend work.
- No automated frontend tests (matches the project's standing "no pytest" preference, extended to the frontend).
- Evaluate page's comparison view (tables/charts described in the UI Design doc) isn't built yet — there's no real evaluation data to visualize until Phase 8 exists; only the trigger UI (config modal) was built.

## Notes for next phase
- Phase 7 (LLM/Ask): needs an LLM model name in `.env` for the Ask page's subheading (currently hardcoded to "LLM: not configured yet"), a `/query` endpoint, and wiring in `Ask.tsx` — the `CollapsiblePanel` component is already built and ready for the citations sidebar.
- Phase 8 (Evaluate): needs `/get_evals` and `evaluate` endpoints; `Evaluate.tsx`'s config modal already collects `testDataSize` and `selectedMechanisms` (as `SearchType[]`) in the exact shape a future `evaluate` API call would need as its payload.
