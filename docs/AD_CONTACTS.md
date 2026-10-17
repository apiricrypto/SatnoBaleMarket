# Message contact details

Market cards distinguish the **publisher profile** from **contact details inside the ad**. A group administrator publishing an ad is not thereby identified as its supplier. Contact details are extracted on read from the original message/caption, including existing messages; no backfill or database migration is required.

Supported details: Iranian mobile numbers (Persian/Arabic digits supported), labelled Iranian landlines, explicit WhatsApp direct/invitation links, Bale profile links and handles explicitly labelled as Bale, email addresses, and www/explicitly labelled website links. A phone number alone does not imply WhatsApp availability. Unlabelled handles have no guessed platform link. Ambiguous handles or Bale links joined to Persian text are shown for review without a clickable guessed identity. Phone digit normalization never rewrites account identifiers.

The card shows three contacts initially and an expandable remainder, capped at 32 deduplicated details. Values are escaped and external links use HTTPS and opener protection. Contact ownership is explicitly unverified. Original message text, stored sender metadata, four-column layout, sources, hourly sync, access controls and CRM delivery settings remain unchanged.

## Validation

- `python -m unittest discover -s tests -v`
- `python tools/verify_ui.py --artifacts /tmp/satno-ad-ui`

Regression coverage includes publisher/contact separation, photo captions, phone numbers touching Persian names, malformed links, Unicode identifier preservation, domain lookalikes and non-contact model/price values. Browser fixtures use synthetic contact data only and exercise 375, 768 and 1440 pixel layouts. No production contact data is included in the repository.

## Installation

This change builds on the deployed sender-contact release `4972d4b`. It adds no dependency or schema change. Before a separately authorized server upgrade, back up the checkout/configuration and production database, select the reviewed commit, restart only the web task and verify health, sign-in and card contacts. Do not change the hourly Sync task or its sources. Existing publisher contact caches need no reset.
