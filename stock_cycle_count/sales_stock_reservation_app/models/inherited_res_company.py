# -*- coding: utf-8 -*-


from odoo import fields, models

class Company(models.Model):
	_inherit = 'res.company'

	location_id = fields.Many2one('stock.location',string="Source Location")
	location_dest_id = fields.Many2one('stock.location',string="Destination Location")

	
