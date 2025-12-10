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

# This will store the audio URL for the current call
current_audio_url = None

# Create Plivo client
client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)


@app.route("/", methods=["GET"])
def home():
    return jsonify(
        {
            "status": "running",
            "message": "Plivo CRM Webhook Receiver is active",
        }
    ), 200


@app.route("/webhook/test", methods=["POST"])
def test_webhook():
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
      "audio_url": "https://your-audio-url.mp3"  (optional)
    }
    """
    try:
        data = request.get_json() or {}

        customer_phone = data.get("phone")
        customer_name = data.get("name", "Customer")

        # 1) Take audio_url from JSON if present, else use default
        message_url = data.get("audio_url", RECORDED_MESSAGE_URL)

        if not customer_phone:
            return jsonify(
                {"success": False, "error": "Phone number is required"}
            ), 400

        # 2) Store this URL globally so /answer_call can use it
        global current_audio_url
        current_audio_url = message_url

        # 3) Initiate call via Plivo
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
    This is called by Plivo when the call is answered.
    It will play the audio_url sent from the CRM webhook.
    """
    try:
        global current_audio_url

        # If for some reason current_audio_url is empty, use default
        play_url = current_audio_url or RECORDED_MESSAGE_URL

        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{play_url}</Play>
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
