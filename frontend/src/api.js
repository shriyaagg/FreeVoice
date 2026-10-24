const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function req(path, options = {}) {
  const r = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail || r.statusText);
  }
  return r.json();
}

export const getDashboard = () => req("/dashboard");
export const getCalls = (status) => req(`/calls${status ? `?status=${status}` : ""}`);
export const getCall = (id) => req(`/calls/${id}`);
export const getPublicCall = (id) => req(`/calls/${id}/public`);
export const startCall = (invoice_id) =>
  req("/calls", { method: "POST", body: JSON.stringify({ invoice_id }) });
export const sendMessage = (id, text) =>
  req(`/calls/${id}/messages`, { method: "POST", body: JSON.stringify({ text }) });
export const decide = (id, approved) =>
  req(`/calls/${id}/approval`, { method: "POST", body: JSON.stringify({ approved }) });

export const createInvoice = (body) =>
  req("/invoices", { method: "POST", body: JSON.stringify(body) });