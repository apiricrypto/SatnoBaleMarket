"""Reviewable party claims from market ads; never a company registry or identity proof."""
import json
import re

from ad_contacts import extract_ad_contacts, extract_reviewed_contacts

PROFILE_FIELDS = {
    'entity_type', 'declared_name', 'roles', 'contact_person',
    'contact_verification', 'verification_note',
}
AUDIT_FIELDS = {'contact_verified_by', 'contact_verified_at', 'verified_contact'}
ROLE_ORDER = ('supplier', 'buyer')
BUSINESS_SCHEMA = 'satno.market-party.v1'


def _signature_name(line):
    """Restrict implicit names to short Persian business signatures, not ad prose."""
    value = re.sub(r'^[^A-Za-zآ-ی]+', '', line)
    value = re.split(r'[|؛;—–]', value, maxsplit=1)[0].strip(' .ـ')
    value = re.sub(r'^شرکت\s+', '', value)
    if not re.search(r'[آ-ی]', value) or not 2 <= len(value.split()) <= 7:
        return ''
    # Footer position alone is insufficient: require a business-name cue as well.
    if not re.search(r'(?<!\w)(?:تجارت|بازرگانی|توسعه|صنایع|صنعت|گروه|پروفیل|سولار|انرژی|الکتریک|الکترونیک|مهندسی)(?!\w)', value):
        return ''
    if not re.fullmatch(r'[A-Za-zآ-ی\u200c -]+', value):
        return ''
    if re.match(r'^(?:استراکچر|تولید|تأمین|تامین|فروش|استعلام|قیمت|موجودی|کیفیت|انتخاب|انواع|مناسب|سازه مطمئن|برای|لیست|توان|فناوری|تماس|با|ارسال|گارانتی|شرایط|ثبت|جهت|پشتیبانی|پنل|اینورتر|باتری|کابل|تجهیزات)\b', value):
        return ''
    if re.search(r'(?<!\w)(?:خیابان|بلوار|بزرگراه|کوچه|میدان|جاده|پلاک|واحد|آدرس|نشانی|شهرک|وات|کیلووات)(?!\w)', value):
        return ''
    return value


