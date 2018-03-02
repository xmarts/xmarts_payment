from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import shutil
import logging
_logger = logging.getLogger(__name__)

class Accountpayment(models.Model):
    _inherit = "account.payment"

    @api.one
    @api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id', 'type_change')
    def _compute_payment_difference(self):
        if len(self.invoice_ids) == 0:
            return
        if self.invoice_ids[0].type in ['in_invoice', 'out_refund']:
            self.payment_difference = self.amount - self._compute_total_invoices_amount()
        else:
            self.payment_difference = self._compute_total_invoices_amount() - self.amount