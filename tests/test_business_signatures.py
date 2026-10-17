"""Synthetic regressions shaped like operator-reported ad signatures."""
import unittest

from ad_contacts import extract_ad_contacts
from business_profiles import suggest_business_profile


class BusinessSignatureTests(unittest.TestCase):
    def test_name_before_address_and_phone_footer_is_not_product_brand(self):
        text = ('JINKO SOLAR | 620W Bifacial\nیکی از برندهای پرفروش پنل خورشیدی\n'
                '⚡ Jinko Solar 620W Bi\n📦 موجودی و استعلام قیمت روز\n\n'
                'نوآوران تجارت خورشید نمونه\n📍 تهران، خیابان نمونه، پلاک ۵\n'
                '📞 02123456789\n📱 09123456789')
        p = suggest_business_profile(text, 'stock_availability')
        self.assertEqual(p['declared_name'], 'نوآوران تجارت خورشید نمونه')
        self.assertEqual(p['entity_type'], 'company')
        self.assertEqual(p['name_evidence'], 'نوآوران تجارت خورشید نمونه')
        self.assertEqual(p['contact_verification'], 'unverified')
        phones = [c['value'] for c in extract_ad_contacts(text) if c['kind'] == 'phone']
        self.assertEqual(phones, ['02123456789', '09123456789'])

    def test_final_signature_with_tagline_beats_opening_product_description(self):
        text = ('استراکچر استاندارد، مستقیم از صنایع سازه نمونه\n'
                'تولید و تأمین انواع سازه خورشیدی\n'
                '📞 استعلام و ثبت سفارش: 09123456789 | 09351234567 جناب نمونه\n'
                '📍 اصفهان، شهرک صنعتی\n📲 @sample-profile\n'
                '🦅 صنایع سازه نمونه | سازه مطمئن، انتخاب حرفه‌ای')
        p = suggest_business_profile(text, 'supplier_seller')
        self.assertEqual(p['declared_name'], 'صنایع سازه نمونه')
        self.assertEqual(p['name_evidence'], '🦅 صنایع سازه نمونه | سازه مطمئن، انتخاب حرفه‌ای')
        self.assertEqual(len([c for c in extract_ad_contacts(text) if c['kind'] == 'phone']), 2)
        handle = next(c for c in extract_ad_contacts(text) if c['value'] == '@sample-profile')
        self.assertIsNone(handle['href'])

    def test_landline_phone_icon_supported_but_unlabelled_number_not_promoted(self):
        self.assertEqual([c['value'] for c in extract_ad_contacts('☎️ ۰۲۱۲۳۴۵۶۷۸۹')], ['02123456789'])
        self.assertEqual(extract_ad_contacts('شناسه کالا 02123456789'), [])

    def test_product_brand_header_and_sales_slogans_do_not_become_party(self):
        for text in (
            'JINKO SOLAR | 620W Bifacial\n📞 09123456789',
            'استعلام قیمت روز\n📍 تهران\n📞 09123456789',
            'تولید و تأمین تجهیزات خورشیدی\n📍 اصفهان\n📞 09123456789',
            'فروش ویژه پنل خورشیدی\n📞 09123456789\nکیفیت مطمئن، انتخاب حرفه‌ای',
            '📞 09123456789\n📍 تهران، خیابان نمونه',
        ):
            with self.subTest(text=text):
                self.assertEqual(suggest_business_profile(text, 'supplier_seller')['declared_name'], '')

    def test_unrelated_name_without_contact_evidence_is_not_guessed(self):
        self.assertEqual(suggest_business_profile('نوآوران تجارت نمونه\n📍 تهران', 'other')['declared_name'], '')

    def test_ambiguous_signatures_are_left_for_review(self):
        text = ('بازرگانی نمونه اول\n📍 تهران\n📞 09123456789\n'
                'بازرگانی نمونه دوم\n📍 اصفهان\n📞 09351234567')
        self.assertEqual(suggest_business_profile(text, 'supplier_seller')['declared_name'], '')

    def test_contact_calls_product_lines_and_addresses_are_not_business_names(self):
        for ending in ('تماس بگیرید', 'با ما تماس بگیرید', 'ارسال به سراسر کشور',
                       'گارانتی معتبر و خدمات پس از فروش', 'اینورتر خورشیدی اصل',
                       'تهران بزرگراه ارتش', 'شرایط پرداخت آسان'):
            with self.subTest(ending=ending):
                self.assertEqual(suggest_business_profile('📞 09123456789\n' + ending, 'supplier_seller')['declared_name'], '')

    def test_valid_explicit_company_is_not_replaced_by_footer_prose(self):
        for ending in ('ارسال به سراسر کشور', 'تهران میدان آزادی', 'گروه بازاریابی نمونه | تبلیغات'):
            with self.subTest(ending=ending):
                text = 'شرکت انرژی نمونه\n📞 09123456789\n' + ending
                self.assertEqual(suggest_business_profile(text, 'supplier_seller')['declared_name'], 'انرژی نمونه')

    def test_product_before_address_is_not_an_implicit_company(self):
        self.assertEqual(suggest_business_profile('پنل خورشیدی جینکو\n📍 تهران\n📞 09123456789', 'supplier_seller')['declared_name'], '')
