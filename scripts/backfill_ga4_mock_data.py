#!/usr/bin/env python3
"""
Seeds a real GA4 property with realistic session traffic via the
Measurement Protocol — so Explore/Reports aren't empty while you build.

GA4's Measurement Protocol only accepts events backdated up to ~71-72
hours; anything older is silently dropped (a Google-side limit, not a
script limitation — see README §7). This script always seeds a rolling
window ending now, so re-run it every 1-2 days for continuous history,
or just click through the live site yourself for real, non-backdated
Realtime activity.

Usage:
    pip install -r scripts/requirements.txt   # stdlib only — nothing to install
    python3 scripts/backfill_ga4_mock_data.py --measurement-id G-XXXXXXXXXX --api-secret YOUR_SECRET --validate
    python3 scripts/backfill_ga4_mock_data.py --measurement-id G-XXXXXXXXXX --api-secret YOUR_SECRET --live
"""
import argparse
import json
import random
import time
import urllib.request
import urllib.parse
import uuid
from collections import Counter

DEBUG_URL = "https://www.google-analytics.com/debug/mp/collect"
LIVE_URL = "https://www.google-analytics.com/mp/collect"

# Matches the Lookup Table in the GTM container (Folder 5).
LEAD_SCORE = {
    "view_item": 2,
    "add_to_cart": 10,
    "begin_checkout": 20,
    "purchase": 50,
    "contact_form_submit": 15,
}

BASE = "https://solstice-outdoor.netlify.app"  # cosmetic only — page_location on seeded events

CATALOG = [
    {"id": "SOL-001", "name": "Ridgeline Trail Shell", "price": 148.00},
    {"id": "SOL-002", "name": "Switchback Softshell", "price": 129.00},
    {"id": "SOL-003", "name": "Basecamp Down Vest", "price": 118.00},
    {"id": "SOL-004", "name": "Traverse Hiking Boot", "price": 142.00},
    {"id": "SOL-005", "name": "Lowline Trail Runner", "price": 98.00},
    {"id": "SOL-006", "name": "Alpine Wool Beanie", "price": 28.00},
    {"id": "SOL-007", "name": "Contour 32L Daypack", "price": 112.00},
    {"id": "SOL-008", "name": "Summit 65L Expedition Pack", "price": 148.00},
    {"id": "SOL-009", "name": "Driftline Merino Tee", "price": 68.00},
    {"id": "SOL-010", "name": "Thermalayer Base Set", "price": 84.00},
]

# Traffic mix — matches the interview prep numbers: cpc 30 / direct 25 /
# paid_social 20 / email 15 / affiliate 10 (%).
CHANNELS = [
    ("google", "cpc", "search_hiking_boots", 0.30),
    ("(direct)", "(none)", "(not set)", 0.25),
    ("facebook", "paid_social", "aw25_carousel", 0.20),
    ("klaviyo", "email", "weekly_newsletter", 0.15),
    ("trailguide", "affiliate", "partner_q4", 0.10),
]


def pick_channel():
    r = random.random()
    cum = 0.0
    for source, medium, campaign, weight in CHANNELS:
        cum += weight
        if r <= cum:
            return source, medium, campaign
    return CHANNELS[-1][:3]


def landing_url(source, medium, campaign):
    """
    GA4 derives session source/medium by parsing UTM parameters off the
    landing page URL — the same mechanism whether the hit is client-side
    or Measurement Protocol. Sending "source"/"medium" as bare custom
    params (the previous version of this script) does nothing; GA4 does
    not treat those as attribution signals. Real utm_source/utm_medium/
    utm_campaign query params on page_location are what it actually reads.
    """
    if source == "(direct)":
        return BASE + "/"
    qs = urllib.parse.urlencode({
        "utm_source": source, "utm_medium": medium, "utm_campaign": campaign,
    })
    return f"{BASE}/?{qs}"


def common(client_id, session_id, source, medium, campaign, overrides=None):
    """Base params every event carries: page/session context."""
    base = {
        "page_location": landing_url(source, medium, campaign),
        "session_id": session_id,
        "engagement_time_msec": "100",
    }
    if overrides:
        base.update(overrides)
    return base


def build_session(profile, now_us, window_us):
    """
    Builds one session's event sequence based on its profile:
      bounce   — page_view only
      browse   — page_view, view_item_list, 1-2x view_item
      abandon  — browse path + add_to_cart, then leaves
      lead     — reaches checkout, submits the lead form instead of buying
      purchase — full funnel through purchase, 30% chance of a second lead

    Funnel shape as a share of all sessions (matches interview prep numbers):
        page_view      100%
        view_item       ~93%
        add_to_cart     ~38%
        begin_checkout  ~13%
        purchase        ~11.5%
    """
    client_id = f"{uuid.uuid4().hex[:10]}.{random.randint(1000000000, 1999999999)}"
    source, medium, campaign = pick_channel()
    session_offset = random.randint(0, window_us)
    t = now_us - window_us + session_offset  # backdated within the rolling window
    session_id = str(t // 1_000_000)  # GA4 convention: epoch seconds as session_id

    events = []
    score = 0

    def push(name, overrides=None, dt_us=0):
        nonlocal t
        t += dt_us
        events.append({
            "name": name,
            "params": common(client_id, session_id, source, medium, campaign, overrides),
            "timestamp_micros": t,
        })

    # session_start anchors the session; GA4 reads UTM attribution off this
    # hit's page_location. page_view on the same landing page follows it —
    # every subsequent event in the session uses a plain internal path
    # instead, matching how a real visit only tags the entry page.
    push("session_start")
    push("page_view")

    if profile == "bounce":
        return client_id, events, score

    product = random.choice(CATALOG)
    push("view_item_list", {
        "page_location": BASE + "/shop.html",
        "item_list_id": "all_products", "item_list_name": "All Gear",
        "items": [{"item_id": p["id"], "item_name": p["name"], "price": p["price"]} for p in CATALOG],
    }, dt_us=8_000_000)
    push("view_item", {
        "page_location": BASE + f"/product.html?id={product['id']}",
        "currency": "USD", "value": product["price"],
        "items": [{"item_id": product["id"], "item_name": product["name"], "price": product["price"], "quantity": 1}],
    }, dt_us=15_000_000)
    score += LEAD_SCORE["view_item"]

    if profile == "browse":
        return client_id, events, score

    qty = random.choice([1, 1, 1, 2])
    push("add_to_cart", {
        "page_location": BASE + f"/product.html?id={product['id']}",
        "currency": "USD", "value": product["price"] * qty,
        "items": [{"item_id": product["id"], "item_name": product["name"], "price": product["price"], "quantity": qty}],
    }, dt_us=20_000_000)
    score += LEAD_SCORE["add_to_cart"]

    if profile == "abandon":
        return client_id, events, score

    cart_items = [{"item_id": product["id"], "item_name": product["name"], "price": product["price"], "quantity": qty}]
    cart_value = product["price"] * qty
    push("begin_checkout", {
        "page_location": BASE + "/checkout.html",
        "currency": "USD", "value": cart_value, "items": cart_items,
    }, dt_us=45_000_000)
    score += LEAD_SCORE["begin_checkout"]

    if profile == "lead":
        push("generate_lead", {
            "page_location": BASE + "/",
            "lead_type": "layering_guide", "lead_score": score,
        }, dt_us=12_000_000)
        return client_id, events, score

    # profile == "purchase"
    push("add_payment_info", {
        "page_location": BASE + "/checkout.html",
        "currency": "USD", "value": cart_value, "payment_type": "Card", "items": cart_items,
    }, dt_us=30_000_000)

    shipping = 0 if cart_value > 120 else 9.95
    tax = round(cart_value * 0.08, 2)
    push("purchase", {
        "page_location": BASE + "/thankyou.html",
        "transaction_id": f"SOL-{uuid.uuid4().hex[:10].upper()}",
        "currency": "USD",
        "value": round(cart_value + shipping + tax, 2),
        "shipping": shipping,
        "tax": tax,
        "items": cart_items,
    }, dt_us=25_000_000)
    score += LEAD_SCORE["purchase"]

    if random.random() < 0.30:
        push("generate_lead", {
            "page_location": BASE + "/thankyou.html",
            "lead_type": "post_purchase_newsletter",
            "lead_score": score,
        }, dt_us=5_000_000)

    return client_id, events, score


def build_profiles(total):
    """
    Funnel shape, as a share of all sessions:
        bounce    7%   — page_view only
        browse   54.5%  — view_item(_list), no cart
        abandon  25%   — add_to_cart, no checkout
        lead      2%   — reaches checkout, converts to lead not sale
        purchase 11.5%  — full funnel through purchase
    """
    bounce = round(total * 0.07)
    purchase = round(total * 0.115)
    lead = round(total * 0.02)
    abandon = round(total * 0.25)
    browse = total - bounce - purchase - lead - abandon
    profiles = (["bounce"] * bounce + ["browse"] * browse + ["abandon"] * abandon
                + ["lead"] * lead + ["purchase"] * purchase)
    random.shuffle(profiles)
    return profiles


def post(url, measurement_id, api_secret, body, timeout=20):
    qs = urllib.parse.urlencode({"measurement_id": measurement_id, "api_secret": api_secret})
    req = urllib.request.Request(
        f"{url}?{qs}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def main():
    ap = argparse.ArgumentParser(description="Seed a GA4 property with Solstice demo traffic.")
    ap.add_argument("--measurement-id", required=True, help="G-XXXXXXXXXX")
    ap.add_argument("--api-secret", required=True, help="Measurement Protocol API secret")
    ap.add_argument("--sessions", type=int, default=200, help="Sessions to generate (default 200)")
    ap.add_argument("--seed", type=int, default=None, help="Random seed, for reproducible runs")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate", action="store_true", help="Debug endpoint, records nothing")
    mode.add_argument("--live", action="store_true", help="Actually send the data")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if not args.measurement_id.startswith("G-"):
        print(f"Measurement ID looks wrong: {args.measurement_id} (expected G-XXXXXXXXXX)")
        return 1

    url = DEBUG_URL if args.validate else LIVE_URL
    now_us = int(time.time() * 1_000_000)
    window_us = 71 * 60 * 60 * 1_000_000  # 71-hour rolling window (under the 72h MP limit)
    profiles = build_profiles(args.sessions)

    print(f"\nSolstice GA4 seeder")
    print(f"  property   {args.measurement_id}")
    print(f"  mode       {'VALIDATE (nothing recorded)' if args.validate else 'LIVE'}")
    print(f"  sessions   {len(profiles)}")
    print(f"  window     rolling 71 hours ending now\n")

    tally = Counter()
    problems = 0
    sent = 0

    for i, profile in enumerate(profiles, 1):
        client_id, events, _score = build_session(profile, now_us, window_us)
        for e in events:
            tally[e["name"]] += 1

        # Measurement Protocol accepts up to 25 events per request — one
        # session's events (max ~6 here) always fits in a single call.
        # timestamp_micros at the top level backdates the whole request;
        # per-event timestamps above keep relative ordering for the debug view.
        body = {
            "client_id": client_id,
            "timestamp_micros": events[-1]["timestamp_micros"],
            "events": [{"name": e["name"], "params": e["params"]} for e in events],
        }

        try:
            status, resp_text = post(url, args.measurement_id, args.api_secret, body)
            if args.validate:
                resp = json.loads(resp_text)
                n_issues = len(resp.get("validationMessages", []))
                problems += n_issues
                if n_issues:
                    print(f"  [{i}/{len(profiles)}] {profile:10s} — {n_issues} validation issue(s)")
            sent += 1
        except Exception as exc:
            problems += 1
            print(f"  [{i}/{len(profiles)}] {profile:10s} — ERROR: {exc}")

        if i % 25 == 0 or i == len(profiles):
            print(f"  ...{i}/{len(profiles)} sessions sent")

    print(f"\nDone. {sent}/{len(profiles)} requests sent, {problems} problem(s) flagged.")
    print("Event tally:")
    for name, count in tally.most_common():
        print(f"  {name:20s} {count}")

    if args.validate:
        print("\nValidate mode — nothing was recorded. Re-run with --live to actually send.")
    else:
        print("\nCheck GA4 → Reports → Realtime now, or Explore in a few minutes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
