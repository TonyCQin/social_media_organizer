# Frontend Dashboard

This folder holds all dashboard UI logic: components, styles, and utilities for visualizing ingested places and NLP results.

Current setup: vanilla JavaScript + HTML/CSS (no framework yet).

File structure:
- `index.html` — main entry point
- `components/` — reusable UI components
- `styles/` — global CSS
- `utils/` — helper functions (API calls, etc.)

## Framework Decision

You can add a framework later. Current options:

### Option 1: Stay Vanilla (Current)
- ✓ No build step; just plain HTML/CSS/JS
- ✓ Fast prototype and iterate
- ✗ As app grows, code gets messy without structure

### Option 2: React (npm + vite/webpack)
- ✓ Component-based, reusable
- ✓ Great ecosystem (react-leaflet for maps, etc.)
- ✗ Requires build step and npm

### Option 3: Vue (npm + vite)
- ✓ Lighter than React, easier to learn
- ✓ Good component isolation
- ✗ Still requires npm/build

### Option 4: Svelte (npm + vite)
- ✓ Very lightweight, minimal boilerplate
- ✓ Compiles to vanilla JS
- ✗ Requires build step

**Recommendation:** Start vanilla (current), refactor to React/Vue when you have 5+ components or need interactive state management.

To migrate later:
1. Run `npm init vite@latest . -- --template react` (or vue/svelte)
2. Move your logic into JSX components
3. Wire API calls in useEffect hooks
