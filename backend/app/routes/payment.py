from flask import Blueprint

bp = Blueprint('payment', __name__)

@bp.route('/test')
def test():
    return {'message': 'Payment route working'}, 200
