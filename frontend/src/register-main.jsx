import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import UserRegistrations from "./pages/UserRegistrations";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <UserRegistrations />
  </StrictMode>
);
