import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import ClientCall from "./ClientCall.jsx";

const match = window.location.pathname.match(/^\/call\/([\w-]+)/);

createRoot(document.getElementById("root")).render(
  match ? <ClientCall callId={match[1]} /> : <App />
);