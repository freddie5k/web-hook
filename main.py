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
        for tx_notification in notifications:
            # Basic fields
            signature = tx_notification.get("signature")
            # The 'instructions' field might contain detailed info about each instruction
            instructions = tx_notification.get("instructions", [])

            # Parse each instruction
            for instr in instructions:
                program_id = instr.get("programId")
                # The 'parsed' field might show the specific instruction name, e.g. 'initialize_pool'
                parsed = instr.get("parsed", {})
                if parsed.get("type") == "initialize_pool":
                    print(f"[Webhook] New pool initialized in tx {signature}")

                    # Here, you'd parse the new token mint or pool addresses
                    # Possibly check if it's truly a brand-new token
                    # Then proceed to fetch liquidity data, do your sniper logic, etc.

        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # This runs a simple dev server on port 5000
    # In production, run via gunicorn or another WSGI server.
    app.run(host="0.0.0.0", port=5000, debug=True)
