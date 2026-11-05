"""Web Server DAT callbacks. Keep the latest complete message for each type."""
import json
import time


def onHTTPRequest(dat, request, response):
    response['statusCode'] = 404
    response['statusReason'] = 'Not Found'
    response['data'] = ''
    return response


def onWebSocketReceiveText(dat, client, data):
    root = dat.parent()
    try:
        message = json.loads(data)
        if not isinstance(message, dict):
            raise ValueError('Expected a JSON object')
        kind = message.get('type')
        if not isinstance(kind, str) or not kind:
            raise ValueError('Expected a non-empty string type')
    except (ValueError, TypeError) as error:
        root.op('last_error').text = str(error)
        return
    table = root.op('INPUT_MSGS')
    # Skip the header, including when the incoming type is literally "type".
    row = next((i for i in range(1, table.numRows) if table[i, 0].val == kind), None)
    received_ms = time.monotonic_ns() // 1_000_000
    if row is None:
        table.appendRow([kind, data, received_ms])
    else:
        table[row, 1] = data
        table[row, 2] = received_ms
    root.op('last_error').text = ''


def onWebSocketReceivePing(dat, client, data):
    dat.webSocketSendPong(client, data=data)
