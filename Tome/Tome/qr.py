import base64
from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


def build_qr_data_uri(payload):
    """Return a base64-encoded SVG data URI for the supplied payload."""
    if not payload:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(str(payload))
    qr.make(fit=True)

    image = qr.make_image(image_factory=SvgPathImage)
    buffer = BytesIO()
    image.save(buffer)
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/svg+xml;base64,{encoded}'
