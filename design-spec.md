# Blinkdrop Design Spec

Source of truth for the production frontend (`styles.css`, `landing.html`,
`form.html`, `thanks.html`, `dashboard.html`). Extracted from the Blinkdrop
logo and a screenshot of the live Blinkdrop dashboard product surface.

> Note: the reference screenshot also showed an *outer* builder/editor
> chrome bar (Preview/Edit tabs, Home breadcrumb, avatar, Upgrade, Publish).
> That chrome belongs to the third-party tool used to prototype the screen,
> not to Blinkdrop's own UI, and is intentionally excluded below. Only the
> product surface itself (black sidebar + white content area) informed
> these tokens.

## Colors

| Token | Value | Usage |
|---|---|---|
| `--color-bg-dark` | `#171717` | Sidebar background |
| `--color-gold` | `#D4A72C` | Brand accent — logo, active states, primary buttons |
| `--color-gold-hover` | `#C79826` | Hover state for gold elements |
| `--color-bg-light` | `#FFFFFF` | Main content background, cards |
| `--color-bg-muted` | `#F5F5F4` | Page background |
| `--color-border` | `#E4E4E7` | Card/table/input borders |
| `--color-text-primary` | `#18181B` | Headings, primary text on light bg |
| `--color-text-secondary` | `#71717A` | Muted labels, subtext |
| `--color-text-on-dark` | `#FFFFFF` | Active sidebar nav text |
| `--color-text-on-dark-muted` | `#A1A1AA` | Inactive sidebar nav text |
| `--color-success` | `#16A34A` | Positive/approved values |

## Typography

- `--font-sans`: system stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`) — used for all UI text.
- `--font-script`: cursive stack (`"Brush Script MT", "Segoe Script", cursive`) — reserved **only** for the "Blinkdrop" wordmark, never body text.
- Scale: `--fs-xs:11px --fs-sm:12px --fs-base:14px --fs-md:16px --fs-lg:18px --fs-2xl:24px --fs-3xl:28px --fs-stat:32px`
- Weights: `--fw-regular:400 --fw-medium:500 --fw-bold:700`

## Spacing / shape

- 4px scale: `--space-1:4px --space-2:8px --space-3:12px --space-4:16px --space-5:20px --space-6:24px --space-8:32px`
- Radius: `--radius-sm:6px` (inputs), `--radius-md:8px` (buttons), `--radius-lg:10px` (cards/panels), `--radius-full:999px` (pills)
- `--shadow-sm: 0 1px 2px rgba(0,0,0,0.05)`
- `--sidebar-width: 230px`
- `--transition-fast: 120ms ease`

## Components

- **Logo lockup** (`.logo`) — gold "B" monogram mark (`.logo-mark`) paired with the "Blinkdrop" script wordmark (`.logo-wordmark`) in gold.
- **Button** (`.btn`) — `.btn-primary` solid gold background, dark text, used for main CTAs (Give Feedback, Submit, Done). `.btn-ghost` transparent/text-only, used for secondary actions and links.
- **Card** (`.card`) — white background, subtle border, `--radius-lg`, `--shadow-sm`; the shell for landing/form/thanks content.
- **Sidebar nav item** (`.nav-item`) — muted gray text by default; `.is-active` gets a gold left border accent + bold white text.
- **Stat card** (`.stat-card`) — uppercase muted label on top, large bold number below; `.stat-card-value--success` renders the number in `--color-success`.
- **Pill tab** (`.pill-tab`) — fully rounded filter button; `.is-active` gets a gold border ring.
- **Data table** (`.data-table`) — bold gray header row, bottom-bordered rows, centered muted text for empty states.
- **Form control** (`.field`, `.input`, `.textarea`) — bordered, `--radius-sm`; `.input-readonly` for prefilled/non-editable fields.

## Naming convention

- **IDs**: kebab-case, `<role>-<name>` — e.g. `btn-give-feedback`, `nav-dashboard`, `filter-tab-pending`, `input-rating-3`, `stat-approved-today`.
- **Classes**: component-scoped BEM-lite — `.block`, `.block-part`, and `.is-active` / `--success` style modifiers.
