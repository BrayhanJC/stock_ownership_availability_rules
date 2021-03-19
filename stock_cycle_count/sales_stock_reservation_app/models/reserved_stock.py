# -*- coding: utf-8 -*-

from odoo import models, fields, exceptions, api, _
from odoo.exceptions import Warning, UserError
from odoo.tools.float_utils import float_round

# Inherited Sale Order
class StockReserveSaleOrder(models.Model):
	_inherit = 'sale.order'

	stock_reservation = fields.Boolean( string="Enable Stock Reservation", copy=False)
	check_stock = fields.Boolean( string="Check Stock", copy=False,default = False)
	reserved_stock_ids = fields.One2many('reserved.stock','sale_order', string='Stock Reserve', readonly="1")

	@api.multi
	def reserve_stock_button(self):
		xml_id = 'sales_stock_reservation_app.reserved_stock_tree_view'
		tree_view_id = self.env.ref(xml_id).id
		xml_id = 'sales_stock_reservation_app.reserved_stock_form_view'
		form_view_id = self.env.ref(xml_id).id
		return {
			'name': _('Reserved Stock'),
			'res_model': 'reserved.stock',
			'type': 'ir.actions.act_window',
			'view_type': 'form',
			'view_mode': 'tree,form',
			'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
			'domain': [('sale_order', 'in', self.ids)],
		}

	@api.multi
	def cancel_reserved_stock(self):
		self.ensure_one()
		cancel_reserve_stock = self.env['reserved.stock'].search([('state', '=', 'reserved'),('sale_order', '=', self.id),('order_line_id','in', self.order_line.ids)], limit=1)
		for reserve in cancel_reserve_stock:
			picking_ids = self.env['stock.picking'].search([('origin', '=', self.name),('location_dest_id', '=', reserve.location_dest_id.id)], order='id DESC')
			product_return_moves = []
			for picking in picking_ids:
				for move in picking.move_lines:
					quantity = move.product_uom_qty
					quantity = float_round(quantity, precision_rounding=move.product_uom.rounding)
					product_return_moves.append((0, 0, {
						'product_id': move.product_id.id,
						'quantity': quantity,
						'move_id': move.id,
						'to_refund_so': True,
						}))
				location_id = picking.location_id.id
				if picking.picking_type_id.return_picking_type_id.default_location_dest_id.return_location:
					location_id = picking.picking_type_id.return_picking_type_id.default_location_dest_id.id
				stock_return = self.env['stock.return.picking'].create({
						'product_return_moves' : product_return_moves,
						'picking_id': picking.id,
						'original_location_id': picking.location_id.id,
						'parent_location_id': picking.picking_type_id.warehouse_id and picking.picking_type_id.warehouse_id.view_location_id.id or picking.location_id.location_id.id,
						'location_id': location_id  
					})
				if stock_return:
					new_picking_id, pick_type_id = stock_return.with_context(active_ids=picking.ids, active_id=picking.ids[0])._create_returns()
					new_picking = self.env['stock.picking'].browse(new_picking_id)
					immediate_transfer = self.env['stock.immediate.transfer'].create({'pick_id': new_picking.id})
					if new_picking.mapped('move_lines').filtered(lambda move: move.state in ['confirmed', 'waiting','partially_available']):
						for move in new_picking.pack_operation_product_ids:
							move.qty_done = reserve.reserve_qty
						for move in new_picking.move_lines:
							move.product_uom_qty = reserve.reserve_qty
						new_picking.action_assign()
						immediate_transfer.process()
					else:
						for move in new_picking.pack_operation_product_ids:
							move.qty_done = reserve.reserve_qty
						for move in new_picking.move_lines:
							move.product_uom_qty = reserve.reserve_qty
						new_picking.action_assign()
						immediate_transfer.process()
					self.check_stock = False
		cancel_reserve_stock_ids = self.env['reserved.stock'].search([('state', '=', 'reserved'),('sale_order', '=', self.id),('order_line_id','in', self.order_line.ids)])
		cancel_reserve_stock_ids.cancel_reserved()

#  Reserved Stock
class ReservedStock(models.Model):
	_name = 'reserved.stock'
	_description = "Reserved Stock from Sales"

	name = fields.Char(string="Name", readonly=True, required=True, copy=False, default='New')
	state = fields.Selection([
		('draft', 'Draft'),('reserved', 'Reserved'),('cancelled', 'Cancelled')],
		string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', track_sequence=3, default='draft')
	reference = fields.Char('Reference')
	sale_order = fields.Many2one( 'sale.order', string="Sale Order")
	order_line_id = fields.Many2one( 'sale.order.line', string="Order Line")
	product_id = fields.Many2one( 'product.product', string="Product")
	product_qty = fields.Float( string="Order Quantity")
	user_id = fields.Many2one( 'res.users', 'Reserve Request By')
	reserve_qty = fields.Float( string="Reserve Quantity")
	location_id = fields.Many2one('stock.location', string="Source Location")
	location_dest_id = fields.Many2one('stock.location', string="Destination Location")
	view_on_sale = fields.Many2one('sale.order')

	@api.model
	def create(self, vals):
		seq = self.env['ir.sequence'].next_by_code('reserved.stock') or '/'
		vals['name'] = seq
		return super(ReservedStock, self).create(vals)

	@api.multi
	def action_reserved(self):
		self.write({'state':'reserved'})
		return 

	@api.multi
	def cancel_reserved(self):
		self.write({'state':'cancelled'})
		return 

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: