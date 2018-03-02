## -*- coding: utf-8 -*-

from openerp import models, fields, api, _, tools
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import shutil
import logging
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, float_compare
from odoo.tools.safe_eval import safe_eval
import odoo.addons.decimal_precision as dp
_logger = logging.getLogger(__name__)
MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}
# Since invoice amounts are unsigned, this is how we know if money comes in or goes out
MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'in_refund': 1,
    'in_invoice': -1,
    'out_refund': -1,
}

class Accountpayment(models.Model):
	_inherit ='account.payment'
  	type_change = fields.Float(string='Tipo de Cambio', required=False,  help='Tipo de cambio especifico para los pagos', digits=(12, 4))
	is_dolar = fields.Boolean(string="Es dolar", default=False)
  	@api.onchange('currency_id','payment_date')
  	def payment_change(self):
		currency_obj = self.env['res.currency']
  		if self.currency_id.name <>'MXN':
			currency = currency_obj.search([('name', '=','USD')])
			rate_obj=self.env['res.currency.rate']
			payment=  self.payment_date + ' 00:00:00'
			rates = rate_obj.search([('currency_id', '=',currency.id),('name', '>=', self.payment_date + ' 00:00:00'),
                        ('name', '<=', self.payment_date + ' 23:59:59')])
			if len(rates) > 0:
				rate_id = rates and max(rates)
				self.type_change = rate_id.rate2
			else:
				rates = rate_obj.search([('currency_id', '=', currency.id)])
				rate_id =rates and max(rates)
				self.type_change = rate_id.rate2
			self.is_dolar = True
  		else:
			self.type_change=1
			self.is_dolar = False

  	def _create_payment_entry(self,amount):
		#raise UserError(_("ENTROO: \n%s ") % (self.type_change))
  		aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
  		invoice_currency = False
  		if self.invoice_ids and all([x.currency_id == self.invoice_ids[0].currency_id for x in self.invoice_ids]):
  			invoice_currency = self.invoice_ids[0].currency_id
		#raise UserError(_("ENTROO2: \n%s ") % (self.type_change))
  		debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields2(self.type_change,self.is_dolar,amount, self.currency_id, self.company_id.currency_id, invoice_currency)
  		#raise UserError(_("ENTROO: \n%s ") % (debit))
  		move= self.env['account.move'].create(self._get_move_vals())
  		counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
  		#_logger.info(_("ENTROO debit: \n%s ") % (debit))
		#_logger.info(_("ENTROO credit: \n%s  ") %  (credit) )
		#_logger.info(_("ENTROO  amount_currency: \n%s  ") % (amount_currency))
		#_logger.info(_("ENTROO  currency: \n%s  ") % (currency_id))
		#_logger.info(_("ENTROO: metodo get_move_vals() \n%s  ") %  (self._get_move_vals()))
  		counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
		#_logger.info(_("ENTROO: self.invoice_ids\n%s  ") % (self.invoice_ids))
		#_logger.info(_("self._get_counterpart_move_line_vals(self.invoice_ids) \n%s  ") % (self._get_counterpart_move_line_vals(self.invoice_ids)))
  		counterpart_aml_dict.update({'currency_id': currency_id})
  		counterpart_aml = aml_obj.create(counterpart_aml_dict)
		#_logger.info(_("counterpart_aml_dict: \n%s  ") % (counterpart_aml_dict))
  		if self.payment_difference_handling == 'reconcile' and self.payment_difference:
			#_logger.info(_("entro al if \n "))
			writeoff_line = self._get_shared_move_line_vals(0, 0, 0, move.id, False)
			#_logger.info(_("self._get_shared_move_line_vals(0, 0, 0, move.id, False): \n%s  ") % (
			#	self._get_shared_move_line_vals(0, 0, 0, move.id, False)))
			amount_currency_wo, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(
				self.payment_difference, self.currency_id, self.company_id.currency_id, invoice_currency)[2:]
			#_logger.info(_("ENTROO  amount_currency: \n%s  ") % (amount_currency_wo))
			#_logger.info(_("ENTROO  currency_id: \n%s  ") % (currency_id))
			total_residual_company_signed = sum(invoice.residual_company_signed for invoice in self.invoice_ids)
			total_payment_company_signed = self.currency_id.with_context(date=self.payment_date).compute(self.amount,
																										 self.company_id.currency_id)
			#_logger.info(_("total_residual_company_signed\n%s  ") % (total_residual_company_signed))
			#_logger.info(_("total_payment_company_signed  \n%s  ") % (total_payment_company_signed ))
			if self.invoice_ids[0].type in ['in_invoice', 'out_refund']:
				amount_wo = total_payment_company_signed - total_residual_company_signed
			else:
				amount_wo = total_residual_company_signed - total_payment_company_signed
			if amount_wo > 0:
				debit_wo = amount_wo
				credit_wo = 0.0
				amount_currency_wo = abs(amount_currency_wo)
			else:
				debit_wo = 0.0
				credit_wo = -amount_wo
				amount_currency_wo = -abs(amount_currency_wo)
			#_logger.info(_("debit_wo\n%s  ") % (debit_wo))
			#_logger.info(_("credit_wo  \n%s  ") % (credit_wo ))
			#_logger.info(_("amount_currency_wo \n%s  ") % (amount_currency_wo))
			writeoff_line['name'] = _('Counterpart')
			writeoff_line['account_id'] = self.writeoff_account_id.id
			writeoff_line['debit'] = debit_wo
			writeoff_line['credit'] = credit_wo
			writeoff_line['amount_currency'] = amount_currency_wo
			writeoff_line['currency_id'] = currency_id
			#_logger.info(_("writeoff_line\n%s  ") % (writeoff_line))
			writeoff_line = aml_obj.create(writeoff_line)
			if counterpart_aml['debit']:
				counterpart_aml['debit'] += credit_wo - debit_wo
				#_logger.info(_("counterpart_aml['debit']\n%s  ") % (counterpart_aml['debit']))
			if counterpart_aml['credit']:
				counterpart_aml['credit'] += debit_wo - credit_wo
				#_logger.info(_("counterpart_aml['credit'] \n%s  ") % (counterpart_aml['credit'] ))
			counterpart_aml['amount_currency'] -= amount_currency_wo


		self.invoice_ids.register_payment(counterpart_aml)
		#_logger.info(_("counterpart_aml \n%s  ") % (counterpart_aml))
		if not self.currency_id != self.company_id.currency_id:
			amount_currency = 0
		liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
		liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
		aml_obj.create(liquidity_aml_dict)
		#_logger.info(_("liquidity_aml_dict \n%s  ") % (liquidity_aml_dict))
		move.post()
		return move

	@api.model
	def default_get(self, fields):
		rec = super(Accountpayment, self).default_get(fields)
		invoice_defaults = self.resolve_2many_commands('invoice_ids', rec.get('invoice_ids'))
		_logger.info(_("numero de invoices %s")%(invoice_defaults))
		if invoice_defaults and len(invoice_defaults) == 1:
			invoice = invoice_defaults[0]
			rec['communication'] = invoice['reference'] or invoice['name'] or invoice['number']
			rec['currency_id'] = invoice['currency_id'][0]
			rec['payment_type'] = invoice['type'] in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
			rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice['type']]
			rec['partner_id'] = invoice['partner_id'][0]
			rec['amount'] = invoice['residual']
		return rec


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def compute_amount_fields2(self, change,is_dolar,amount, src_currency, company_currency, invoice_currency=False):
		amount_currency = False
		currency_id = False
		if src_currency and src_currency != company_currency:
			if is_dolar == True:
				amount_currency = amount
				# amount = src_currency.with_context(self._context).compute(amount, company_currency)
				amount = amount * change
				currency_id = src_currency.id
			elif is_dolar == False:
				amount_currency = amount
				amount = amount
				#amount = amount * change
				currency_id = src_currency.id
		# raise UserError(_("ENTROO a compute: \n%s ") % (amount))
		debit = amount > 0 and amount or 0.0
		credit = amount < 0 and -amount or 0.0
		if invoice_currency and invoice_currency != company_currency and not amount_currency:
			amount_currency = src_currency.with_context(self._context).compute(amount, invoice_currency)
			currency_id = invoice_currency.id
		return debit, credit, amount_currency, currency_id

