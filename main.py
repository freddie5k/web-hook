from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route("/helis-webhook", methods=["POST"])
def helis_webhook():
    """
    Helius will POST a JSON array of transaction notifications to this endpoint.
    Each element in the array represents a transaction that triggered the webhook.
    """
    try:
        notifications = request.get_json()  # should be a list of tx notifications
        
        # 1) Print the entire JSON payload for debugging:
        print("Received JSON from Helius:\n", json.dumps(notifications, indent=2))
        
        # 2) Then proceed with your existing loop:
        for tx_notification in notifications:
            signature = tx_notification.get("signature")
            instructions = tx_notification.get("instructions", [])

            for instr in instructions:
                program_id = instr.get("programId")
                parsed = instr.get("parsed", {})
                if parsed.get("type") == "initialize_pool":
                    print(f"[Webhook] New pool initialized in tx {signature}")

                    # Additional logic goes here
                    # e.g., parse token mint addresses, check liquidity, etc.

        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # This runs a simple dev server on port 5000.
    # In production, you typically run via gunicorn or another WSGI server.
    app.run(host="0.0.0.0", port=5000, debug=True)
