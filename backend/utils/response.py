from flask import jsonify


def success_response(data=None, message='操作成功', code=200):
    response = {
        'success': True,
        'message': message,
        'code': code
    }
    if data is not None:
        response['data'] = data
    return jsonify(response), code


def error_response(message, code=400, errors=None):
    response = {
        'success': False,
        'message': message,
        'code': code
    }
    if errors is not None:
        response['errors'] = errors
    return jsonify(response), code


def paginated_response(items, total, page, page_size):
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    response = {
        'success': True,
        'message': '操作成功',
        'code': 200,
        'data': {
            'items': items,
            'pagination': {
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
    }
    return jsonify(response), 200
