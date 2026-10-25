// Local-only fixture based on https://open-meteo.com/en/docs.
// Synthetic values test protocol/error handling, not forecast accuracy.
const http = require("http");
http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (url.pathname !== "/v1/forecast") { res.writeHead(501); return res.end("Not modelled"); }
  const lat = Number(url.searchParams.get("latitude"));
  // Reserved fixture coordinates exercise transport failure paths.
  if (lat === 0) { res.writeHead(500, { "Content-Type": "text/html" }); return res.end("<h1>Upstream unavailable</h1>"); }
  if (lat === 1) { res.writeHead(429, { "Content-Type": "application/json", "Retry-After": "1" }); return res.end('{"error":true,"reason":"rate limit"}'); }
  if (lat === 2) { res.writeHead(401); return res.end("Unauthorized"); }
  if (lat === 3) { return setTimeout(() => { res.writeHead(504); res.end("late"); }, 20000); }
  if (url.searchParams.get("timezone") !== "Asia/Ho_Chi_Minh" || url.searchParams.get("forecast_days") !== "7" || !url.searchParams.get("daily")?.includes("precipitation_sum")) {
    res.writeHead(400); return res.end("Invalid request contract");
  }
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const start = Date.parse(today + "T00:00:00Z");
  const days = Array.from({length: 7}, (_, i) => new Date(start + i * 86400000).toISOString().slice(0, 10));
  const hours = Array.from({length: 168}, (_, i) => new Date(start + i * 3600000).toISOString().slice(0, 16));
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ latitude: lat, longitude: Number(url.searchParams.get("longitude")), utc_offset_seconds: 25200,
    daily_units: { precipitation_sum: "mm" }, hourly_units: { precipitation: "mm" },
    daily: { time: days, precipitation_sum: [0, 2, null, 4, 8, 16, 32], precipitation_probability_max: [0, 20, null, 40, 60, 80, 100], weather_code: [0, 61, null, 61, 63, 63, 65], temperature_2m_max: days.map(() => 30), temperature_2m_min: days.map(() => 22) },
    hourly: { time: hours, precipitation: hours.map(() => 0) }
  }));
}).listen(process.env.PORT || 4911);
