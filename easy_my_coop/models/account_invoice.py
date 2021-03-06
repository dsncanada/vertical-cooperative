# -*- coding: utf-8 -*-
from datetime import datetime

from openerp import api, fields, models, _

class account_invoice(models.Model):
    _inherit = 'account.invoice'
    
    subscription_request = fields.Many2one('subscription.request', string='Subscription request')
    release_capital_request = fields.Boolean(string='Release of capital request')
    
    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        values = super(account_invoice, self)._prepare_refund(invoice, date_invoice, date, description, journal_id)
        values['release_capital_request'] = self.release_capital_request
        
        return values
    
    def set_cooperator_effective(self, effective_date):
        # flag the partner as a effective member
        obj_sequence = self.env['ir.sequence']
        
        mail_template_name = 'Payment Received Confirmation - Send By Email'
        
        # if not yet cooperator we generate a cooperator number
        if self.partner_id.member == False :
            sequence_id = obj_sequence.search([('name','=','Subscription Register')])[0]
            sub_reg_num = sequence_id.next_by_id()
            self.partner_id.write({'member':True,
                                   'cooperator_register_number':int(sub_reg_num)})
        else:
            mail_template_name = 'Share Increase - Payment Received Confirmation - Send By Email'
        sequence_operation = obj_sequence.search([('name','=','Register Operation')])[0]
        sub_reg_operation = sequence_operation.next_by_id()
        
        for line in self.invoice_line_ids:
            sub_reg = self.env['subscription.register'].create(
                               {'name':sub_reg_operation,
                                'register_number_operation':int(sub_reg_operation),
                                'partner_id':self.partner_id.id,
                                'quantity':line.quantity,
                                'share_product_id':line.product_id.id,
                                'share_unit_price':line.price_unit,
                                'date':effective_date,
                                'type':'subscription'})
            self.env['share.line'].create({'share_number':line.quantity,
                                           'share_product_id':line.product_id.id,
                                           'partner_id':self.partner_id.id,
                                           'share_unit_price':line.price_unit,
                                           'effective_date':effective_date})
        
        email_template_obj = self.env['mail.template']
        certificat_email_template = email_template_obj.search([('name', '=', mail_template_name)])[0]
        # we send the email with the certificat in attachment 
        certificat_email_template.send_mail(self.partner_id.id, False)
        
        return True
    
    def post_process_confirm_paid(self, effective_date):
        self.set_cooperator_effective(effective_date) 
               
        return True
    
    @api.multi                
    def confirm_paid(self):
        for invoice in self:
            super(account_invoice, invoice).confirm_paid()
            if invoice.partner_id.cooperator and invoice.release_capital_request and invoice.type == 'out_invoice':
                effective_date = datetime.now().strftime("%d/%m/%Y")
                #take the effective date from the payment. by default the confirmation date is the payment date
                if invoice.payment_move_line_ids :
                    move_line = invoice.payment_move_line_ids[0]
                    effective_date = move_line.date
                
                invoice.subscription_request.state = 'paid'
                invoice.post_process_confirm_paid(effective_date)        
        return True
    
    @api.multi
    def invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        self.ensure_one()
        self.sent = True
        return self.env['report'].get_action(self, 'easy_my_coop.report_sexy_invoice')