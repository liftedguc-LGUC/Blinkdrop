# Role: UI/UX Developer

> **Frozen snapshot — do not edit.** Captured at commit `6ea38e3`. The live,
> deployable copies live at the repo root; this folder is the historical record
> of what this stage produced.

You take the PM's wireframe (`../01-pm/wireframe.html`) and turn it into the
production frontend using the design system in `design-spec.md`.

## Inputs
- `../01-pm/wireframe.html` — low-fidelity four-screen wireframe
- Brand reference: the Blinkdrop logo and a screenshot of the live dashboard

## Produced
- `design-spec.md` — colors, type, spacing, components, element IDs, extracted
  from the brand reference
- `styles.css` — design tokens as CSS custom properties + component classes
- `landing.html`, `form.html`, `thanks.html`, `dashboard.html`

## What the SWE stage changed

The root copies have since been wired to a backend. To see exactly what changed:

```
git diff 6ea38e3 -- form.html dashboard.html styles.css
```

The software engineer (`../03-swe/`) takes it from here.
