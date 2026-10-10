# User-authorized clients

**No separate agent integration is claimed.** M14c supports normal user API
access tokens; a named agent integration is outside its required scope.
The pinned IdP supports module-owned confidential registrations, not a general
external public-client registration API. An arbitrary external agent without its
own approved registration is unavailable; do not share Explorer credentials to
make it work. Independent machine identities, password automation and Device
Authorization Grant are outside this initial scope.

A compatible NS8 application may register its own client under its own module
identity and bound user domain. It must request its exact callback, C1's persistent
API audience, `c1_principal_kind=human`, Authorization Code with S256 PKCE, and
securely keep credentials/tokens on its own server. Confirm that the provider
policy and client actually use PKCE, explicit user authorization, correct access
tokens and refresh handling. The current `register-client` API does not expose a
PKCE-enforcement or consent configuration option: record that platform dependency
rather than widening the claim PR into client-management features.

Refresh only according to provider policy. When refresh is no longer available,
require renewed user authorization. Never retain a user's password, copy browser
cookies, export tokens from Explorer or copy its confidential client secret.

The authenticated account's **current C1 permissions** apply. Audit records the
account as actor; `on_behalf_of` does not supply a separately authenticated machine
identity. OAuth does not automatically reduce privileges per agent. A static
human classification identifies the user-authentication contract, not proof of
manual work. Prefer a restricted automation account and never grant administrative
or reviewer permissions automatically. The same account submitting and approving
is one principal; C1's independent-review check continues to reject self-approval.

Stopping issuance, denying refresh, changing C1 permissions and invalidating an
already-issued access token are distinct operations. Client disable or secret
rotation does not promise immediate revocation of every locally validated JWT.

Release verification must exercise one named client, exact registration/callback,
audience and classification, secure storage, refresh failure/reauthorization,
permission removal, audit attribution and independent review on real services.
