"""Per-user rate limits with an IP fallback, and the key re-fetch cooldown
(PLAN #12 and the S2 known gaps; ARCHITECTURE.md §9 "Abuse").

- Signed in, a caller is limited on the verified token's `sub`, so people
  behind one address (a university's NAT) never use up each other's
  budget, and anonymous use from that address does not touch theirs.
- Anonymous callers keep the per-IP limit.
- A token that fails verification is charged to its IP in a budget of its
  own; beyond it the answer is 429.
- A token naming a key id nobody has published makes the engine fetch the
  keys again at most once a minute, whoever asks.

Tokens are minted with throwaway keys (test_accounts.py); all text is
synthetic.
"""

from __future__ import annotations

import uuid

import pytest

import test_accounts as ta
from researchly_service import accounts
from researchly_service import settings as settings_mod

FULL = "/v1/analyze"
LIVE = "/v1/check-paragraphs"
FILE = "/v1/analyze-file"
TEXT = "Results\n\nThe effect was large."


class CountingJWKS(ta.InMemoryJWKS):
    """The real client, minus the network; counts every key-set download."""

    def __init__(self, jwks=ta.JWKS, down=False):
        super().__init__(jwks=jwks, down=down)
        self.fetches = 0

    def fetch_data(self):
        self.fetches += 1
        return super().fetch_data()


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def signed(make_client):
    """A client with accounts on; returns (client, jwks, clock)."""
    def _make(jwks=None, **kw):
        c = make_client(supabase_url=ta.URL,
                        supabase_publishable_key=ta.PUBLISHABLE, **kw)
        jwks = jwks or CountingJWKS()
        clock = Clock()
        c.app.state.accounts = accounts.Accounts(
            ta.URL, ta.PUBLISHABLE, jwks_client=jwks,
            fetch=ta.FakeSupabase({}), clock=clock)
        return c, jwks, clock
    return _make


def user_token(user=None, **kw):
    return ta.token(sub=user or str(uuid.uuid4()), **kw)


def call(c, path=FULL, tok=None, ip="203.0.113.7"):
    headers = {"x-forwarded-for": ip}
    if tok is not None:
        headers["authorization"] = f"Bearer {tok}"
    if path == LIVE:
        return c.post(path, json={"revision": 1, "paragraphs": [
            {"id": "p", "text": "The effect was large."}]}, headers=headers)
    if path == FILE:
        headers.update({"content-type": "application/octet-stream",
                        "x-researchly-filename": "chapter.md"})
        return c.post(path, content=TEXT.encode(), headers=headers)
    return c.post(path, json={"content": TEXT}, headers=headers)


