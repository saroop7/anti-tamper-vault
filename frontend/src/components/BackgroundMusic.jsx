import { useCallback, useEffect, useRef, useState } from "react";
import { PlayIcon, PauseIcon, PrevIcon, NextIcon, VolumeOnIcon, VolumeOffIcon, DragHandleIcon } from "../icons";

// A pool of currently-live NCS (NoCopyrightSounds) tracks, verified
// individually -- NCS does sometimes pull tracks from its catalog (e.g.
// Alan Walker's "Fade" and Tobu's "Candyland" were both removed after
// their artists' contracts with the label expired), so this only includes
// ones confirmed still up on the official channel.
const TRACKS = [
  { id: "K4DyBUG242c", title: "Cartoon, Jéja - On & On (feat. Daniel Levi)" },
  { id: "TW9d8vYrVFQ", title: "Elektronomia - Sky High" },
  { id: "x_OwcYTNbHs", title: "Jim Yosef - Firefly" },
  { id: "J2X5mJ3HDYE", title: "DEAF KEV - Invincible" },
  { id: "jK2aIUmmdP4", title: "Different Heaven & EH!DE - My Heart" },
  { id: "3nQNiWdeH2Q", title: "Janji - Heroes Tonight (feat. Johnning)" },
];

const NO_REPEAT_MS = 15 * 60 * 1000; // don't replay a track for at least 15 minutes

let apiLoadPromise = null;
function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve();
  if (apiLoadPromise) return apiLoadPromise;
  apiLoadPromise = new Promise((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      resolve();
    };
    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
  });
  return apiLoadPromise;
}

function pickNextTrack(currentId, lastPlayedAt) {
  const now = Date.now();
  const eligible = TRACKS.filter((t) => t.id !== currentId && now - (lastPlayedAt[t.id] || 0) >= NO_REPEAT_MS);
  const pool = eligible.length ? eligible : TRACKS.filter((t) => t.id !== currentId);
  return pool[Math.floor(Math.random() * pool.length)] || TRACKS[0];
}

// Browsers block autoplay-with-sound outright, so this starts muted (the
// only way any site can autoplay at all) and surfaces one button to turn
// sound on -- there's no way to force real unmuted autoplay from code.
export default function BackgroundMusic() {
  const [dismissed, setDismissed] = useState(false);
  const [muted, setMuted] = useState(true);
  const [playing, setPlaying] = useState(true);
  const [current, setCurrent] = useState(TRACKS[0]);
  const [pos, setPos] = useState(null); // null = default bottom-right via CSS

  const playerRef = useRef(null);
  const containerRef = useRef(null);
  const widgetRef = useRef(null);
  const lastPlayedAt = useRef({ [TRACKS[0].id]: Date.now() });
  const currentRef = useRef(current);
  currentRef.current = current;

  // browser-history-style navigation: `next` past the end picks a fresh
  // random (respecting the 15-minute cooldown), but if you've gone back
  // with `previous`, `next` first retraces the forward step you already took
  const historyRef = useRef([TRACKS[0]]);
  const historyIndexRef = useRef(0);

  function loadTrack(track) {
    setCurrent(track);
    playerRef.current?.loadVideoById(track.id);
    setPlaying(true);
  }

  const goNext = useCallback(() => {
    const h = historyRef.current;
    const i = historyIndexRef.current;
    if (i < h.length - 1) {
      historyIndexRef.current = i + 1;
      loadTrack(h[i + 1]);
      return;
    }
    const next = pickNextTrack(currentRef.current.id, lastPlayedAt.current);
    lastPlayedAt.current[next.id] = Date.now();
    h.push(next);
    historyIndexRef.current = h.length - 1;
    loadTrack(next);
  }, []);

  const goPrev = useCallback(() => {
    const i = historyIndexRef.current;
    if (i === 0) return; // nothing before the first track
    historyIndexRef.current = i - 1;
    loadTrack(historyRef.current[i - 1]);
  }, []);

  useEffect(() => {
    if (dismissed) return;
    let cancelled = false;
    loadYouTubeApi().then(() => {
      if (cancelled || !containerRef.current) return;
      playerRef.current = new window.YT.Player(containerRef.current, {
        videoId: current.id,
        playerVars: { autoplay: 1, mute: 1, controls: 0 },
        events: {
          onStateChange: (e) => {
            if (e.data === window.YT.PlayerState.ENDED) goNext();
            else if (e.data === window.YT.PlayerState.PLAYING) setPlaying(true);
            else if (e.data === window.YT.PlayerState.PAUSED) setPlaying(false);
          },
        },
      });
    });
    return () => {
      cancelled = true;
      playerRef.current?.destroy?.();
      playerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dismissed]);

  function togglePlay() {
    if (playing) playerRef.current?.pauseVideo();
    else playerRef.current?.playVideo();
    setPlaying((p) => !p);
  }

  function toggleMute() {
    setMuted((m) => {
      const next = !m;
      if (next) playerRef.current?.mute();
      else playerRef.current?.unMute();
      return next;
    });
  }

  // ---- drag to move, like a picture-in-picture window ------------------
  const dragRef = useRef(null);

  const onDragMove = useCallback((e) => {
    if (!dragRef.current || !widgetRef.current) return;
    const { offsetX, offsetY } = dragRef.current;
    const w = widgetRef.current.offsetWidth;
    const h = widgetRef.current.offsetHeight;
    const x = Math.min(Math.max(e.clientX - offsetX, 4), window.innerWidth - w - 4);
    const y = Math.min(Math.max(e.clientY - offsetY, 4), window.innerHeight - h - 4);
    setPos({ x, y });
  }, []);

  const onDragEnd = useCallback(() => {
    dragRef.current = null;
    document.removeEventListener("pointermove", onDragMove);
    document.removeEventListener("pointerup", onDragEnd);
  }, [onDragMove]);

  function onDragStart(e) {
    if (!widgetRef.current) return;
    const rect = widgetRef.current.getBoundingClientRect();
    dragRef.current = { offsetX: e.clientX - rect.left, offsetY: e.clientY - rect.top };
    document.addEventListener("pointermove", onDragMove);
    document.addEventListener("pointerup", onDragEnd);
  }

  useEffect(() => () => onDragEnd(), [onDragEnd]);

  if (dismissed) return null;

  const style = pos ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" } : undefined;

  return (
    <div className="bg-music" ref={widgetRef} style={style}>
      <div className="bg-music-handle" onPointerDown={onDragStart}>
        <DragHandleIcon />
        <span className="bg-music-title">{current.title}</span>
        <button className="bg-music-close" onClick={() => setDismissed(true)} aria-label="Stop music">
          ×
        </button>
      </div>
      <div ref={containerRef} />
      <div className="bg-music-controls">
        <button onClick={goPrev} aria-label="Previous track">
          <PrevIcon />
        </button>
        <button onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <button onClick={goNext} aria-label="Next track">
          <NextIcon />
        </button>
        <button onClick={toggleMute} aria-label={muted ? "Unmute" : "Mute"}>
          {muted ? <VolumeOffIcon /> : <VolumeOnIcon />}
        </button>
      </div>
    </div>
  );
}
