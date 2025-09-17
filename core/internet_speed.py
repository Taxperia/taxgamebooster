import speedtest

def list_servers(limit: int = 100):
    st = speedtest.Speedtest()
    servers = st.get_servers([])
    out = []
    for sid, lst in servers.items():
        for s in lst:
            out.append({
                "id": int(s["id"]),
                "sponsor": s["sponsor"],
                "name": s["name"],
                "country": s.get("country",""),
                "latency": s.get("latency", 0.0),
            })
    # latency bilinmiyorsa id’ye göre sırala
    out.sort(key=lambda x: (x["country"], x["name"]))
    return out[:limit]

def run_speedtest(server_id: int | None = None) -> dict:
    st = speedtest.Speedtest()
    st.get_servers()
    if server_id:
        st.get_servers([server_id])
    best = st.get_best_server()
    down = st.download()
    up = st.upload()
    return {
        "server": f"{best['sponsor']} ({best['name']})",
        "ping_ms": round(best["latency"], 2),
        "download_mbps": round(down / 1e6, 2),
        "upload_mbps": round(up / 1e6, 2),
        "server_id": int(best["id"])
    }