class AccountPayment(models.Model):
	_inherit="account.payment"
	@api.one
	@api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id')
	def _compute_payment_difference(self):
		if len(self.invoice_ids) == 0:
			#_logger.info(_("entro :$"))
			return
		if self.invoice_ids[0].type in ['in_invoice', 'out_refund']:
			self.payment_difference = self.amount - self._compute_total_invoices_amount()
			#_logger.info(_("self._compute_total_invoices_amount()IFF    %s") % (self._compute_total_invoices_amount()))
		elif self.is_dolar == True:
				self.payment_difference = (self.type_change * self.amount) - self._compute_total_invoices_amount2()
				#_logger.info(_(" el iff self._compute_total_invoices_amount()IFF    %s") % (self._compute_total_invoices_amount2()))
		else:
			self.payment_difference = self._compute_total_invoices_amount() - self.amount
			#_logger.info(_("else     self._compute_total_invoices_amount()IFF    %s") % (self._compute_total_invoices_amount()))
class account_abstract_payment(models.AbstractModel):
	_inherit = "account.abstract.payment"
	def _compute_total_invoices_amount2(self):
		payment_currency = self.currency_id or self.journal_id.currency_id or self.journal_id.company_id.currency_id or self.env.user.company_id.currency_id
		invoices = self._get_invoices()
		if all(inv.currency_id == payment_currency for inv in invoices):
			total = sum(invoices.mapped('residual_signed'))
			#raise UserError(_("compute total invoice amount2 %s")%(total))
		else:
			total = 0
			for inv in invoices:
				if inv.company_currency_id != payment_currency:
					total += inv.company_currency_id.with_context(date=self.payment_date).compute(inv.residual_company_signed, payment_currency)
				else:
					total += inv.residual_company_signed
		return abs(total)

