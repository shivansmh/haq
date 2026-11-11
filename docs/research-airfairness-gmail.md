# Haq redesign notes: inbox sweep and consent

## Product pattern

The public airfairness homepage uses a direct promise, one dominant action, and a visible sweep narrative: connect an inbox, find relevant records, evaluate eligibility, and help the user act. Haq adopts that interaction shape without copying its branding or claims. Haq's version is intentionally user-filed: it finds likely payment and dues events, shows the source and working, and prepares a draft the user controls.

Source: https://www.airfairness.com/

## Consent and data boundary

The Gmail flow requests read-only access to Gmail and explains the exact purpose before redirecting to Google. Email content is processed transiently; the product does not need to retain message bodies or attachments. A Disconnect action revokes the Google token and clears the Haq session. This is a product promise that must remain aligned with the deployed privacy policy.

Source: https://www.airfairness.com/terms

## OAuth implementation

Google's web-server OAuth guidance recommends a random `state` value for CSRF protection, `access_type=offline` when a refresh token is needed, and an exact registered redirect URI. Haq uses these controls. The authorization code is exchanged by the backend, never by the browser, and the resulting access/refresh token is kept in server-side session memory for this demo deployment.

Source: https://developers.google.com/identity/protocols/oauth2/web-server

## Gmail API behavior

The Gmail `users.messages.list` endpoint supports a Gmail search query and returns message IDs; message details are fetched separately. Haq uses `gmail.readonly` for the sweep and requests only the bounded search result set configured by the backend.

Source: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list

## Production requirement

Gmail read scopes are restricted/sensitive data access. Google requires OAuth verification for applicable apps, and server-side handling of restricted-scope data can require a security assessment. The deployed app must therefore complete Cloud Console consent-screen configuration, authorized-domain setup, privacy-policy publication, and any verification that Google requires before broad public use.

Source: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
