---
name: frontend-ui
component-scope: VoyageMind AI React + TypeScript + Vite client
description: Design system, animation philosophy, and frontend conventions for the VoyageMind AI cinematic travel planner.
version: 2.0.0
---

# VoyageMind Frontend Skill

## Core Operational Directives
* **Type Safety First:** Every API payload and response is modeled in `src/types.ts` and imported where used.
* **API Base URL:** Use `import.meta.env.VITE_API_BASE_URL` (default `http://localhost:8000`).
* **Async Handling:** Wrap API calls in `try/catch`; render user-readable error messages and keep the UI responsive.
* **Build Verification:** Run `npm run build` before considering any frontend change complete.

---

## Applied Design Systems & Skills

This frontend intentionally blends several modern UI philosophies into a cohesive, premium travel experience.

### Unlumen UI
* **Animated components:** every interactive element should feel alive — buttons glow, chips shimmer, cards tilt.
* **Glowing badges:** status pills, category tags, and active states use soft colored glows.
* **Shimmering text:** hero headlines and loading states can use animated gradient text.
* **Tilt cards:** glass cards respond to mouse position with subtle 3D tilt.
* **Magnetic buttons:** primary CTAs gently pull toward the cursor on hover.
* **Text reveal:** assistant messages enter with a staggered character or word reveal.
* **Orbiting elements:** decorative icons or loading indicators can orbit a central point.

### Magic UI
* **Particles & ambient motion:** subtle background particles, floating orbs, and starfields add depth without distraction.
* **Animated backgrounds:** use gradients, aurora, and radial glows that shift slowly.
* **Number counters:** budget and cost figures animate when they first appear.
* **Shimmer buttons:** CTAs have a sweeping light reflection on hover.
* **Confetti / celebration:** booking or completion moments trigger a delightful burst.

### Smooth UI
* **Spring-driven motion:** prefer `type: "spring"` over duration-based tweens for organic, interruptible animations.
* **Consistent easing:** use custom cubic-bezier curves; avoid default `ease-in` for UI motion.
* **Staggered reveals:** lists and groups of elements cascade in with 30–80 ms delays.
* **Reduced motion:** all motion must respect `prefers-reduced-motion`.

### Retro UI
* **Grain & scanlines:** a subtle film-grain overlay and optional scanlines give a nostalgic, cinematic texture.
* **Neon accents:** cyan, violet, and amber glows reference vintage synthwave / sci-fi aesthetics.
* **Bold outlines:** high-contrast borders and retro-style badges on key metrics.
* **Monospace accents:** use monospace for data-heavy microcopy (costs, durations, dates).

### Emil Kowalski Design Engineering
* **Taste is trained:** every animation and spacing decision should feel intentional, not arbitrary.
* **Unseen details compound:** small press feedback, correct transform-origin, and precise durations add up to a premium feel.
* **Never animate from `scale(0)`:** entrances start from `scale(0.9–0.95)` with `opacity: 0`.
* **Never use `ease-in` on UI elements:** use `ease-out` or custom curves for responsive motion.
* **Keep UI animations under 300 ms:** modals/drawers can stretch to 500 ms; marketing moments can be longer.
* **Buttons must feel responsive:** apply `scale(0.97)` on `:active` with a 100–160 ms transition.
* **Use CSS transitions for dynamic UI:** toasts, chips, and rapidly-triggered states should be interruptible.
* **Only animate `transform` and `opacity`:** these are GPU-accelerated and avoid layout thrash.
* **Hover gating:** wrap hover effects behind `@media (hover: hover) and (pointer: fine)`.

### Taste Skills / Impeccable Polish
* **Visual rhythm:** maintain consistent spacing (multiples of 4) and typographic hierarchy.
* **Color discipline:** limit the palette to cosmic dark, cyan glow, violet glow, amber accents, and white text.
* **Micro-copy:** labels and helper text are friendly, concise, and action-oriented.
* **Empty states:** always provide a graceful fallback — default activities, mock transit, and explanatory notes.
* **Conversion clarity:** the booking CTA is always visible on the itinerary screen.

---

## Component Conventions
1. **Functional Components:** all UI components are React function components with explicit prop interfaces.
2. **Props Naming:** align prop names with backend schemas (`TravelPlanRequest`, `MasterTravelItinerary`).
3. **Styling:** use Tailwind CSS utility classes; extract reusable patterns into `src/lib/utils.ts` with `cn()`.
4. **Animation:** use `framer-motion` for orchestrated animations; prefer `transform` strings for GPU acceleration under load.
5. **Accessibility:** include focus rings, ARIA labels, keyboard support, and `prefers-reduced-motion` fallbacks.

---

## Animation Tokens
```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--duration-fast: 150ms;
--duration-base: 250ms;
--duration-slow: 500ms;
```

---

## Verification Checklist
Before submitting frontend changes, verify:
- [ ] `npm run build` completes with zero TypeScript errors.
- [ ] The conversational wizard still submits a valid `TravelPlanRequest`.
- [ ] The itinerary view renders all days, transit, stays, and activities.
- [ ] Animations respect `prefers-reduced-motion`.
- [ ] No inline styles are used for layout (Tailwind + CSS variables only).
