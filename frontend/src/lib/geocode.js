import { useEffect, useState } from "react";

// Turns lat/lng into a human-readable place name instead of raw
// coordinates. Uses OpenStreetMap's free Nominatim API (no key needed).
// Cached in localStorage (keyed to ~11m precision) so re-rendering the
// same records on every poll doesn't refetch, and lookups are
// staggered ~1.1s apart to respect Nominatim's 1 request/sec usage policy.
const GEO_CACHE_KEY = "geoLabelCache";

let geoCache = new Map();
try {
  geoCache = new Map(Object.entries(JSON.parse(localStorage.getItem(GEO_CACHE_KEY)) || {}));
} catch (e) {}

function saveGeoCache() {
  try {
    localStorage.setItem(GEO_CACHE_KEY, JSON.stringify(Object.fromEntries(geoCache)));
  } catch (e) {}
}

function geoCacheKey(lat, lng) {
  return `${Number(lat).toFixed(4)},${Number(lng).toFixed(4)}`;
}

export function getCachedGeoLabel(lat, lng) {
  return geoCache.get(geoCacheKey(lat, lng)) || null;
}

async function reverseGeocode(lat, lng) {
  const key = geoCacheKey(lat, lng);
  if (geoCache.has(key)) return geoCache.get(key);
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=14&addressdetails=1`,
      { headers: { "Accept-Language": "en" } }
    );
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    const a = data.address || {};
    const locality = a.suburb || a.neighbourhood || a.village || a.town || a.city_district || a.hamlet;
    const city = a.city || a.town || a.county;
    const label = [locality, city, a.state].filter(Boolean).join(", ") || data.display_name || null;
    geoCache.set(key, label);
    saveGeoCache();
    return label;
  } catch (e) {
    return null; // leave the coordinates as the fallback display
  }
}

// chain onto one queue so concurrent lookups (poll + filter re-renders)
// don't fire overlapping bursts of requests at Nominatim
let geoResolveQueue = Promise.resolve();
function enqueueGeocode(lat, lng) {
  const result = geoResolveQueue.then(async () => {
    const label = await reverseGeocode(lat, lng);
    await new Promise((res) => setTimeout(res, 1100));
    return label;
  });
  geoResolveQueue = result.catch(() => {});
  return result;
}

export function hasGeo(lat, lng) {
  return lat !== null && lat !== undefined && lng !== null && lng !== undefined;
}

// resolves a lat/lng to a place name, falling back to the raw coordinates
// if the lookup fails; re-renders once the label (or fallback) is ready
export function useGeoLabel(lat, lng) {
  const [label, setLabel] = useState(() => (hasGeo(lat, lng) ? getCachedGeoLabel(lat, lng) : null));

  useEffect(() => {
    if (!hasGeo(lat, lng)) return;
    const cached = getCachedGeoLabel(lat, lng);
    if (cached) {
      setLabel(cached);
      return;
    }
    let cancelled = false;
    setLabel(null);
    enqueueGeocode(lat, lng).then((result) => {
      if (cancelled) return;
      setLabel(result || `${Number(lat).toFixed(5)}, ${Number(lng).toFixed(5)}`);
    });
    return () => {
      cancelled = true;
    };
  }, [lat, lng]);

  return label;
}
