# ADR 0006: Public entry and the authenticated product client

Status: Accepted for Phase 10 under the user's vertical-slice and public-entry brief
Date: 2026-09-08

## Context

The authentication, canonical CSV and transaction-understanding APIs already exist.
The frontend needs one usable journey and a public explanation of LedgerX without
claiming that planned behavioral analysis is available.

## Decision

The latest Phase 10 scope completes only public entry and authentication. Existing
private-client work below is preserved in progress, not declared complete by this
public-side refinement.

- `/` is a public, prerendered landing page. Its explicitly synthetic interactive
  example demonstrates current merchant/category presentation. It does not query
  private transactions or supply fixtures to authenticated screens.
- Spending-change, personal-baseline, recurring-commitment and unusual-activity
  previews are explicitly labeled planned intelligence with illustrative data.
  Their predefined values demonstrate concepts, not implemented analytics. No
  authoritative calculations or additional transaction attributes are inferred.
- `/login` and `/register` retain the existing accessible form. Registration calls
  the existing register API, then the existing login API; register itself still
  creates no session. If login fails after registration, the form offers sign-in.
- `/app` and `/app/transactions` use the same bounded transaction-history component.
  `/app/import` uploads; `/app/import/{id}` previews/finalizes;
  `/app/transactions/{id}` reads detail and corrects categories. Earlier import
  and transaction-detail URLs redirect to their corresponding product URLs.
- Next.js rewrites `/api/v1/*` to the existing FastAPI service. The server-only
  `LEDGERX_API_ORIGIN` defaults to loopback for native development and is
  `http://api:8000` in Compose. No client-selectable destination or custom session
  proxy is introduced. Cookie and Origin/CSRF behavior remain backend-authoritative.
- One typed client validates API responses with Zod, sends same-origin credentials,
  disables response caching and obtains CSRF before each authenticated mutation.
  Arbitrary backend error text is not rendered. CSRF conflicts ask for a retry;
  mutations are never automatically replayed after an uncertain response.
- Session restoration gates private rendering. A generation counter discards stale
  identity responses. Private trees are keyed by user; expiry/logout clears them.
  Cross-tab sign-in/logout is announced without identifiers through BroadcastChannel;
  returning to a visible tab revalidates identity before showing retained content.
- CSV bytes and upload UUID keys stay in component memory for retries. A page reload
  can lose an uncertain upload, so a before-unload warning protects pending attempts.
  No raw CSV or auth material goes into browser storage. The transport uses a neutral
  valid filename because the original filename is not required by the domain.
- Finalize uses the immutable import UUID as its operation key, stable across reloads.
  Backend key scope and atomicity remain unchanged. Existing externally finalized
  batches are read back on conflict rather than treated as new imports.
- Category corrections use the exact quoted server version in `If-Match`. Any
  failed/uncertain save triggers a read-back before another correction. Clearing a
  correction sends null. Facts remain immutable.
- Money is displayed directly from decimal strings without arithmetic or rounding.
  History uses 25-row cursor pages in backend record order, not chronological order.
  No client aggregation or analytics is introduced.

## Alternatives and consequences

A second authentication scheme or browser token store would violate the existing
security model. Direct cross-origin fetch is supported by the backend but would add
public environment configuration; the bounded same-origin rewrite keeps browser
requests simple. A large UI framework and animation library are unnecessary here.

The public design evolves the existing emerald/cool-neutral identity with a
self-hosted Geist font. Native semantic controls, keyboard-scrollable tables,
visible focus and reduced-motion support take priority over marketing effects.

There is no imports-list API, date sorting/filtering, global transaction count,
duplicate detection across uploads or import recovery after a lost upload response
and navigation. Preview URLs remain resumable for 24 hours. Planned baselines,
recurring analysis, financial-health scores and risk features are disclosed as
future direction only. Production launch/security gates in earlier ADRs still apply.

## Verification

Component/transport tests cover public entry, forms, redirects, session gating and
stale responses, upload recovery, validation, explicit finalization, cursor paging,
exact amounts and optimistic category correction. Actual Docker/browser checks and
the final command results are recorded in `docs/STATUS.md`.
