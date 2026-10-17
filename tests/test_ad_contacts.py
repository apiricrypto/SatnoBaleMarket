import unittest
from ad_contacts import extract_ad_contacts


class AdContactTests(unittest.TestCase):
    def contacts(self, text, kind):
        return [c for c in extract_ad_contacts(text) if c["kind"] == kind]

    def test_mobile_persian_arabic_digits_and_separators(self):
        contacts = self.contacts("تماس: ۰۹۱۲ ۳۴۵ ۶۷۸۹ و +۹۸۹۱۲۳۴۵۶۷۸۹", "phone")
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["href"], "tel:+989123456789")
        self.assertEqual(contacts[0]["origin"], "message_text")
        self.assertEqual(
            self.contacts("٠٩١٢٣٤٥٦٧٨٩", "phone")[0]["href"], "tel:+989123456789"
        )

    def test_multiple_mobile_numbers_are_not_merged(self):
        contacts = self.contacts("09123456789 09351234567", "phone")
        self.assertEqual(len(contacts), 2)

    def test_landline_requires_contact_context(self):
        self.assertEqual(
            self.contacts("تلفن دفتر: 021-12345678", "phone")[0]["href"],
            "tel:+982112345678",
        )
        self.assertEqual(extract_ad_contacts("مدل: 02112345678"), [])
        self.assertEqual(extract_ad_contacts("قیمت 09123456789 تومان"), [])
        self.assertEqual(extract_ad_contacts("MODEL-PV-09123456789"), [])

    def test_direct_whatsapp_links_canonicalize_without_prefilled_text(self):
        contacts = self.contacts(
            "واتساپ https://wa.me/989123456789 و https://api.whatsapp.com/send?phone=%2B989123456789&text=hello",
            "whatsapp",
        )
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["href"], "https://wa.me/989123456789")
        self.assertEqual(
            self.contacts("wa.me/989351234567", "whatsapp")[0]["href"],
            "https://wa.me/989351234567",
        )

    def test_whatsapp_group_link_is_labelled_separately(self):
        contact = self.contacts(
            "https://chat.whatsapp.com/AbCDef123456789", "whatsapp_group"
        )[0]
        self.assertEqual(contact["href"], "https://chat.whatsapp.com/AbCDef123456789")

    def test_bale_profile_and_contextual_username(self):
        contacts = self.contacts(
            "لینک https://ble.ir/supplier_one و آیدی بله: @supplier_one", "bale"
        )
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["href"], "https://ble.ir/supplier_one")
        self.assertEqual(
            self.contacts("آیدی بله: @supplier_two", "bale")[0]["href"],
            "https://ble.ir/supplier_two",
        )

    def test_unlabelled_username_does_not_guess_platform(self):
        contact = self.contacts("تماس: @supplier_unknown", "username")[0]
        self.assertIsNone(contact["href"])
        self.assertEqual(contact["value"], "@supplier_unknown")
        self.assertEqual(self.contacts("تلگرام: @supplier_unknown", "bale"), [])

    def test_email_is_not_misread_as_bale_username(self):
        contacts = extract_ad_contacts("ایمیل: sales@example.com")
        self.assertEqual([c["kind"] for c in contacts], ["email"])
        self.assertEqual(contacts[0]["href"], "mailto:sales@example.com")

    def test_unsafe_and_lookalike_domains_are_not_contacts(self):
        for value in [
            "https://wa.me.evil.example/989123456789",
            "https://evil.example/wa.me/989123456789",
            "https://ble.ir@evil.example/person",
            "https://evilble.ir/person",
            "javascript:alert(1)",
            "https://ble.ir:444/person",
        ]:
            with self.subTest(value=value):
                self.assertEqual(extract_ad_contacts(value), [])

    def test_phone_inside_arbitrary_url_and_model_is_not_promoted(self):
        self.assertEqual(
            extract_ad_contacts("https://example.com/product/09123456789"), []
        )
        self.assertEqual(
            extract_ad_contacts("COM/CHANNEL/0029VB8G24C65YDAEUEQ6H0J"), []
        )

    def test_bad_whatsapp_numbers_do_not_create_links(self):
        for value in [
            "https://wa.me/123",
            "https://wa.me/not_a_phone",
            "https://api.whatsapp.com/send?text=09123456789",
        ]:
            self.assertEqual(extract_ad_contacts(value), [])

    def test_no_automatic_whatsapp_from_ordinary_phone(self):
        self.assertEqual(self.contacts("تماس 09123456789", "whatsapp"), [])

    def test_empty_text_and_non_contact_numbers(self):
        self.assertEqual(extract_ad_contacts(None), [])
        self.assertEqual(
            extract_ad_contacts(
                "پنل 550 وات، باتری 16 کیلووات ساعت و قیمت 250000000 تومان"
            ),
            [],
        )

    def test_phone_touching_persian_name_in_photo_caption(self):
        from types import SimpleNamespace
        from sync_bale import get_text

        caption = (
            "فروش اینورتر هیبرید 6KW؛ برای استعلام در تماس باشید09123456789نام نمونه"
        )
        text = get_text(
            SimpleNamespace(
                content=SimpleNamespace(
                    text=None, media=SimpleNamespace(caption=caption)
                )
            )
        )
        self.assertEqual(self.contacts(text, "phone")[0]["href"], "tel:+989123456789")

    def test_explicit_website_and_markdown_escaped_dot(self):
        contact = self.contacts(r"وبسایت www.example\.com", "website")[0]
        self.assertEqual(contact["href"], "https://www.example.com")
        self.assertEqual(
            self.contacts(
                "https://web.bale.ai/emoji-data/img-apple-64/1f4e3.png", "website"
            ),
            [],
        )

    def test_bale_url_stuck_to_persian_text_is_not_silently_guessed(self):
        contact = self.contacts(
            "بله: https://ble.ir/supplier_oneمایه افتخار ماست", "needs_review"
        )[0]
        self.assertIsNone(contact["href"])
        self.assertIn("supplier_oneمایه", contact["value"])

    def test_ambiguous_handle_continuations_are_never_truncated(self):
        for text in ('بله: @supplier_oneمایه افتخار ماست','بله: @supplier_one.other'):
            with self.subTest(text=text):
                contacts=extract_ad_contacts(text)
                self.assertFalse(any(c['href'] for c in contacts))
                self.assertTrue(any(c['kind']=='needs_review' for c in contacts))

    def test_digit_normalization_does_not_change_account_identifiers(self):
        for text in ('بله: https://ble.ir/supplier_۱','بله: @supplier_۱'):
            with self.subTest(text=text):
                contacts=extract_ad_contacts(text)
                self.assertFalse(any(c['href'] for c in contacts))
                self.assertTrue(any('۱' in c['value'] for c in contacts))
        self.assertEqual(extract_ad_contacts('sales۱@example.com'),[])

    def test_whatsapp_phone_digits_can_be_normalized_without_changing_usernames(self):
        contact=self.contacts('https://wa.me/۹۸۹۱۲۳۴۵۶۷۸۹','whatsapp')[0]
        self.assertEqual(contact['href'],'https://wa.me/989123456789')

    def test_publisher_link_does_not_replace_text_contact(self):
        import os, tempfile, db
        from main import MessageIn, save_message, list_messages
        from sender_contacts import Contact, save_contact

        previous = db.DB_PATH
        with tempfile.TemporaryDirectory() as temporary:
            db.DB_PATH = os.path.join(temporary, "ad-contact.db")
            try:
                db.init_db()
                mid, _ = save_message(
                    MessageIn(text="واتساپ https://wa.me/989123456789", sender_id="123")
                )
                save_contact(Contact("123", "Publisher", "publisher_account"))
                row = list_messages(limit=10, user={"role": "viewer"})[0]
                self.assertEqual(row["sender_link"], "https://ble.ir/publisher_account")
                self.assertEqual(row["sender_contact_role"], "publisher")
                self.assertEqual(
                    row["ad_contacts"][0]["href"], "https://wa.me/989123456789"
                )
                with db.connect() as con:
                    self.assertEqual(
                        con.execute(
                            "SELECT text FROM messages WHERE id=?", (mid,)
                        ).fetchone()[0],
                        "واتساپ https://wa.me/989123456789",
                    )
            finally:
                db.DB_PATH = previous


if __name__ == "__main__":
    unittest.main()
