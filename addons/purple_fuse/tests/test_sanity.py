from openerp.tests.common import TransactionCase


class OdooTest(TransactionCase):

    def test_odoo_sanity(self):
        self.assertEqual(self.env.user.id, 1)
