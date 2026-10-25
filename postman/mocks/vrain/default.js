// Synthetic fixtures using the live-observed Data/station_id/value/time_point/depth shape.
// This does not establish that depth represents an interval or timestamp its end.
const http = require("http");
http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  if(url.pathname !== "/v1/stations/stats") {res.writeHead(501); return res.end("Not modelled");}
  const start = url.searchParams.get("start_time");
  const end = url.searchParams.get("end_time");
  if (!start || !end || req.headers["x-api-key"] !== "synthetic-only") {res.writeHead(403); return res.end();}
  if (start.startsWith("2000-01-01")) {res.writeHead(500, {"Content-Type":"text/html"}); return res.end("<h1>Failure</h1>");}
  if (start.startsWith("2000-01-02")) {res.writeHead(429,{"Retry-After":"1"}); return res.end("{}");}
  if (start.startsWith("2000-01-03")) {res.writeHead(401); return res.end();}
  if (start.startsWith("2000-01-04")) {return setTimeout(()=>{res.writeHead(504);res.end();},1600);}
  res.writeHead(200,{"Content-Type":"application/json"});
  res.end(JSON.stringify({Data:[{station_id:"036604",value:[{time_point:start,depth:0},{time_point:end,depth:1.2}]}]}));
}).listen(process.env.PORT || 4922);
