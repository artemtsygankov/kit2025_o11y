import streamlit as st
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Load Generator", layout="centered")
st.title("🚀 Нагрузочный сервис")

target_url = st.text_input("URL целевого сервиса", value="http://app:8000/hash")
input_text = st.text_input("Строка для хэширования", value="hello world")
algorithm = st.selectbox("Алгоритм", ["sha256", "md5", "sha512"])
rps = st.slider("RPS (запросов в секунду)", 10, 500, 150)
duration = st.slider("Длительность нагрузки (сек)", 5, 60, 15)

start = st.button("▶️ Запустить нагрузку")

if start:
    st.write("⏳ Нагрузка началась...")
    total_requests = rps * duration
    success = 0
    errors = 0
    latencies = []

    def send_request():
        try:
            t0 = time.time()
            r = requests.post(target_url, json={
                "input": input_text,
                "algorithm": algorithm
            }, timeout=10)
            t1 = time.time()
            latency = (t1 - t0) * 1000
            if r.status_code == 200:
                latencies.append(latency)
                return True
        except Exception:
            pass
        return False

    with ThreadPoolExecutor(max_workers=rps * 2) as executor:
        end_time = time.time() + duration
        futures = []
        while time.time() < end_time:
            for _ in range(rps):
                futures.append(executor.submit(send_request))
            time.sleep(1)

        for f in as_completed(futures):
            if f.result():
                success += 1
            else:
                errors += 1

    st.success("Нагрузка завершена ✅")
    st.write(f"Успешных запросов: {success}")
    st.write(f"Ошибок: {errors}")

    if latencies:
        p99 = sorted(latencies)[int(len(latencies) * 0.99) - 1]
        st.write(f"p99 latency: {round(p99, 2)} ms")
        st.line_chart(latencies)
