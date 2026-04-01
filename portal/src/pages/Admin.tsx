import { useEffect, useState } from "react";
import { api } from "../api/client";

export function Admin() {
  const [health, setHealth] = useState<{
    status: string;
    version: string;
    mode: string;
  } | null>(null);

  useEffect(() => {
    api.getHealth().then(setHealth);
  }, []);

  return (
    <div className="admin-page">
      <h1>Server Administration</h1>

      <div className="admin-card">
        <h2>Server Status</h2>
        {health ? (
          <table>
            <tbody>
              <tr>
                <td>Status</td>
                <td>
                  <span className={`badge ${health.status === "healthy" ? "success" : "error"}`}>
                    {health.status}
                  </span>
                </td>
              </tr>
              <tr>
                <td>Version</td>
                <td>{health.version}</td>
              </tr>
              <tr>
                <td>Mode</td>
                <td>{health.mode}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p>Loading...</p>
        )}
      </div>
    </div>
  );
}
