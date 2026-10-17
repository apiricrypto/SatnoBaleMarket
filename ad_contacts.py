"""Contact details explicitly present in message text, never inferred ownership."""

import re
from urllib.parse import parse_qs, quote, urlsplit

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
URL = re.compile(
    r"""https?://[^\s<>"'،؛]+|(?<![A-Za-z0-9_./@-])(?:www\.)?(?:wa\.me|api\.whatsapp\.com|web\.whatsapp\.com|chat\.whatsapp\.com|ble\.ir)/[^\s<>"'،؛]+|(?<![A-Za-z0-9_./@-])www\.[^\s<>"'،؛]+""",
    re.I,
)
EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}(?![\w.-])"
)
HANDLE = re.compile(r"""(?<![\w@])@([^\s<>"'،؛:!?؟()\[\]{}]+)""")
SEP = r"[ \t\u200c\u200e\u200f().-]*"
PREFIX = rf"(?:(?:\+98|0098){SEP}|0{SEP})"
PHONE = re.compile(
    rf"(?<![A-Za-z0-9_/@-])(?:{PREFIX}?9(?:{SEP}[0-9]){{9}}|{PREFIX}[1-8](?:{SEP}[0-9]){{9}})(?![A-Za-z0-9_])"
)
CONTACT_LABEL = re.compile(r"تماس|تلفن|موبایل|همراه|دفتر|فکس|phone|tel\b|call|📞|☎|📠", re.I)


def _iran_phone(value):
    digits = re.sub(r"[^0-9]", "", value)
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return "+98" + digits if re.fullmatch(r"[1-9][0-9]{9}", digits) else None


def _whatsapp_phone(value):
    value = value.translate(DIGITS).strip()
    # WhatsApp links must carry an explicit international number.
    if not re.fullmatch(r"\+?[1-9][0-9]{7,14}", value):
        return None
    return value.lstrip("+")


def _link(value, explicit_website=False):
    if not value.lower().startswith(("https://", "http://")):
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return None
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.strip("/")
        if host == "wa.me":
            phone = _whatsapp_phone(path)
            return ("whatsapp", phone, "https://wa.me/" + phone) if phone else None
        if host in {"api.whatsapp.com", "web.whatsapp.com"} and path == "send":
            phones = parse_qs(parsed.query).get("phone", [])
            phone = _whatsapp_phone(phones[0]) if len(phones) == 1 else None
            return ("whatsapp", phone, "https://wa.me/" + phone) if phone else None
        if host == "chat.whatsapp.com" and re.fullmatch(r"[A-Za-z0-9_-]{6,128}", path):
            return (
                "whatsapp_group",
                "گروه واتس‌اپ",
                "https://chat.whatsapp.com/" + path,
            )
        if host == "ble.ir":
            if re.fullmatch(r"[A-Za-z0-9_]{1,64}", path):
                return ("bale", "@" + path, "https://ble.ir/" + path.lower())
            if re.match(r"[A-Za-z0-9_]+[^\x00-\x7f]", path):
                return ("needs_review", value, None)
            return None
        if (
            explicit_website or (parsed.hostname or "").lower().startswith("www.")
        ) and re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
            parsed.hostname or "",
            re.I,
        ):
            host = (parsed.hostname or "").lower()
            href = "https://" + host + parsed.path
            if parsed.query:
                href += "?" + parsed.query
            return ("website", host, href)
    except ValueError:
        return None
    return None


def extract_ad_contacts(text):
    text = str(text or "").replace(r"\.", ".")
    contacts, seen, occupied = [], set(), []

    def add(kind, value, href):
        key = (kind, href or value.lower())
        if key not in seen and len(contacts) < 32:
            seen.add(key)
            contacts.append(
                {
                    "kind": kind,
                    "value": value,
                    "href": href,
                    "origin": "message_text",
                    "ownership_verified": False,
                }
            )

    def inside(match):
        return any(
            match.start() < end and match.end() > start for start, end in occupied
        )

    for match in URL.finditer(text):
        occupied.append(match.span())  # Do not reinterpret URL parts as phones/email.
        prefix = text[max(0, match.start() - 24) : match.start()]
        explicit_website = bool(
            re.search(r"(?:سایت|وبسایت|website)\s*[:：-]?\s*$", prefix, re.I)
        )
        result = _link(match.group().rstrip(".,;:!?؟)]}»"), explicit_website)
        if result:
            add(*result)
    for match in EMAIL.finditer(text):
        if not inside(match):
            occupied.append(match.span())
            value = match.group()
            add("email", value, "mailto:" + quote(value, safe="@._+-"))
    for match in PHONE.finditer(text.translate(DIGITS)):
        if inside(match):
            continue
        prefix = text[
            max(
                text.rfind("\n", 0, match.start()) + 1, match.start() - 40
            ) : match.start()
        ]
        suffix = text[match.end() : match.end() + 12]
        has_label = bool(CONTACT_LABEL.search(prefix))
        phone = _iran_phone(match.group())
        if not phone or (not phone.startswith("+989") and not has_label):
            continue
        if not has_label and (
            re.search(r"مدل|model|قیمت|price", prefix, re.I)
            or re.match(r"\s*(?:تومان|ریال|rial|toman)", suffix, re.I)
        ):
            continue
        add("phone", "0" + phone[3:], "tel:" + phone)
    for match in HANDLE.finditer(text):
        if inside(match):
            continue
        prefix = text[
            max(
                text.rfind("\n", 0, match.start()) + 1, match.start() - 40
            ) : match.start()
        ]
        suffix = text[match.end() : match.end() + 16]
        bale = re.search(r"(?:بله|\bbale)\s*[:：=\-]?\s*$", prefix, re.I) or re.match(
            r"\s*(?:در\s+)?(?:بله|bale)\b", suffix, re.I
        )
        username = match.group(1)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,63}", username):
            add("needs_review", "@" + username, None)
            continue
        add(
            "bale" if bale else "username",
            "@" + username,
            "https://ble.ir/" + username.lower() if bale else None,
        )
    rank = {
        "phone": 0,
        "whatsapp": 1,
        "bale": 2,
        "email": 3,
        "website": 4,
        "whatsapp_group": 5,
        "username": 6,
        "needs_review": 7,
    }
    return sorted(contacts, key=lambda contact: rank.get(contact["kind"], 9))


def extract_reviewed_contacts(text):
    """Parse reviewer-entered details without claiming they came from the ad."""
    contacts = extract_ad_contacts("تماس: " + str(text or ""))
    for contact in contacts:
        contact["origin"] = "reviewer_input"
    return contacts
