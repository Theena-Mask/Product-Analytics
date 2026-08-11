#!/usr/bin/env python3
"""
Builds gtm-container/Solstice-GA4-GTM-Container.json — an importable GTM
container covering the five capabilities in the README: GA4 e-commerce,
Google Ads conversion tracking, engagement metrics, Consent Mode v2, and
UTM-based lead scoring.

Design note on import safety: this version deliberately avoids constructs
that GTM's importer rejects or that aren't publicly documented.
  - Parameter "type" values are uppercase enums (TEMPLATE / BOOLEAN /
    INTEGER / LIST / MAP) — lowercase is rejected outright.
  - Consent default/update tags are Custom HTML running gtag('consent',...)
    rather than undocumented native consent tag types.
  - consentSettings blocks are omitted; consent is enforced by Consent
    Initialization trigger ordering plus the gtag consent state, which is
    the documented GTM-managed pattern.
  - Every {{variable}} referenced by a tag is defined in this file.

Run: python3 scripts/build_gtm_container.py
"""
import json
import os

ACCOUNT_ID = "6100000000"
CONTAINER_ID = "200000000"
PUBLIC_ID = "GTM-W48BV4SP"
GA4_MEASUREMENT_ID = "G-47X3FGWN78"

_ids = {"tag": 0, "trigger": 0, "variable": 0, "folder": 0}


def nid(kind):
    _ids[kind] += 1
    return str(_ids[kind])


def base(id_key, kind):
    return {
        "accountId": ACCOUNT_ID,
        "containerId": CONTAINER_ID,
        id_key: nid(kind),
        "fingerprint": "1000000000000",
    }


def make_folder(name):
    f = base("folderId", "folder")
    f["name"] = name
    return f


def const_var(name, value, folder_id):
    v = base("variableId", "variable")
    v.update({
        "name": name,
        "type": "c",
        "parameter": [{"type": "TEMPLATE", "key": "value", "value": value}],
        "parentFolderId": folder_id,
    })
    return v


def dlv_var(name, dl_key, folder_id):
    v = base("variableId", "variable")
    v.update({
        "name": name,
        "type": "v",
        "parameter": [
            {"type": "INTEGER", "key": "dataLayerVersion", "value": "2"},
            {"type": "TEMPLATE", "key": "name", "value": dl_key},
        ],
        "parentFolderId": folder_id,
    })
    return v


def custom_event_trigger(name, event_name, folder_id):
    t = base("triggerId", "trigger")
    t.update({
        "name": name,
        "type": "CUSTOM_EVENT",
        "customEventFilter": [{
            "type": "EQUALS",
            "parameter": [
                {"type": "TEMPLATE", "key": "arg0", "value": "{{_event}}"},
                {"type": "TEMPLATE", "key": "arg1", "value": event_name},
            ],
        }],
        "parentFolderId": folder_id,
    })
    return t


def ga4_event_tag(name, event_name, trigger_id, folder_id):
    t = base("tagId", "tag")
    t.update({
        "name": name,
        "type": "gaawe",
        "parameter": [
            {"type": "BOOLEAN", "key": "sendEcommerceData", "value": "true"},
            {"type": "TEMPLATE", "key": "eventName", "value": event_name},
            {"type": "TEMPLATE", "key": "measurementIdOverride",
             "value": "{{Constant - GA4 Measurement ID}}"},
        ],
        "firingTriggerId": [trigger_id],
        "parentFolderId": folder_id,
    })
    return t


def html_tag(name, html, trigger_ids, folder_id):
    t = base("tagId", "tag")
    t.update({
        "name": name,
        "type": "html",
        "parameter": [
            {"type": "TEMPLATE", "key": "html", "value": html},
            {"type": "BOOLEAN", "key": "supportDocumentWrite", "value": "false"},
        ],
        "firingTriggerId": trigger_ids,
        "parentFolderId": folder_id,
    })
    return t


