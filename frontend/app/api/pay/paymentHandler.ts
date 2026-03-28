import { NextResponse } from "next/server";

export type PaymentPayload = {
  wallet?: string;
  amount?: number;
  cart?: Array<{ id: string | number; quantity: number; price: string | number }>;
  proof?: {
    signature?: string; // For Solana
    tx_hash?: string;   // For TON
    boc?: string;       // For TON
  };
};

export async function handlePayment(request: Request, chain: "solana" | "ton") {
  let payload: PaymentPayload;

  try {
    payload = (await request.json()) as PaymentPayload;
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload." }, { status: 400 });
  }

  if (!payload.wallet || typeof payload.amount !== "number") {
    return NextResponse.json({ error: "wallet and amount are required." }, { status: 400 });
  }

  // SECURITY: The backend 'store' service MUST recalculate the total amount from the cart.
  // Do NOT trust the 'amount' field from the client for the final charge.

  const verifierUrl = process.env.STORE_PAYMENTS_URL;

  if (!verifierUrl) {
    console.error(`STORE_PAYMENTS_URL not set. Cannot verify ${chain} payment.`);
    return NextResponse.json({ error: "Payment verification configuration missing." }, { status: 500 });
  }

  try {
    const response = await fetch(verifierUrl, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({ ...payload, chain }),
      cache: "no-store",
    });

    // Safely parse JSON error details, falling back to status text for 502/503 HTML pages
    let data;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = { error: `Upstream service error: ${response.statusText}` };
    }

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`Failed to forward payment verification to store service for chain: ${chain}`, error);
    return NextResponse.json({ error: "Payment verification service is unavailable." }, { status: 503 });
  }
}