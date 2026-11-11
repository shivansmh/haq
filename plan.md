# Haq T5 Frontend Plan

## Outcome
A mobile-first React/Vite frontend lets a stranger complete the failed-payment golden path using mock data, while preserving the API contract for integration with the FastAPI backend.

## Design

Three possible directions considered:

- **Civic ledger** (0.06): dense public-service utility, structured tables, restrained color.
- **Quiet confidence** (0.07): warm paper background, ink typography, one trust color, progressive disclosure.
- **Fintech dashboard** (0.05): dark chrome, bright metrics, card-heavy presentation.

Chosen: **Quiet confidence**.

- **Design movement:** editorial civic-tech with a paper-like surface and ledger-inspired evidence panels.
- **Core principles:** explain before asking; show uncertainty instead of hiding it; one primary action per screen; keep personal data transient.
- **Color philosophy:** deep ink for authority, warm paper for approachability, indigo for action, amber for unresolved research, green only for confirmed parsing—not legal certainty.
- **Layout paradigm:** a narrow reading column with a persistent step rail on larger screens; each screen starts with a plain-language question and ends with one next action.
- **Signature elements:** indigo left rule on active cards, numbered evidence trace, small uppercase source labels.
- **Interaction:** progressive disclosure for working and sources; every destructive/reset action is visible and reversible within the session.
- **Typography:** system sans for UI, Georgia for large editorial headings.
- **Brand essence:** “Know what happened. See what the rule says. Decide what to do next.” Calm, candid, practical.
- **Brand voice:** “The rule says…” and “You could…”; never “you are entitled” or “guaranteed”.
- **Wordmark:** a compact “H” mark formed from two offset ledger strokes, represented in CSS so the app has no external asset dependency.
- **Signature color:** indigo `#3949ab`, used sparingly for action and active state.

## Implementation

- `web/src/App.tsx`: in-memory navigation/state and T5 screens.
- `web/src/api.ts`: mock-first adapter with real API methods matching the contract.
- `web/src/components.tsx`: shared disclaimer, stamp, range amount, trace, source, confidence and state components.
- `web/src/styles.css`: responsive phone-first design system, WCAG-conscious contrast, 44px controls.
- `web/public/manus-routes.json`: route manifest for the SPA entry route.

The frontend never persists uploads or user-entered data. Reloading the page starts a fresh session. The mock path uses the contract's demo fixture and clearly labels every result as `UNVERIFIED RULE`.
