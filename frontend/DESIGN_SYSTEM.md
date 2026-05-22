# WhatsInDemand — Design System

## Foundations

**Font:** IBM Plex Sans (UI), IBM Plex Mono (code/data)  
**Theme:** Dark-only. No light mode planned.  
**Design language:** High-contrast, monochromatic, data-dense. No rounded corners on interactive elements. Minimal decoration.

---

## Color Tokens

Defined in `tailwind.config.js`.

### Text
| Token | Opacity | Use |
|---|---|---|
| `text-white` / `text-ink` | 95% | Primary text, headings |
| `text-ink-muted` | 62% | Descriptions, secondary labels, helper text |
| `text-ink-faint` | 38% | Metadata, eyebrow labels, placeholders, disabled text |
| `text-ink-ghost` | 22% | Minimal-emphasis accents |

### Backgrounds
| Token | Use |
|---|---|
| `bg-black` | Page background |
| `bg-surface` | Cards, panels, inputs (`rgba(255,255,255,0.05)`) |
| `bg-surface-raised` | Elevated surfaces (`rgba(255,255,255,0.07)`) |
| `bg-white/10` | Disabled button background |
| `bg-white/20` | Slightly more visible disabled state |

### Borders
| Token | Use |
|---|---|
| `border-line` | Default card/container borders (`rgba(255,255,255,0.10)`) |
| `border-line-strong` | Form inputs, high-contrast dividers (`rgba(255,255,255,0.20)`) |
| `border-white` | Focused input, active state |

### Accent
| Token | Use |
|---|---|
| `text-accent-up` / `bg-accent-up` | `#4ade80` — positive, growth |
| `text-accent-down` / `bg-accent-down` | `#f87171` — negative, errors |
| `text-accent-warn` / `bg-accent-warn` | `#fbbf24` — warning |

---

## Typography

Custom sizes defined in `tailwind.config.js`.

| Class | Size | Use |
|---|---|---|
| `text-eyebrow` | 12px, 600 weight, 0.06em tracking | All-caps section labels (`PROFILE`, `SKILLS IN DEMAND`) |
| `text-small` | 13px | UI labels, button text, help text |
| `text-meta` | 14px | Data annotations, counts, secondary info |
| `text-body` | 16px | Main content blocks |
| `text-h2` | 22px, 500 weight | Section headings |
| `text-display` | 36px, −0.02em tracking | Card/panel display numbers |
| `text-hero` | 48px, −0.02em tracking | Page hero titles |

**Standard Tailwind sizes in use:**
- `text-4xl font-semibold` — major auth/form headings (CREATE ACCOUNT, SIGN IN)
- `text-5xl` / `text-6xl font-semibold` — screen titles (WHAT'S YOUR ROLE?)
- `text-xl text-ink-muted` — subtitle/description under page title
- `text-sm` — general UI copy, dropdown items, table cells

**Rules:**
- Page titles: ALL CAPS, `font-semibold`, `tracking-tight`
- Section labels: ALL CAPS, `text-eyebrow`, `tracking-widest`, `text-ink-faint` or `text-ink-muted`
- Body copy: sentence case, no weight modifier
- Never mix font sizes within a single button label

---

## Buttons

Three tiers. One primary CTA per screen max.

### Primary
White fill, black text. Main action per screen.
```
px-6 py-3 bg-white text-black font-medium text-sm tracking-wide hover:bg-gray-200 transition-colors
```

**Loading state** — drops to dark, shows DotSpinner:
```jsx
disabled={isLoading}
className={isLoading
  ? 'bg-white/10 text-ink-faint cursor-not-allowed ...'
  : 'bg-white text-black hover:bg-gray-200 ...'}

{isLoading && <DotSpinner size={16} tone="white" />}
{isLoading ? 'LOADING...' : 'LABEL'}
```
> Always use `tone="white"` on loading state — button background turns dark.

**Disabled state** (not loading, just invalid):
```
bg-white/10 text-ink-faint cursor-not-allowed
```

### Secondary
Transparent with border. Supporting/back actions.
```
px-5 py-3 border border-line-strong text-sm font-medium hover:bg-surface transition-colors
```

### Ghost
Text-only. Low-priority actions (Skip, Cancel).
```
text-small text-ink-muted hover:text-white transition-colors
```

### Destructive
For irreversible actions (delete account, remove).
```
px-4 py-2 border border-red-500/50 text-red-400 text-sm hover:bg-red-500/10 transition-colors
```

### Icon buttons
```
p-2 text-ink-muted hover:text-white transition-colors
```

---

## Loading Spinner

**Always use `<DotSpinner>`** — never raw `animate-spin` SVG or third-party spinners.

```jsx
<DotSpinner size={48} tone="white" />  // Full-screen / large
<DotSpinner size={20} tone="white" />  // In-button (dark bg)
<DotSpinner size={16} tone="white" />  // Compact in-button
<DotSpinner size={18} tone="black" />  // On light backgrounds only
```

**Tone rule:**
- `tone="white"` — whenever background is dark (black, surface, white/10)
- `tone="black"` — only when placed on a white background

---

## Form Inputs

```
w-full px-4 py-3 bg-surface border border-line-strong text-white
placeholder-gray-500 text-sm focus:outline-none focus:border-white transition-colors
```

**Textarea:** same as input + `resize-none`  
**Focus:** `focus:outline-none focus:border-white` — border brightens, no glow  
**Error state:** swap `border-line-strong` → `border-accent-down`

---

## Cards & Surfaces

**Standard card:**
```
bg-surface border border-line p-6
```

**Compact card:**
```
bg-surface border border-line p-4
```

**Info/callout box:**
```
p-3 bg-surface border-l-2 border-white/40
```

**Error box:**
```
p-4 bg-accent-down/20 border border-accent-down text-accent-down
```

---

## Layout

**Max-width containers:**
| Width | Use |
|---|---|
| `max-w-7xl mx-auto` | Nav, footer |
| `max-w-4xl mx-auto` | Hero sections |
| `max-w-3xl mx-auto` | Main screen content (dashboard, role selection, skills input) |
| `max-w-md mx-auto` | Auth flows (login, signup) |

**Page padding:**
- Content: `px-8 pt-16 pb-24`
- Auth: `px-6 pt-16 pb-24`
- Nav: `px-4 sm:px-6 lg:px-8 py-6`

**Vertical rhythm:**
- Between major sections: `mb-10`
- Between form fields: `mb-6` / `space-y-3`
- Between label and input: `mb-2`
- Between items in a list: `gap-3`

---

## Shared Components

All live in `frontend/src/App.js`.

| Component | Props | Notes |
|---|---|---|
| `<NavBar />` | none | Fixed top nav |
| `<Footer />` | none | Page footer |
| `<ErrorMessage />` | `error`, `onClose`, `onRetry`, `retryLabel` | Red error bar |
| `<DotSpinner />` | `size`, `tone`, `className` | Loading spinner — see Loading section |

---

## Rules

1. **One primary button per screen.** Secondary and ghost for everything else.
2. **All loading states use `DotSpinner`.** No raw SVG spinners.
3. **Loading buttons always drop to dark background** (`bg-white/10`) + `tone="white"` spinner.
4. **No border-radius on buttons or cards** unless it's a circular icon button.
5. **ALL CAPS for primary actions and section labels.** Sentence case for body copy and descriptions.
6. **`text-ink-muted` for descriptions, `text-ink-faint` for metadata/labels.** Don't mix them.
7. **Never hardcode colors** — use tokens from `tailwind.config.js`.
