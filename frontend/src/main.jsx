import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import BoxMonitor from "./pages/BoxMonitor";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BoxMonitor />
  </StrictMode>
);
