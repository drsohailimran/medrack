# Design System

UX guidance for the MedRack frontend. No code; this is a
specification for the design language. The production
frontend will be built with Lovable; the operator should
follow this guide.

## Philosophy

MedRack is a **medical professional tool** for serious work.
The design should be:
- **Calm** — no loud colors, no aggressive animations
- **Dense** — show all relevant data without scrolling
- **Trustworthy** — typography and color convey precision
- **Quiet** — only the data the user asked for, not promotional
  content

The audience is a single operator (likely a medical student
or doctor) who will spend hours in the app. The design
should support sustained focus, not be flashy.

## Typography

**Font family**: System font stack (San Francisco, Segoe UI,
Inter, Roboto, sans-serif). No custom fonts in v1.

**Font sizes** (rem-based):
- `xs` (0.75rem, 12px) — labels, captions
- `sm` (0.875rem, 14px) — table cells, secondary text
- `base` (1rem, 16px) — body text
- `lg` (1.125rem, 18px) — section headings
- `xl` (1.25rem, 20px) — page titles
- `2xl` (1.5rem, 24px) — main heading on each page
- `3xl` (1.875rem, 30px) — top-level titles

**Font weights**:
- `400` — body text
- `500` — table headers, button text
- `600` — section headings
- `700` — page titles (rare)

**Line height**:
- `1.5` for body text
- `1.2` for headings
- `1.7` for the answer text (more readable for long prose)

## Spacing

**Base unit**: 4px. Use multiples of 4 for all spacing.

- `1` (4px) — tight padding
- `2` (8px) — small gap
- `3` (12px) — default gap
- `4` (16px) — section padding
- `6` (24px) — large gap
- `8` (32px) — section margin
- `12` (48px) — page margin

**Page max width**: 1200px. Long answer text should be
limited to 800px for readability.

## Layout

**Grid**: 12-column grid with 24px gutters.

**Breakpoints**:
- `sm` (640px) — phone
- `md` (768px) — tablet
- `lg` (1024px) — desktop
- `xl` (1280px) — wide desktop

**Page structure**:
- Top bar (always visible, 64px height)
- Side nav (always visible on `lg`+, collapsible on `md`,
  hidden on `sm`)
- Main content (fluid width, max 1200px)

**Side nav width**: 240px expanded, 64px collapsed.

## Cards

Cards are the primary content containers.

**Card anatomy**:
- Header (title, optional action)
- Body (the main content)
- Optional footer (actions, status)

**Card spacing**:
- Internal padding: 16px (4 units)
- Border radius: 8px
- Shadow: `0 1px 3px rgba(0,0,0,0.05)` (subtle)
- Border: 1px solid #e5e7eb (light gray)

**Card states**:
- Default: white background
- Hover (for clickable cards): shadow deepens to
  `0 4px 6px rgba(0,0,0,0.1)`
- Disabled: opacity 0.5, cursor: not-allowed

## Dialogs

Use modal dialogs for:
- Destructive actions (Remove book, Re-answer)
- Forms (Import book, Revise answer)
- Confirmations (Bulk re-answer)

**Dialog anatomy**:
- Overlay (rgba(0,0,0,0.5))
- Card (centered, max-width 500px)
- Header (title, close button)
- Body
- Footer (Cancel + primary action)

**Dialog behavior**:
- Click outside to close (with confirmation if dirty)
- ESC to close
- Focus trap (keyboard nav stays inside)
- Restore focus on close

## Tables

Tables are the primary data display for Library, Cache, and
Benchmarks.

**Table anatomy**:
- Header row (sticky on scroll, with sort indicators)
- Body rows
- Optional pagination footer

**Cell padding**: 12px horizontal, 8px vertical

