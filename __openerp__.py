# -*- coding: utf-8 -*-
{
    'name': "Payment Xmarts",

    'summary': """Personalizaciones a pagos de diferentes monedas
       """,

    'description': """
   Personalizaciones
    """,

    'author': "Nayeli Valencia Díaz",
    'website': "http://www.xmarts.com",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base','sale','purchase','account'],
    'data': [
        'views/views.xml',
        'views/templates.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
}