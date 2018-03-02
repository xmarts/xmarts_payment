# -*- coding: utf-8 -*-
from openerp import http

# class XmartsPac(http.Controller):
#     @http.route('/xmarts_pac/xmarts_pac/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/xmarts_pac/xmarts_pac/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('xmarts_pac.listing', {
#             'root': '/xmarts_pac/xmarts_pac',
#             'objects': http.request.env['xmarts_pac.xmarts_pac'].search([]),
#         })

#     @http.route('/xmarts_pac/xmarts_pac/objects/<model("xmarts_pac.xmarts_pac"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('xmarts_pac.object', {
#             'object': obj
#         })