def build():
    tags, triggers, variables = [], [], []

    f_ecom = make_folder("1. GA4 e-commerce")
    f_ads = make_folder("2. Paid ads conversion tracking")
    f_eng = make_folder("3. Engagement metrics")
    f_con = make_folder("4. Cookie consent (Consent Mode v2)")
    f_lead = make_folder("5. Lead scoring (UTM + CRM)")
    folders = [f_ecom, f_ads, f_eng, f_con, f_lead]

    F_ECOM = f_ecom["folderId"]
    F_ADS = f_ads["folderId"]
    F_ENG = f_eng["folderId"]
    F_CON = f_con["folderId"]
    F_LEAD = f_lead["folderId"]

    # ---- shared variables ------------------------------------------------
    variables.append(const_var("Constant - GA4 Measurement ID", GA4_MEASUREMENT_ID, F_ECOM))
    variables.append(dlv_var("DLV - Ecommerce Value", "ecommerce.value", F_ECOM))
    variables.append(dlv_var("DLV - Ecommerce Currency", "ecommerce.currency", F_ECOM))

    # ---- shared triggers -------------------------------------------------
    t_pageview = base("triggerId", "trigger")
    t_pageview.update({"name": "Page View - All Pages", "type": "PAGEVIEW",
                       "parentFolderId": F_ECOM})
    triggers.append(t_pageview)

    # Consent Initialization is a BUILT-IN trigger present in every web
    # container by default — it must be referenced by its reserved ID, not
    # redefined. Defining it is what produced:
    #   "Unrecognized value [CONSENT_INITIALIZATION]"
    # Reserved built-in trigger IDs:
    #   2147479553  All Pages
    #   2147479572  Initialization - All Pages
    #   2147479573  Consent Initialization - All Pages
    CONSENT_INIT_TRIGGER_ID = "2147479573"

    # ---- Folder 1: GA4 e-commerce ----------------------------------------
    t_config = base("tagId", "tag")
    t_config.update({
        "name": "GA4 Configuration - Base Tag",
        "type": "gaawc",
        "parameter": [
            {"type": "TEMPLATE", "key": "measurementId",
             "value": "{{Constant - GA4 Measurement ID}}"},
            {"type": "BOOLEAN", "key": "sendPageView", "value": "true"},
        ],
        "firingTriggerId": [t_pageview["triggerId"]],
        "parentFolderId": F_ECOM,
    })
    tags.append(t_config)

    ecom_events = [
        ("View Item", "view_item"),
        ("View Item List", "view_item_list"),
        ("Add to Cart", "add_to_cart"),
        ("Begin Checkout", "begin_checkout"),
        ("Add Payment Info", "add_payment_info"),
        ("Purchase", "purchase"),
    ]
    ecom_trigger_ids = {}
    for label, ev in ecom_events:
        trg = custom_event_trigger(f"Custom Event - {ev}", ev, F_ECOM)
        triggers.append(trg)
        ecom_trigger_ids[ev] = trg["triggerId"]
        tags.append(ga4_event_tag(f"GA4 Event - {label}", ev, trg["triggerId"], F_ECOM))

    # ---- generate_lead trigger (used by folders 2 and 5) ------------------
    t_lead = custom_event_trigger("Custom Event - generate_lead", "generate_lead", F_LEAD)
    triggers.append(t_lead)

    # ---- Folder 2: Paid ads conversion tracking --------------------------
    variables.append(const_var("Constant - Google Ads Conversion ID", "AW-XXXXXXXXX", F_ADS))
    variables.append(const_var("Constant - Ads Label - Purchase", "REPLACE_LABEL_PURCHASE", F_ADS))
    variables.append(const_var("Constant - Ads Label - Lead", "REPLACE_LABEL_LEAD", F_ADS))

    # NOTE: Conversion Linker is deliberately NOT included here.
    # GTM resolves the "sp" tag type to a vendor template that requires a
    # non-empty conversionId, which a portfolio container has no value for,
    # and the import fails with:
    #   containerVersion.tag[n].vendorTemplate.parameter.conversionId:
    #   The value must not be empty.
    # Add it manually after import (30 seconds, and it's a native type):
    #   New Tag -> Conversion Linker -> Trigger: Page View - All Pages
    # It only matters once a real linked Google Ads account exists.

    tags.append(html_tag(
        "Google Ads Conversion - Purchase",
        "<script>\n"
        "  gtag('event', 'conversion', {\n"
        "    'send_to': '{{Constant - Google Ads Conversion ID}}/{{Constant - Ads Label - Purchase}}',\n"
        "    'value': {{DLV - Ecommerce Value}},\n"
        "    'currency': {{DLV - Ecommerce Currency}}\n"
        "  });\n"
        "</script>",
        [ecom_trigger_ids["purchase"]], F_ADS,
    ))
    tags.append(html_tag(
        "Google Ads Conversion - Lead Form Submit",
        "<script>\n"
        "  gtag('event', 'conversion', {\n"
        "    'send_to': '{{Constant - Google Ads Conversion ID}}/{{Constant - Ads Label - Lead}}'\n"
        "  });\n"
        "</script>",
        [t_lead["triggerId"]], F_ADS,
    ))

    # ---- Folder 3: Engagement metrics ------------------------------------
    t_click = base("triggerId", "trigger")
    t_click.update({
        "name": "Click - Tracked Buttons",
        "type": "CLICK",
        "filter": [{
            "type": "CONTAINS",
            "parameter": [
                {"type": "TEMPLATE", "key": "arg0", "value": "{{Click Classes}}"},
                {"type": "TEMPLATE", "key": "arg1", "value": "track-click"},
            ],
        }],
        "parentFolderId": F_ENG,
    })
    triggers.append(t_click)

    t_form = base("triggerId", "trigger")
    t_form.update({"name": "Form Submission - All Forms", "type": "FORM_SUBMISSION",
                   "parentFolderId": F_ENG})
    triggers.append(t_form)

    t_scroll = base("triggerId", "trigger")
    t_scroll.update({
        "name": "Scroll Depth - 25/50/75/90%",
        "type": "SCROLL_DEPTH",
        "parameter": [
            {"type": "BOOLEAN", "key": "verticalThresholdOn", "value": "true"},
            {"type": "TEMPLATE", "key": "verticalThresholdUnits", "value": "PERCENT"},
            {"type": "TEMPLATE", "key": "verticalThresholdsPercent", "value": "25,50,75,90"},
            {"type": "TEMPLATE", "key": "triggerStartOption", "value": "WINDOW_LOAD"},
        ],
        "parentFolderId": F_ENG,
    })
    triggers.append(t_scroll)

    tags.append(ga4_event_tag("GA4 Event - Engagement Click", "engagement_click",
                              t_click["triggerId"], F_ENG))
    tags.append(ga4_event_tag("GA4 Event - Form Submission", "form_submission",
                              t_form["triggerId"], F_ENG))
    tags.append(ga4_event_tag("GA4 Event - Scroll Tracking", "scroll_depth",
                              t_scroll["triggerId"], F_ENG))

    # ---- Folder 4: Consent Mode v2 ---------------------------------------
    t_accept = custom_event_trigger("Consent Update - Accept", "consent_accepted", F_CON)
    t_reject = custom_event_trigger("Consent Update - Reject", "consent_rejected", F_CON)
    triggers += [t_accept, t_reject]

    tags.append(html_tag(
        "Consent - Set Defaults (Denied)",
        "<script>\n"
        "  window.dataLayer = window.dataLayer || [];\n"
        "  function gtag(){dataLayer.push(arguments);}\n"
        "  gtag('consent', 'default', {\n"
        "    'ad_storage': 'denied',\n"
        "    'ad_user_data': 'denied',\n"
        "    'ad_personalization': 'denied',\n"
        "    'analytics_storage': 'denied',\n"
        "    'wait_for_update': 500\n"
        "  });\n"
        "</script>",
        [CONSENT_INIT_TRIGGER_ID], F_CON,
    ))
    tags.append(html_tag(
        "Consent - Update on Accept",
        "<script>\n"
        "  window.dataLayer = window.dataLayer || [];\n"
        "  function gtag(){dataLayer.push(arguments);}\n"
        "  gtag('consent', 'update', {\n"
        "    'ad_storage': 'granted',\n"
        "    'ad_user_data': 'granted',\n"
        "    'ad_personalization': 'granted',\n"
        "    'analytics_storage': 'granted'\n"
        "  });\n"
        "</script>",
        [t_accept["triggerId"]], F_CON,
    ))
    tags.append(html_tag(
        "Consent - Update on Reject",
        "<script>\n"
        "  window.dataLayer = window.dataLayer || [];\n"
        "  function gtag(){dataLayer.push(arguments);}\n"
        "  gtag('consent', 'update', {\n"
        "    'ad_storage': 'denied',\n"
        "    'ad_user_data': 'denied',\n"
        "    'ad_personalization': 'denied',\n"
        "    'analytics_storage': 'denied'\n"
        "  });\n"
        "</script>",
        [t_reject["triggerId"]], F_CON,
    ))

    # ---- Folder 5: Lead scoring (UTM + CRM) ------------------------------
    variables.append(const_var("Constant - CRM Webhook URL",
                               "https://REPLACE-WITH-YOUR-WEBHOOK-URL", F_LEAD))
    for label, key in [
        ("UTM Source", "utm_source"), ("UTM Medium", "utm_medium"),
        ("UTM Campaign", "utm_campaign"), ("UTM Term", "utm_term"),
        ("UTM Content", "utm_content"), ("Lead Type", "lead_type"),
        ("Lead Score", "lead_score"),
    ]:
        variables.append(dlv_var(f"DLV - {label}", key, F_LEAD))

    v_lookup = base("variableId", "variable")
    v_lookup.update({
        "name": "Lookup Table - Lead Score Weights by Event",
        "type": "smm",
        "parameter": [
            {"type": "TEMPLATE", "key": "input", "value": "{{_event}}"},
            {"type": "TEMPLATE", "key": "defaultValue", "value": "0"},
            {"type": "LIST", "key": "map", "list": [
                {"type": "MAP", "map": [
                    {"type": "TEMPLATE", "key": "key", "value": "view_item"},
                    {"type": "TEMPLATE", "key": "value", "value": "2"}]},
                {"type": "MAP", "map": [
                    {"type": "TEMPLATE", "key": "key", "value": "add_to_cart"},
                    {"type": "TEMPLATE", "key": "value", "value": "10"}]},
                {"type": "MAP", "map": [
                    {"type": "TEMPLATE", "key": "key", "value": "begin_checkout"},
                    {"type": "TEMPLATE", "key": "value", "value": "20"}]},
                {"type": "MAP", "map": [
                    {"type": "TEMPLATE", "key": "key", "value": "purchase"},
                    {"type": "TEMPLATE", "key": "value", "value": "50"}]},
                {"type": "MAP", "map": [
                    {"type": "TEMPLATE", "key": "key", "value": "contact_form_submit"},
                    {"type": "TEMPLATE", "key": "value", "value": "15"}]},
            ]},
        ],
        "parentFolderId": F_LEAD,
    })
    variables.append(v_lookup)

    v_js = base("variableId", "variable")
    v_js.update({
        "name": "Custom JavaScript - Total Lead Score",
        "type": "jsm",
        "parameter": [{
            "type": "TEMPLATE", "key": "javascript",
            "value": ("function() {\n"
                      "  try {\n"
                      "    return parseInt(localStorage.getItem('solstice_lead_score') || '0', 10);\n"
                      "  } catch (e) {\n"
                      "    return 0;\n"
                      "  }\n"
                      "}"),
        }],
        "parentFolderId": F_LEAD,
    })
    variables.append(v_js)

    tags.append(ga4_event_tag("GA4 Event - Generate Lead", "generate_lead",
                              t_lead["triggerId"], F_LEAD))
    tags.append(html_tag(
        "Lead Scoring - Send to CRM Webhook",
        "<script>\n"
        "  fetch('{{Constant - CRM Webhook URL}}', {\n"
        "    method: 'POST',\n"
        "    headers: {'Content-Type': 'application/json'},\n"
        "    body: JSON.stringify({\n"
        "      lead_type: {{DLV - Lead Type}},\n"
        "      lead_score: {{Custom JavaScript - Total Lead Score}},\n"
        "      utm_source: {{DLV - UTM Source}},\n"
        "      utm_medium: {{DLV - UTM Medium}},\n"
        "      utm_campaign: {{DLV - UTM Campaign}},\n"
        "      utm_term: {{DLV - UTM Term}},\n"
        "      utm_content: {{DLV - UTM Content}},\n"
        "      page_location: {{Page URL}},\n"
        "      timestamp: new Date().toISOString()\n"
        "    })\n"
        "  });\n"
        "</script>",
        [t_lead["triggerId"]], F_LEAD,
    ))

    # Only the built-ins actually referenced by tags/triggers in this
    # container. Every extra entry is another enum that can be rejected on
    # import for no benefit.
    built_in = [
        {"accountId": ACCOUNT_ID, "containerId": CONTAINER_ID, "type": t, "name": n}
        for t, n in [
            ("EVENT", "Event"),
            ("CLICK_CLASSES", "Click Classes"),
            ("PAGE_URL", "Page URL"),
        ]
    ]

    return {
        "exportFormatVersion": 2,
        "exportTime": "2026-08-10 00:00:00",
        "containerVersion": {
            "path": f"accounts/{ACCOUNT_ID}/containers/{CONTAINER_ID}/versions/0",
            "accountId": ACCOUNT_ID,
            "containerId": CONTAINER_ID,
            "containerVersionId": "0",
            "name": "Solstice - initial setup",
            "container": {
                "path": f"accounts/{ACCOUNT_ID}/containers/{CONTAINER_ID}",
                "accountId": ACCOUNT_ID,
                "containerId": CONTAINER_ID,
                "name": "Solstice Outdoor Demo",
                "publicId": PUBLIC_ID,
                "usageContext": ["WEB"],
                "fingerprint": "1000000000000",
            },
            "tag": tags,
            "trigger": triggers,
            "variable": variables,
            "folder": folders,
            "builtInVariable": built_in,
            "fingerprint": "1000000000000",
        },
    }


if __name__ == "__main__":
    data = build()
    out_dir = os.path.join(os.path.dirname(__file__), "..", "gtm-container")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "Solstice-GA4-GTM-Container.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    cv = data["containerVersion"]
    print(f"Wrote {out_path}")
    print(f"  tags {len(cv['tag'])} - triggers {len(cv['trigger'])} - "
          f"variables {len(cv['variable'])} - folders {len(cv['folder'])}")