class account_register_payments(models.TransientModel):
	_inherit = 'account.register.payments'
	type_change = fields.Float(string='Tipo de Cambio', required=False, help='Tipo de cambio especifico para los pagos',
							   digits=(12, 4))
	is_dolar = fields.Boolean(string="Es dolar", default=False)
	def _get_invoices(self):
		return self.env['account.invoice'].browse(self._context.get('active_ids'))
	@api.model
	def default_get(self, fields):
		rec = super(account_register_payments, self).default_get(fields)
		context = dict(self._context or {})
		active_model = context.get('active_model')
		active_ids = context.get('active_ids')
		if not active_model or not active_ids:
			raise UserError(_("Programmation error: wizard action executed without active_model or active_ids in context."))
		if active_model != 'account.invoice':
			raise UserError(_("Programmation error: the expected model for this action is 'account.invoice'. The provided one is '%d'.") % active_model)
		invoices = self.env[active_model].browse(active_ids)
		if any(invoice.state != 'open' for invoice in invoices):
			raise UserError(_("You can only register payments for open invoices"))
		if any(inv.commercial_partner_id != invoices[0].commercial_partner_id for inv in invoices):
			raise UserError(_("In order to pay multiple invoices at once, they must belong to the same commercial partner."))
		if any(MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type] != MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type] for inv in invoices):
			raise UserError(_("You cannot mix customer invoices and vendor bills in a single payment."))
		if any(inv.currency_id != invoices[0].currency_id for inv in invoices):
			raise UserError(_("In order to pay multiple invoices at once, they must use the same currency."))
		total_amount = sum(inv.residual * MAP_INVOICE_TYPE_PAYMENT_SIGN[inv.type] for inv in invoices)
		communication = ' '.join([ref for ref in invoices.mapped('reference') if ref])
		rec.update({
			'amount': abs(total_amount),
            'currency_id': invoices[0].currency_id.id,
            'payment_type': total_amount > 0 and 'inbound' or 'outbound',
            'partner_id': invoices[0].commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
            'communication': communication,
        })
		return rec
	def get_payment_vals(self):
		return {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': self.communication,
            'invoice_ids': [(4, inv.id, None) for inv in self._get_invoices()],
            'payment_type': self.payment_type,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'partner_type': self.partner_type,
        }
	@api.multi
	def create_payment(self):
		payment = self.env['account.payment'].create(self.get_payment_vals())
		payment.post()
		return {'type': 'ir.actions.act_window_close'}