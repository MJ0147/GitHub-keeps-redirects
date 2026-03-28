import json
import os
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SOLANA_RPC_URL = os.getenv(
    "SOLANA_RPC_URL",
    "https://api.mainnet-beta.solana.com")
TON_API_BASE = os.getenv("TON_API_BASE", "https://toncenter.com/api/v2")
TON_API_KEY = os.getenv("TON_API_KEY", "")


def _http_json(url: str, payload: dict[str, Any]
               | None = None) -> dict[str, Any]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(url=url, data=body, headers=headers,
                      method="POST" if payload is not None else "GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Network error while calling payment provider: {exc}") from exc


def process_solana_payment(wallet: str, amount: float,
                           signature: str) -> dict[str, Any]:
    if not signature:
        raise RuntimeError("Missing Solana transaction signature.")

    expected_lamports = int(Decimal(str(amount)) * Decimal("1000000000"))
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0
            },
        ],
    }
    rpc_response = _http_json(SOLANA_RPC_URL, rpc_payload)
    tx_result = rpc_response.get("result")
    if tx_result is None:
        raise RuntimeError(
            "Solana transaction not found or not finalized yet.")

    message = tx_result.get("transaction", {}).get("message", {})
    account_keys = message.get("accountKeys", [])
    addresses: list[str] = []
    for key in account_keys:
        if isinstance(key, dict):
            addresses.append(str(key.get("pubkey", "")))
        else:
            addresses.append(str(key))

    if wallet not in addresses:
        raise RuntimeError(
            "Provided wallet is not part of this Solana transaction.")

    payer_index = addresses.index(wallet)
    meta = tx_result.get("meta", {})
    pre_balances = meta.get("preBalances", [])
    post_balances = meta.get("postBalances", [])
    if payer_index >= len(pre_balances) or payer_index >= len(post_balances):
        raise RuntimeError(
            "Unable to read payer balances from Solana transaction.")

    spent_lamports = int(pre_balances[payer_index]) - \
        int(post_balances[payer_index])
    if spent_lamports < expected_lamports:
        raise RuntimeError("Solana payment amount is lower than expected.")

    return {
        "verified": True,
        "network": "solana-mainnet",
        "signature": signature,
        "wallet": wallet,
        "required_lamports": expected_lamports,
        "observed_spent_lamports": spent_lamports,
    }


def process_ton_payment(wallet: str, amount: float,
                        tx_hash: str) -> dict[str, Any]:
    if not tx_hash:
        raise RuntimeError("Missing TON transaction hash.")

    try:
        expected_nanotons = int(Decimal(str(amount)) * Decimal("1000000000"))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError("Invalid TON amount.") from exc

    query = {"address": wallet, "limit": 30}
    if TON_API_KEY:
        query["api_key"] = TON_API_KEY
    endpoint = f"{TON_API_BASE}/getTransactions?{urlencode(query)}"
    response = _http_json(endpoint)

    if not response.get("ok", False):
        raise RuntimeError("TON API returned an unsuccessful response.")

    transactions = response.get("result", [])
    matched_tx = None
    for tx in transactions:
        tx_id = tx.get("transaction_id", {})
        if tx.get("hash") == tx_hash or tx_id.get("hash") == tx_hash:
            matched_tx = tx
            break

    if matched_tx is None:
        raise RuntimeError("TON transaction hash not found for this wallet.")

    in_msg = matched_tx.get("in_msg", {})
    observed_nanotons = int(in_msg.get("value", 0))
    if observed_nanotons < expected_nanotons:
        raise RuntimeError("TON payment amount is lower than expected.")

    return {
        "verified": True,
        "network": "ton-mainnet",
        "tx_hash": tx_hash,
        "wallet": wallet,
        "required_nanotons": expected_nanotons,
        "observed_nanotons": observed_nanotons,
    }


def verify_ton_transaction(wallet_address: str, tx_hash: str) -> bool:
    if not tx_hash or not wallet_address:
        return False

    query = {"address": wallet_address, "hash": tx_hash, "limit": 1}
    if TON_API_KEY:
        query["api_key"] = TON_API_KEY
    endpoint = f"{TON_API_BASE}/getTransactions?{urlencode(query)}"

    try:
        response = _http_json(endpoint)
    except RuntimeError:
        return False

    if not response.get("ok", False):
        return False

    result = response.get("result")
    return bool(result)


def verify_solana_transaction(signature: str) -> bool:
    if not signature:
        return False

    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0
            },
        ],
    }

    try:
        rpc_response = _http_json(SOLANA_RPC_URL, rpc_payload)
    except RuntimeError:
        return False

    result = rpc_response.get("result")
    if result is None:
        return False
    
    # Ensure the transaction didn't fail on-chain
    return result.get("meta", {}).get("err") is None