**Row state**:
- Default: white background
- Hover: light gray (#f9fafb)
- Selected: light blue (#dbeafe)
- Stale: light yellow (#fef3c7) — for stale cache entries

**Column priorities** (when space is tight):
1. Primary (e.g. qid, book_id) — never hidden
2. Secondary (e.g. subject) — never hidden
3. Tertiary (e.g. validation_score) — hidden on `md`, shown
   on `lg+`
4. Actions — always shown

## Navigation

**Top bar**:
- Logo: text "MedRack" + simple book icon
- Version: small text "v0.3.0" in the top-right
- Settings: gear icon
- Help: question-mark icon

**Side nav**:
- Library (book icon)
- Generate (pencil icon)
- Cache (database icon)
- Benchmarks (chart icon)
- Logs (file-text icon)
- Settings (gear icon)

**Active item**: bold + colored accent bar on the left.

**Breadcrumbs**: not needed (the side nav is enough).

## Color hierarchy

The color palette is muted. The app is for medical work, not
consumer entertainment.

**Primary palette** (gray + blue accent):
- Background: #ffffff (white)
- Surface: #f9fafb (very light gray)
- Border: #e5e7eb (light gray)
- Text primary: #111827 (almost black)
- Text secondary: #6b7280 (gray)
- Text disabled: #9ca3af (light gray)
- Accent: #2563eb (blue) — for primary actions, links
- Accent hover: #1d4ed8 (darker blue)

**Status colors** (used sparingly):
- Success: #16a34a (green) — for "passed", "succeeded"
- Warning: #ca8a04 (amber) — for "warn", "stale"
- Error: #dc2626 (red) — for "failed", "fail"

**Use status colors only for status**. Don't use green/amber
red for decorative purposes. Don't use color as the only
signal — always pair with text or icon.

## Icons

Use a consistent icon set. Recommendations:
- **Lucide** (lucide.dev) — open-source, 1000+ icons
- **Heroicons** (heroicons.com) — Tailwind's icon set
- **Phosphor** (phosphoricons.com) — flexible, multiple weights

Icons should be:
- 16-24px for inline use
- 24-32px for navigation
- Outlined (not filled) for nav, filled for active state

**Required icons**:
- Book (Library)
- Pencil (Generate)
- Database (Cache)
- Chart (Benchmarks)
- FileText (Logs)
- Gear (Settings)
- Upload (Import)
- Download (Download PDF)
- Refresh (Retry / Refresh)
- Trash (Remove)
- CheckCircle (Pass)
- AlertCircle (Warn / Fail)

## Loading indicators

Loading should be quiet. Don't show spinners for fast
operations (< 200ms).

**Inline loading** (for refreshes, button actions):
- Small spinner (16px) next to the action
- Or a skeleton placeholder

**Page-level loading** (for initial page load):
- Skeleton placeholders matching the page layout
- No spinner (feels faster)

**Long-running loading** (for ingestion, generation,
benchmarks):
- Full-page modal overlay
- Progress text: "Ingesting Park PSM V4... (this may take a
  few minutes)"
- "Cancel" button (if applicable; v1 doesn't support
  cancellation for generation, so don't show it)
- Background polling (no need for the user to do anything)

**Generation in progress** (5-30s):
- Inline spinner next to the answer area
- Text: "Generating answer... (this may take up to 30 seconds)"
- Disable the "Generate" button (no double-submit)
- Allow the user to navigate away (the request continues
  server-side; on return, refetch the result)

## Empty states

Every page should have a useful empty state.

**Empty state anatomy**:
- Illustration (optional, simple)
- Headline (what's missing)
- Body (why it's missing, in 1-2 sentences)
- CTA (what to do next)

**Examples**:
- Library empty: "No books yet." + "Click 'Import book' to
  add your first textbook." + [Import book] button
- Cache empty: "No cached answers yet." + "Generate an
  answer to see it here." + [Generate] button
- Benchmarks empty: "No benchmarks yet." + "Benchmarks are
  run by the operator from the command line. See the
  documentation for how to run a benchmark."

## Error states

**Inline error** (for one row / one field):
- Red text below the field
- Red border on the field
- "What happened" + "How to fix" in 1-2 sentences

**Page error** (for failed page load):
- Red banner at the top of the page
- Icon (AlertCircle)
- Title: "Couldn't load [resource name]"
- Body: the error message
- "Retry" button

**System error** (backend unreachable):
- Full-page error screen
- Title: "Backend not reachable"
- Body: "MedRack is not running at {API_URL}. Check the
  backend status and try again."
- "Retry" button

## Responsive behavior

The MedRack frontend is desktop-first. The user is one
operator on one machine. Mobile is not a primary target.

**Breakpoints**:
- `sm` (640px) — phone, NOT a primary target. The app should
  still load but the UX may be degraded.
- `md` (768px) — small tablet. Some columns may be hidden;
  side nav collapses to icons.
- `lg` (1024px) — desktop. Default layout.
- `xl` (1280px) — wide desktop. More columns visible.

**Mobile considerations**:
- The user is a single operator on a desktop. They will not
  be on mobile in a clinical setting. Don't optimize for
  mobile; just don't break it.
- Tables become stacked cards on `sm` (one card per row).
- Dialogs become full-screen on `sm`.
