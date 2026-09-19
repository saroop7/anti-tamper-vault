// live: null = "connecting…", true = "live", false = "demo mode / offline"
export default function ConnDot({ live }) {
  const cls = live === null ? "" : live ? "live" : "mock";
  const text = live === null ? "connecting…" : live ? "live · backend connected" : "demo mode · backend offline";
  return (
    <div className="conn">
      <span className={"dot " + cls}></span>
      <span>{text}</span>
    </div>
  );
}