def _contact_signatures(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    contact_lines = set()
    for i, line in enumerate(lines):
        if any(c.get('href') and c['kind'] in {'phone', 'email', 'whatsapp', 'bale'}
               for c in extract_ad_contacts(line)):
            contact_lines.add(i)
    candidates = {}
    for i, line in enumerate(lines):
        if i in contact_lines or line.startswith(('📍', '@', '📲')):
            continue
        name = _signature_name(line)
        if not name:
            continue
        before_address = (i + 1 < len(lines) and
            re.match(r'^(?:📍|آدرس|نشانی|address\b)', lines[i + 1], re.I) and
            any(j in contact_lines for j in range(i + 1, min(i + 5, len(lines)))))
        # An end signature needs preceding contact evidence, not just a slogan.
        end_signature = (i >= len(lines) - 2 and
            any(j in contact_lines for j in range(max(0, i - 4), i)))
        if before_address or end_signature:
            candidates.setdefault(name, line)
    return candidates


def suggest_business_profile(text, category='other'):
    text = str(text or '')
    # An explicit company marker or a contact-block signature is an advertised claim.
    match = re.search(r'(?<!\w)شرکت[ \t]+([^\n؛;،,:：«»"<>|☀️]{2,100})', text)
    name, evidence = '', ''
    if match:
        candidate = match.group(1).strip(' .ـ\t')
        if (len(candidate.split()) <= 5 and not re.match(r'^(?:در|کنید|کردن|ما|شما|های|ها)\b', candidate)
                and not re.search(r'https?://|www\.|@|[0-9۰-۹٠-٩]{5}', candidate)):
            name, evidence = candidate, match.group().strip()
    signatures = _contact_signatures(text)
    if not name and len(signatures) == 1:
        name, evidence = next(iter(signatures.items()))
    elif not name and len(signatures) > 1:
        name, evidence = '', ''  # Multiple advertised parties need human selection.
    roles = []
    if category in {'supplier_seller', 'stock_availability'}:
        roles = ['supplier']
    elif category in {'buyer_demand', 'inquiry_project'}:
        roles = ['buyer']
    return dict(entity_type='company' if name else 'unknown', declared_name=name,
                roles=roles, contact_person='', contact_verification='unverified',
                verification_note='', name_origin='message_text' if name else None,
                name_evidence=evidence)


def load_business_profile(value):
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError('business_profile contains invalid JSON') from None
    if not isinstance(value, dict):
        raise ValueError('business_profile must be an object')
    return dict(value)


def validate_business_profile(value, *, selected=False, primary_contact=None, trusted_stored=False):
    profile = load_business_profile(value)
    if profile is None:
        return None  # Existing clients and historical reviews remain compatible.
    if set(profile) - (PROFILE_FIELDS | AUDIT_FIELDS if trusted_stored else PROFILE_FIELDS):
        raise ValueError('business_profile has unsupported fields')
    result = {}
    for key, limit in (('declared_name', 200), ('contact_person', 200), ('verification_note', 1000)):
        field = profile.get(key, '')
        if not isinstance(field, str) or len(field) > limit:
            raise ValueError(f'{key} must be text of at most {limit} characters')
        result[key] = field.strip()
    result['entity_type'] = profile.get('entity_type', 'unknown')
    if not isinstance(result['entity_type'], str) or result['entity_type'] not in {'company', 'person', 'unknown'}:
        raise ValueError('entity_type must be company, person or unknown')
    roles = profile.get('roles', [])
    if not isinstance(roles, list) or len(roles) > 2 or any(r not in ROLE_ORDER for r in roles):
        raise ValueError('roles must contain supplier and/or buyer')
    result['roles'] = [r for r in ROLE_ORDER if r in roles]
    result['contact_verification'] = profile.get('contact_verification', 'unverified')
    if not isinstance(result['contact_verification'], str) or result['contact_verification'] not in {'unverified', 'confirmed'}:
        raise ValueError('contact_verification must be unverified or confirmed')
    if selected and (not result['declared_name'] or result['entity_type'] == 'unknown' or not result['roles']):
        raise ValueError('برای ورود به صف، نام طرف تجاری، نوع و نقش را مشخص کنید.')
    if result['contact_verification'] == 'confirmed':
        usable = [c for c in extract_reviewed_contacts(primary_contact) if c.get('href') and c['kind'] != 'whatsapp_group']
        if not result['declared_name'] or not result['verification_note'] or not usable:
            raise ValueError('تأیید تعلق تماس نیازمند نام، تماس اصلی معتبر و توضیح بررسی است.')
    if result['entity_type'] == 'person' and result['contact_person']:
        raise ValueError('برای شخص حقیقی، نام را در نام طرف تجاری ثبت کنید؛ نمایندهٔ شرکت را خالی بگذارید.')
    if trusted_stored:
        for field in AUDIT_FIELDS:
            result[field] = profile.get(field)
    return result


def build_business_context(row, review):
    profile = validate_business_profile(review.get('business_profile'),
        selected=review.get('review_status') == 'selected', primary_contact=review.get('contact'), trusted_stored=True)
    if profile is None:
        return None
    roles = profile['roles']
    intake = ('dual_role_intake' if len(roles) == 2 else
              'supplier_intake' if roles == ['supplier'] else
              'sales_lead_intake' if roles == ['buyer'] else 'needs_review')
    suggestion = suggest_business_profile(row.get('text'), row.get('category'))
    name_from_ad = bool(suggestion['declared_name'] and suggestion['declared_name'] == profile['declared_name'])
    return {
        'schema': BUSINESS_SCHEMA,
        'intended_intake': intake,
        'requested_action': 'resolve_or_create_after_review',
        'delivery_state': 'crm_contract_pending',
        'party': {**profile, 'name_origin': 'message_text' if name_from_ad else 'reviewer_input',
                  'name_evidence': suggestion['name_evidence'] if name_from_ad else None},
        'source': {'message_id': row.get('id'), 'external_id': row.get('external_id'),
                   'chat_name': row.get('chat_name'), 'sent_at': row.get('sent_at'),
                   'publisher_role': 'publisher'},
        'review': {'status': review.get('review_status'), 'reviewed_by': review.get('reviewed_by'),
                   'reviewed_at': review.get('reviewed_at'),
                   'verification_scope': 'primary_contact_only' if profile['contact_verification'] == 'confirmed' else 'none',
                   'primary_contact': review.get('contact'),
                   'contact_verified_by': profile.get('contact_verified_by'),
                   'contact_verified_at': profile.get('contact_verified_at')},
    }
