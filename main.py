import os
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Hard-code some constants for demonstration:
MIN_LIQUIDITY_USD = 2000.0

# Official mint addresses:
USDC_MINT = "EPjFWdd5AufqSSqeM2qVPxhC4ZcTzztR5yYLFy5PV6"
WSOL_MINT = "So11111111111111111111111111111111111111112"

# For a real sniper, you'd fetch current SOL price from an API
ASSUMED_SOL_PRICE = 24.0  # Example: $24 per SOL

@app.route("/helis-webhook", methods=["POST"])
def helis_webhook():
    """
    Helius will POST a JSON array of transaction notifications to this endpoint.
    Each element in the array represents a transaction that triggered the webhook.
    """
    try:
        notifications = request.get_json()  # a list of tx notifications

        for tx_notification in notifications:
            # Only care about "CREATE_POOL" (new Raydium pool)
            if tx_notification.get("type") != "CREATE_POOL":
                continue
            
            signature = tx_notification.get("signature")
            slot = tx_notification.get("slot")
            timestamp = tx_notification.get("timestamp")
            
            # We look at tokenTransfers to see how much USDC or wSOL is deposited
            token_transfers = tx_notification.get("tokenTransfers", [])
            
            # Track how many USDC and wSOL were added in total for this pool creation
            total_usdc_deposited = 0.0
            total_wsol_deposited = 0.0
            
            # Keep track of "other token" (potential brand-new token)
            # We'll guess if a token isn't USDC or wSOL, it might be the new token
            # In reality, you'd do a bit more logic to confirm which mint is new
            potential_new_token_mints = set()
            
            for transfer in token_transfers:
                mint = transfer.get("mint")
                token_amount = transfer.get("tokenAmount", 0.0)
                
                # If user is "fromUserAccount" is non-empty, it might be the user depositing
                # Typically a deposit has fromUserAccount = "some user" -> toUserAccount = pool
                # For simplicity, we just see if it matches USDC or wSOL
                if mint == USDC_MINT:
                    total_usdc_deposited += token_amount
                elif mint == WSOL_MINT:
                    total_wsol_deposited += token_amount
                else:
                    # This could be the brand-new token side
                    # If "fromUserAccount" is not empty, they're depositing a new token
                    from_user = transfer.get("fromUserAccount", "")
                    if from_user != "":
                        # Potential new token
                        potential_new_token_mints.add(mint)
            
            # Now let's compute approximate USD from wSOL
            approximate_wsol_in_usd = total_wsol_deposited * ASSUMED_SOL_PRICE
            
            # Combined
            total_liquidity_usd = total_usdc_deposited + approximate_wsol_in_usd
            
            # Check if it meets our min $2k condition
            if total_liquidity_usd >= MIN_LIQUIDITY_USD:
                # We have a new pool with >= $2k in stable/wSOL side
                # Print relevant data
                print("="*60)
                print(f"[New Pool Detected] Signature: {signature}")
                print(f" Slot: {slot}, Timestamp: {timestamp}")
                print(f" USDC Deposited: {total_usdc_deposited:,.2f}")
                print(f" wSOL Deposited: {total_wsol_deposited:,.4f} (~${approximate_wsol_in_usd:,.2f})")
                print(f" Approx total $ in pool (from USDC/wSOL side): ${total_liquidity_usd:,.2f}")

                # Potential new token mints
                if potential_new_token_mints:
                    # In many cases, there's exactly one "other" token
                    # We'll just list them all
                    for token_mint in potential_new_token_mints:
                        print(f" Potential new token mint: {token_mint}")
                        # This is the token you'd likely want to 'snipe' if you want this new pair
                else:
                    print(" [!] No 'other' token mint found. Possibly no new token or special case.")
                
                print("="*60 + "\n")

        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Dev server example (not recommended for production)
    app.run(host="0.0.0.0", port=5000, debug=True)
