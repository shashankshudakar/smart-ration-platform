import qrcode
import io
import base64
import json

async def generate_qr_code(data):
    try:
        qr_data = data if isinstance(data, str) else json.dumps(data)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1e1b4b", back_color="white")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"QR Code generation error: {e}")
        raise Exception("Failed to generate QR code")
