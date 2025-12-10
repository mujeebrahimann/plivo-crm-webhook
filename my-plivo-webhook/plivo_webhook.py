import os
import plivo
from flask import Flask, request, jsonify

app = Flask(__name__)

# Read secrets from environment variables (set in Railway)
PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")
PLIVO_PHONE = os.getenv("PLIVO_PHONE")
RECORDED_MESSAGE_URL = os.getenv(
    "RECORDED_MESSAGE_URL",
    "https://example.com/message.mp3"
)

# Create Plivo client
client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)


@app.route("/", methods=["GET"])
def home():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "running",
            "message": "Plivo CRM Webhook Receiver is active",
        }
    ), 200


@app.route("/webhook/test", methods=["POST"])
def test_webhook():
    """Simple test endpoint to verify server is working"""
    data = request.get_json() or {}
    return jsonify({"success": True, "received": data}), 200


@app.route("/webhook/crm-call", methods=["POST"])
def handle_crm_webhook():
    """
    Receives webhook from your CRM.

    Expected JSON body:
    {
      "phone": "+12025551234",
      "name": "John Doe",
      "audio_url": "https://example.com/message.mp3"  (optional)
    }
    """
    try:
        data = request.get_json() or {}

        customer_phone = data.get("phone")
        customer_name = data.get("name", "Customer")
        message_url = data.get("audio_url", RECORDED_MESSAGE_URL)

        if not customer_phone:
            return jsonify(
                {"success": False, "error": "Phone number is required"}
            ), 400

        # Initiate call via Plivo
        response = client.calls.create(
            from_=PLIVO_PHONE,
            to_=customer_phone,
            answer_url=os.getenv(
                "ANSWER_URL",
                "https://example.com/answer_call",
            ),
        )

        return jsonify(
            {
                "success": True,
                "message": f"Call initiated to {customer_name}",
                "call_id": response.request_uuid,
                "phone": customer_phone,
                "audio_url_used": message_url,
            }
        ), 200

    except plivo.exceptions.PlivoRestError as e:
        return jsonify(
            {"success": False, "error": f"Plivo API Error: {str(e)}"}
        ), 500

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Internal Server Error: {str(e)}"}
        ), 500


@app.route("/answer_call", methods=["POST"])
def answer_call():
    """
    Tells Plivo what to do when the call is answered.
    Plays the recorded message from RECORDED_MESSAGE_URL.
    """
    try:
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{RECORDED_MESSAGE_URL}</Play>
</Response>"""
        return xml_response, 200, {"Content-Type": "application/xml"}
    except Exception:
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Error playing message. Please try again later.</Speak>
</Response>"""
        return error_xml, 500, {"Content-Type": "application/xml"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
