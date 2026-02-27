import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/theme.css";

// App entry point — full routing and providers added in Phase 4 (UI)
function App() {
  return (
    <div>
      <h1>NetworkCrawler</h1>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
