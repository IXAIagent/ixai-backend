"use client";

import { useEffect, useState } from "react";

type DashboardData = {
  mode: string;
  summary: string;
  alerts: any[];
  stocks: any[];
  crypto: any[];
  cash: number;
};

export default function Home() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/dashboard/dev-real-summary`
        );

        if (!res.ok) {
          throw new Error("API request failed");
        }

        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error("Dashboard error:", err);
        setError("Failed to fetch");
      }
    }

    fetchData();
  }, []);

  if (error) {
    return <div style={{ color: "red" }}>{error}</div>;
  }

  if (!data) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>IXAI Dashboard</h1>
      <p>Mode: {data.mode}</p>

      <h2>Summary</h2>
      <p>{data.summary}</p>

      <h2>Alerts</h2>
      {data.alerts.length === 0 ? (
        <p>No alerts</p>
      ) : (
        data.alerts.map((a, i) => <p key={i}>{a.message}</p>)
      )}

      <h2>Stocks</h2>
      {data.stocks.length === 0 ? (
        <p>No stock positions</p>
      ) : (
        data.stocks.map((s, i) => (
          <p key={i}>
            {s.symbol} - {s.quantity} shares
          </p>
        ))
      )}

      <h2>Crypto</h2>
      {data.crypto.length === 0 ? (
        <p>No crypto</p>
      ) : (
        data.crypto.map((c, i) => (
          <p key={i}>
            {c.symbol} - {c.value}
          </p>
        ))
      )}

      <h2>Cash</h2>
      <p>{data.cash}</p>
    </div>
  );
}