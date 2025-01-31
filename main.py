import os
import json
from flask import Flask, request, jsonify

# ----------------------
#  SOLANA-PY IMPORTS
# ----------------------
from solana.rpc.api import Client

app = Flask(__name__)

# Hard-code some constants for demonstration:
MIN_LIQUIDITY_USD = 2000.0

# Official mint addresses:
USDC_MINT = "EPjFWdd5AufqSSqeM2qVPxhC4ZcTzztR5yYLFy5PV6"
WSOL_MINT = "So11111111111111111111111111111111111111112"

# For a real sniper, you'd fetch current SOL price from an API
ASSUMED_SOL_PRICE = 24.0  # Example: $24 per SOL

# Example known locker addresses. In reality, you may not have any on Solana,
# or you'd have to verify a "time-lock" contract's address here.
KNOWN_LOCKING_CONTRACTS = {
    # "LockedEscrowAddressXYZ1234",
    # "MultisigOrTimelock1234abcd",
}

# ----------------------
#   HELPER FUNCTIONS
# ----------------------
def get_top_holders(token_mint: str):
    """
    Uses solana-py to retrieve up to 20 largest token accounts for 'token_mint'.
    Returns a list of dicts:
       [ { "account_address": <tokenAccountPubkey>, "token_amount": <float> }, ... ]

    NOTE:
    - If you want more than 20 accounts or prefer an indexer like Helius, you'll need
      a different approach (e.g., getProgramAccounts or Helius API).
    - This code queries mainnet-beta directly. Consider using a custom RPC or Helius endpoint
      if you need reliability or a higher rate limit.
    """
    client = Client("https://api.mainnet-beta.solana.com")
    
    # 1) get_token_largest_accounts
    largest_res = client.get_token_largest_accounts(token_mint)
    if "value" not in largest_res or not largest_res["value"]:
        return []
    
    # 2) get token supply to find decimals
    supply_res = client.get_token_supply(token_mint)
    if ("value" not in supply_res or not supply_res["value"] or 
        "decimals" not in supply_res["value"]):
        decimals = 9  # fallback if we can't fetch
    else:
        decimals = supply_res["value"]["decimals"]
    
    holders = []
    for entry in largest_res["value"]:
        token_account = entry["address"]
        raw_amount_str = entry["amount"]  # string representing raw units

        if raw_amount_str.isdigit():
            raw_amount = int(raw_amount_str)
        else:
            raw_amount = float(raw_amount_str)

        final_amount = raw_amount / (10 ** decimals)
        
        holders.append({
            "account_address": token_account,
            "token_amount": final_amount
        })

    return holders

def check_liquidity_locked(lp_mint: str, threshold_ratio: float = 0.9) -> bool:
    """
    Checks if > threshold_ratio (default 90%) of lp_mint tokens are held by a known locker address.
    Returns True if locked, else False.
    """
    holders = get_top_holders(lp_mint)
    if not holders:
        return False

    total_supply = sum(h["token_amount"] for h in holders)

    if total_supply <= 0:
        return False

    # Check if any known locker address holds > threshold_ratio of the supply
    for h in holders:
        addr = h["account_address"]
        ratio = h["token_amount"] / total_supply
        if addr in KNOWN_LOCKING_CONTRACTS and ratio >= threshold_ratio:
            return True

    return False

# ----------------------
#       FLASK ROUTE
# ----------------------
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
            
            total_usdc_deposited = 0.0
            total_wsol_deposited = 0.0
            potential_new_token_mints = set()
            
            for transfer in token_transfers:
                mint = transfer.get("mint")
                token_amount = transfer.get("tokenAmount", 0.0)
                from_user = transfer.get("fromUserAccount", "")
                
                if mint == USDC_MINT:
                    total_usdc_deposited += token_amount
                elif mint == WSOL_MINT:
                    total_wsol_deposited += token_amount
                else:
                    # If it's not USDC/wSOL, might be the new token side
                    if from_user != "":
                        potential_new_token_mints.add(mint)
            
            approximate_wsol_in_usd = total_wsol_deposited * ASSUMED_SOL_PRICE
            total_liquidity_usd = total_usdc_deposited + approximate_wsol_in_usd
            
            if total_liquidity_usd >= MIN_LIQUIDITY_USD:
                print("="*60)
                print(f"[New Pool Detected] Signature: {signature}")
                print(f" Slot: {slot}, Timestamp: {timestamp}")
                print(f" USDC Deposited: {total_usdc_deposited:,.2f}")
                print(f" wSOL Deposited: {total_wsol_deposited:,.4f} (~${approximate_wsol_in_usd:,.2f})")
                print(f" Approx total $ in pool (from USDC/wSOL side): ${total_liquidity_usd:,.2f}")

                if potential_new_token_mints:
                    for token_mint in potential_new_token_mints:
                        print(f" Potential new token mint: {token_mint}")
                        
                        # ---------------------------
                        # EXAMPLE: Check if "locked"
                        # (Typically you'd pass the LP mint, not the traded token.
                        # This is just an example.)
                        # ---------------------------
                        locked = check_liquidity_locked(token_mint)
                        if locked:
                            print(f"  => Liquidity APPEARS LOCKED for {token_mint} (based on known locker).")
                        else:
                            print(f"  => Liquidity NOT LOCKED for {token_mint} or unknown.")
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