def limited(r, by="address"):
    assert r.status_code == 429, r.text
    body = r.json()["error"]
    assert body["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert by in body["message"]
    return True


# --- per user, with the IP as the fallback --------------------------------------

def test_people_behind_one_address_each_have_their_own_budget(signed):
    c, _, _ = signed(trusted_proxy_hops=1, rate_limit_per_min=1,
                     user_rate_limit_per_min=2)
    a, b = user_token(), user_token()
    assert [call(c, tok=a).status_code for _ in range(2)] == [200, 200]
    assert limited(call(c, tok=a), by="your account")
    # B, at the same address, is not throttled by A ...
    assert [call(c, tok=b).status_code for _ in range(2)] == [200, 200]
    # ... and anonymous use from it has the per-IP budget, apart.
    assert call(c).status_code == 200
    assert limited(call(c))
    # Anonymous use spent the address's budget: signed-in users carry on.
    assert limited(call(c, tok=b), by="your account")      # B's own two
    assert call(c, tok=user_token()).status_code == 200


def test_a_user_is_one_budget_across_addresses(signed):
    c, _, _ = signed(trusted_proxy_hops=1, user_rate_limit_per_min=2)
    me = str(uuid.uuid4())
    assert call(c, tok=user_token(me), ip="198.51.100.1").status_code == 200
    assert call(c, tok=user_token(me), ip="198.51.100.2").status_code == 200
    assert limited(call(c, tok=user_token(me), ip="198.51.100.3"),
                   by="your account")


def test_full_live_and_upload_budgets_are_separate_per_user(signed):
    c, _, _ = signed(user_rate_limit_per_min=1, user_live_rate_limit_per_min=2,
                     user_upload_rate_limit_per_min=1)
    me = user_token()
    assert call(c, FULL, me).status_code == 200
    assert limited(call(c, FULL, me), by="your account")
    assert [call(c, LIVE, me).status_code for _ in range(2)] == [200, 200]
    assert limited(call(c, LIVE, me), by="your account")
    assert call(c, FILE, me).status_code == 200
    assert limited(call(c, FILE, me), by="your account")
    # analyze-word shares the full check's budget.
    r = c.post("/v1/analyze-word", json={"paragraphs": [{"text": "Fine."}]},
               headers={"authorization": f"Bearer {me}"})
    assert limited(r, by="your account")


def test_signed_in_requests_do_not_spend_the_address_budget(signed):
    c, _, _ = signed(trusted_proxy_hops=1, rate_limit_per_min=1,
                     user_rate_limit_per_min=5)
    for _ in range(3):
        assert call(c, tok=user_token()).status_code == 200
    assert call(c).status_code == 200                # the IP's one, unspent


def test_a_zero_user_limit_means_unlimited(signed):
    c, _, _ = signed(rate_limit_per_min=1, user_rate_limit_per_min=0)
    me = user_token()
    assert all(call(c, tok=me).status_code == 200 for _ in range(4))


def test_without_accounts_a_token_changes_nothing(make_client):
    """S1 behaviour: no Supabase, so the token is ignored and the IP decides."""
    c = make_client(rate_limit_per_min=1, user_rate_limit_per_min=50)
    assert call(c, tok="whatever").status_code == 200
    assert limited(call(c, tok="anything-else"))


def test_other_routes_stay_per_address(signed):
    c, jwks, _ = signed(rate_limit_per_min=1, user_rate_limit_per_min=50)
    h = {"authorization": f"Bearer {user_token()}"}
    assert c.get("/v1/rules", headers=h).status_code == 200
    assert limited(c.get("/v1/rules", headers=h))
    assert c.get("/v1/health", headers=h).status_code == 200   # never limited
    assert jwks.fetches == 0                         # no token was checked


def test_the_token_is_checked_once_per_request(signed, monkeypatch):
    c, _, _ = signed()
    seen = []
    real = accounts.Accounts.verify

    def spy(self, tok):
        seen.append(1)
        return real(self, tok)
    monkeypatch.setattr(accounts.Accounts, "verify", spy)
    assert call(c, tok=user_token()).json()["signed_in"] is True
    assert len(seen) == 1


# --- bad tokens are charged to their address ----------------------------------------

def test_bad_tokens_are_charged_to_the_address(signed):
    c, _, _ = signed(trusted_proxy_hops=1, rate_limit_per_min=2,
                     user_rate_limit_per_min=50)
    bad = ta.token(key=ta.STRANGER_KEY)
    for _ in range(2):
        r = call(c, tok=bad)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
        assert r.headers["www-authenticate"].startswith("Bearer")
    assert limited(call(c, tok=bad))
    assert limited(call(c, tok="garbage"))
    # A valid token at that address is still served: it is never refused
    # because of someone else's forgeries.
    assert call(c, tok=user_token()).status_code == 200
    # Another address is unaffected, and anonymous use has its own budget.
    assert call(c, tok=bad, ip="198.51.100.9").status_code == 401
    assert call(c).status_code == 200


def test_keys_down_is_not_charged(signed):
    c, _, _ = signed(jwks=CountingJWKS(down=True), rate_limit_per_min=1)
    for _ in range(3):
        r = call(c, tok=user_token())
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "auth_unavailable"


# --- the key re-fetch cooldown -----------------------------------------------------

def test_unknown_key_ids_refetch_at_most_once_a_minute(signed):
    c, jwks, clock = signed()
    assert call(c, tok=user_token()).status_code == 200
    assert jwks.fetches == 1                          # the first download
    r = call(c, tok=user_token(kid="nope-1"))
    assert r.status_code == 401                       # re-fetched, not there
    assert jwks.fetches == 2
    for i in range(20):                               # a flood of new ids
        r = call(c, tok=user_token(kid=f"nope-{i + 2}"))
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "auth_unavailable"
    assert jwks.fetches == 2
    # Known keys are unaffected meanwhile.
    assert call(c, tok=user_token()).status_code == 200
    clock.now += 61
    assert call(c, tok=user_token(kid="nope-x")).status_code == 401
    assert jwks.fetches == 3


def test_a_rotated_key_is_picked_up_after_the_cooldown(signed):
    jwks = CountingJWKS(jwks={"keys": [ta.JWKS["keys"][0]]})
    c, _, clock = signed(jwks=jwks)
    assert call(c, tok=user_token(kid="nope")).status_code == 401   # refetch
    # Supabase publishes a new key (the EC one) moments later.
    jwks._data = ta.JWKS
    new = user_token(key=ta.EC_KEY, kid="ec-1", alg="ES256")
    r = call(c, tok=new)
    assert r.status_code == 503 and "minute" in r.json()["error"]["message"]
    clock.now += 61
    assert call(c, tok=new).status_code == 200


def test_unknown_key_ids_in_the_cooldown_are_charged(signed):
    c, _, _ = signed(trusted_proxy_hops=1, rate_limit_per_min=3)
    assert call(c, tok=user_token(kid="a")).status_code == 401
    assert call(c, tok=user_token(kid="b")).status_code == 503
    assert call(c, tok=user_token(kid="c")).status_code == 503
    assert limited(call(c, tok=user_token(kid="d")))


def test_cooldown_holds_across_threads():
    """Many workers meeting an unknown key at once: one download."""
    import threading

    jwks = CountingJWKS()
    accts = accounts.Accounts(ta.URL, ta.PUBLISHABLE, jwks_client=jwks,
                              fetch=ta.FakeSupabase({}))
    accts.verify(ta.token())                          # cache warm
    errors = []

    def go(i):
        try:
            accts.verify(ta.token(kid=f"unknown-{i}"))
        except accounts.AuthError as e:
            errors.append(e.status)
    threads = [threading.Thread(target=go, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert jwks.fetches == 2 and accts.refetches == 1
    assert sorted(errors) == [401] + [503] * 15


@pytest.mark.parametrize("header", [
    {"alg": "RS256", "typ": "JWT"},                         # no kid
    {"alg": "RS256", "kid": "k" * 300},                     # absurd kid
    {"alg": "RS256", "kid": 7},                             # not a string
])
def test_tokens_without_a_usable_key_id_never_fetch(header):
    import base64
    import json

    def part(obj):
        raw = json.dumps(obj).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    jwks = CountingJWKS()
    accts = accounts.Accounts(ta.URL, ta.PUBLISHABLE, jwks_client=jwks,
                              fetch=ta.FakeSupabase({}))
    # Built by hand: PyJWT itself refuses to write some of these headers.
    tok = f"{part(header)}.{part({'sub': ta.USER})}.c2ln"
    with pytest.raises(accounts.AuthError) as e:
        accts.verify(tok)
    assert e.value.status == 401 and jwks.fetches == 0


# --- operator settings --------------------------------------------------------------

def test_user_limits_from_the_environment(monkeypatch):
    for name in ("RESEARCHLY_USER_RATE_LIMIT_PER_MIN",
                 "RESEARCHLY_USER_LIVE_RATE_LIMIT_PER_MIN",
                 "RESEARCHLY_USER_UPLOAD_RATE_LIMIT_PER_MIN"):
        monkeypatch.delenv(name, raising=False)
    s = settings_mod.load()
    assert (s.user_rate_limit_per_min, s.user_live_rate_limit_per_min,
            s.user_upload_rate_limit_per_min) == (30, 120, 10)
    monkeypatch.setenv("RESEARCHLY_USER_RATE_LIMIT_PER_MIN", "45")
    monkeypatch.setenv("RESEARCHLY_USER_LIVE_RATE_LIMIT_PER_MIN", "200")
    monkeypatch.setenv("RESEARCHLY_USER_UPLOAD_RATE_LIMIT_PER_MIN", "-3")
    s = settings_mod.load()
    assert (s.user_rate_limit_per_min, s.user_live_rate_limit_per_min,
            s.user_upload_rate_limit_per_min) == (45, 200, 0)


def test_deploy_manifest_sets_the_user_limits():
    from pathlib import Path
    yaml = (Path(__file__).resolve().parent.parent / "deploy"
            / "cloudrun.service.yaml").read_text(encoding="utf-8")
    for name in ("RESEARCHLY_USER_RATE_LIMIT_PER_MIN",
                 "RESEARCHLY_USER_LIVE_RATE_LIMIT_PER_MIN",
                 "RESEARCHLY_USER_UPLOAD_RATE_LIMIT_PER_MIN"):
        assert f"name: {name}" in yaml, name
