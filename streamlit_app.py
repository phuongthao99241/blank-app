import streamlit as st
import pandas as pd
import datetime
from prophet import Prophet
import numpy as np
import os
import plotly.express as px

st.set_page_config(
    page_title="📊 TV-Stimmungsanalyse",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar mit Firmenlogo und Name
with st.sidebar:
    #st.image("logo.png", width=200)
    st.markdown("## SentimentInsights")
    tab_choice = st.radio("Navigiere zu:", ["Dashboard", "KI-Planung", "Vergleich", "Bericht"])

st.title("📺 KI-gestützte TV-Stimmungsanalyse")

@st.cache_data
def generate_mock_comments(program, start_date, end_date):
    dates = pd.date_range(start_date, end_date)
    data = []
    for date in dates:
        for _ in range(np.random.randint(10, 20)):
            sentiment = np.random.choice(["positive", "neutral", "negative"], p=[0.6, 0.25, 0.15])
            data.append({
                "date": date,
                "program": program,
                "text": f"Kommentar zu {program} am {date}",
                "sentiment": sentiment
            })
    return pd.DataFrame(data)

def simulate_forecast(df, program, periods):
    df_filtered = df[df["program"] == program]
    grouped = df_filtered.groupby("date").apply(
        lambda x: (x["sentiment"] == "positive").sum() / len(x)
    ).reset_index()
    grouped.columns = ["ds", "y"]

    model = Prophet(daily_seasonality=True)
    model.fit(grouped)
    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)

    fig = model.plot(forecast)
    fig.set_size_inches(5, 2.5)

    trend = forecast["yhat"].iloc[-periods:].mean()
    base = grouped["y"].mean()
    delta = trend - base

    if delta > 0.05:
        recommendation = "📈 Empfehlung: Positive Stimmung steigt – Promotion oder Fortsetzung empfohlen."
    elif delta < -0.05:
        recommendation = "📉 Empfehlung: Stimmung sinkt – Inhalte überdenken oder verändern."
    else:
        recommendation = "📊 Empfehlung: Stimmung stabil – keine Maßnahmen notwendig."

    return fig, forecast, grouped, recommendation

program = st.sidebar.selectbox("Wähle ein Programm", ["Master Chef", "The Voice"])
date_range = st.sidebar.date_input("Zeitraum wählen", [datetime.date(2025, 5, 1), datetime.date(2025, 5, 7)])

color_map = {
    "positive": "green",
    "neutral": "lightblue",
    "negative": "red"
}

if tab_choice == "Dashboard":
    df = generate_mock_comments(program, date_range[0], date_range[1])
    df["weekday"] = df["date"].dt.day_name()

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("📄 Kommentare", len(df))
    col_kpi2.metric("😊 Positive", (df["sentiment"] == "positive").sum())
    col_kpi3.metric("☹️ Negative", (df["sentiment"] == "negative").sum())

    st.divider()

    col_main1, col_main2, col_main3 = st.columns([1.2, 2, 2])

    with col_main1:
        st.subheader("📊 Verteilung")
        sentiment_count = df["sentiment"].value_counts().reset_index()
        sentiment_count.columns = ["Sentiment", "Anzahl"]
        fig_pie = px.pie(sentiment_count, names="Sentiment", values="Anzahl", hole=0.4,
                         color="Sentiment", color_discrete_map=color_map)
        st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📝 Beispielkommentare")
        st.dataframe(df[["date", "text", "sentiment"]].sample(5), use_container_width=True)

    with col_main2:
        st.subheader("📈 Sentiment über Zeit")
        df_day = df.groupby(["date", "sentiment"]).size().reset_index(name="Anzahl")
        fig_time = px.bar(df_day, x="date", y="Anzahl", color="sentiment", barmode="group",
                          color_discrete_map=color_map)
        st.plotly_chart(fig_time, use_container_width=True)

        st.subheader("📅 Stimmung nach Wochentag")
        df_wday = df.groupby(["weekday", "sentiment"]).size().reset_index(name="Anzahl")
        fig_wday = px.bar(df_wday, x="weekday", y="Anzahl", color="sentiment", barmode="group",
                          color_discrete_map=color_map)
        st.plotly_chart(fig_wday, use_container_width=True)

    with col_main3:
        st.subheader("🔍 Histogramm")
        fig_hist = px.histogram(df, x="sentiment", color="sentiment",
                                title="Verteilung der Stimmung", color_discrete_map=color_map)
        st.plotly_chart(fig_hist, use_container_width=True)

        st.subheader("📥 Daten herunterladen")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Exportiere als CSV", csv, f"{program}_sentiment.csv", "text/csv")

elif tab_choice == "KI-Planung":
    st.subheader("🤖 KI-gestützte Prognose")
    filename = f"sentiment_data_{program.replace(' ', '_')}.csv"
    if os.path.exists(filename):
        df = pd.read_csv(filename, parse_dates=["date"])
        period_input = st.selectbox("Prognosezeitraum (Tage)", [14, 30])
        if st.button("Prognose anzeigen"):
            fig, forecast, grouped, recommendation = simulate_forecast(df, program, period_input)
            st.markdown(f"**📌 Empfehlung:** {recommendation}")
            st.pyplot(fig)
    else:
        st.warning("Bitte analysiere zuerst Daten im Dashboard.")

elif tab_choice == "Vergleich":
    st.subheader("📈 Vergleich zwischen Programmen")
    compare_programs = st.multiselect("Programme auswählen", ["Master Chef", "The Voice"], default=["Master Chef", "The Voice"])
    df_all = pd.DataFrame()
    for prog in compare_programs:
        file = f"sentiment_data_{prog.replace(' ', '_')}.csv"
        if os.path.exists(file):
            temp = pd.read_csv(file, parse_dates=["date"])
            df_all = pd.concat([df_all, temp])
    if not df_all.empty:
        col1, col2 = st.columns(2)
        with col1:
            df_pos = df_all[df_all["sentiment"] == "positive"]
            pos_trend = df_pos.groupby(["date", "program"]).size().reset_index(name="Anzahl")
            fig_pos = px.line(pos_trend, x="date", y="Anzahl", color="program", title="Positive Kommentare")
            st.plotly_chart(fig_pos, use_container_width=True)
        with col2:
            df_neg = df_all[df_all["sentiment"] == "negative"]
            neg_trend = df_neg.groupby(["date", "program"]).size().reset_index(name="Anzahl")
            fig_neg = px.line(neg_trend, x="date", y="Anzahl", color="program", title="Negative Kommentare")
            st.plotly_chart(fig_neg, use_container_width=True)
    else:
        st.warning("Keine Vergleichsdaten vorhanden.")

elif tab_choice == "Bericht":
    st.subheader("📄 Wochenbericht")
    df = pd.DataFrame()
    for prog in ["Master Chef", "The Voice"]:
        filename = f"sentiment_data_{prog.replace(' ', '_')}.csv"
        if os.path.exists(filename):
            df_prog = pd.read_csv(filename, parse_dates=["date"])
            df = pd.concat([df, df_prog])
    if not df.empty:
        df["KW"] = df["date"].dt.isocalendar().week
        report_programs = st.multiselect("Programme auswählen", ["Master Chef", "The Voice"], default=["Master Chef", "The Voice"])
        df = df[df["program"].isin(report_programs)]
        report = df.groupby(["program", "KW", "sentiment"]).size().unstack(fill_value=0).reset_index()
        st.dataframe(report)
        csv = report.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Bericht herunterladen", csv, "sentiment_report.csv", "text/csv")
    else:
        st.info("Bitte zuerst Daten analysieren.")
