import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="EBYÜ Sismik İzleme", page_icon="🌍", layout="wide")

st.title("🌍 EBYÜ Deprem Bilgi Sistemi ve Canlı Fay Monitörü")
st.markdown("""
Bu platform, güncel veri tablosu üzerinden sismik hareketliliği ve fay hatlarını görselleştirir. 
""")

st.divider()

# --- 1. GEOJSON FAY VERİSİNİ ÇEKME ---
@st.cache_data(show_spinner="Fay hatları yükleniyor...")
def load_faults_geojson():
    url = "https://deprem.ebyu.edu.tr/wp-content/uploads/TurkiyeFaults.geojson"
    try:
        response = requests.get(url, timeout=15)
        return response.json()
    except:
        return None

fay_verisi = load_faults_geojson()

# --- 2. YENİ CSV BAĞLANTISI VE VERİ ÇEKME ---
@st.cache_data(ttl=300)
def get_csv_quakes():
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSuPK5fTjFu6u8LPh7VHCEzDCfNVA_Qg9bQ7qhptcQ5QC4jJrOw5StkeAuir1dffbcfUt4y5D-JATfH/pub?gid=556487398&single=true&output=csv"
    try:
        # Pandas'ın ayırıcıyı (; veya ,) otomatik algılaması için sep=None kullanıyoruz
        df = pd.read_csv(csv_url, sep=None, engine='python')
        
        # Sütun isimlerini güvenli hale getirme (Görseline uygun sıralama)
        df = df.iloc[:, :6] # Sadece ilk 6 sütunu al (gizli boş sütunları yoksay)
        df.columns = ['Tarih', 'Enlem', 'Boylam', 'Derinlik', 'Büyüklük', 'Yer']
        
        # Sayısal dönüşüm (Virgülleri noktaya çevirerek garantiye alıyoruz)
        for col in ['Enlem', 'Boylam', 'Büyüklük', 'Derinlik']:
            df[col] = df[col].astype(str).str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Eksik veya hatalı satırları temizle
        df = df.dropna(subset=['Enlem', 'Boylam', 'Büyüklük'])
        
        return df
    except Exception as e:
        st.error(f"Veri işleme hatası: {e}")
        return pd.DataFrame()

# Uygulamayı çalıştır
df_deprem = get_csv_quakes()

if not df_deprem.empty:
    
    # --- ANA EKRANA ENTEGRE FİLTRELER ---
    st.subheader("🔍 Analiz Araçları")
    col1, col2 = st.columns([3, 1]) # Kaydırma çubuğuna daha fazla alan ayırıyoruz
    
    with col1:
        min_mag = st.slider("Minimum Büyüklük", 0.0, 7.0, 1.5, 0.1)
        df_filtered = df_deprem[df_deprem['Büyüklük'] >= min_mag].copy()
        
    with col2:
        st.metric("Gösterilen Kayıt Sayısı", len(df_filtered))
        
    st.divider() # Filtreler ile harita arasında estetik bir ayraç

    # Renk Kategorileri
    df_filtered['Risk_Kategorisi'] = pd.cut(
        df_filtered['Büyüklük'], 
        bins=[0, 3.5, 5.0, 10], 
        labels=['Düşük (Yeşil)', 'Orta (Sarı)', 'Yüksek (Kırmızı)']
    )
    renk_haritasi = {'Düşük (Yeşil)': 'green', 'Orta (Sarı)': 'orange', 'Yüksek (Kırmızı)': 'red'}

    # Ortak Lejant Ayarı (Sol Üst Köşe, Saydam Arka Plan)
    ortak_lejant_ayari = dict(
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(30, 30, 30, 0.7)",
        bordercolor="gray",
        borderwidth=1,
        title_text="" # Lejant başlığını (Risk Kategorisi) kaldırır, daha temiz durur
    )

    # --- SEKMELER ---
    tab1, tab2, tab3 = st.tabs(["🗺️ Harita", "🧊 3D Kesit", "📋 Veri Listesi"])

    with tab1:
        fig_map = px.scatter_map(
            df_filtered, lat="Enlem", lon="Boylam", color="Risk_Kategorisi",
            color_discrete_map=renk_haritasi, size="Büyüklük",
            hover_name="Yer",
            hover_data={"Derinlik": True, "Tarih": True, "Büyüklük": True},
            size_max=15, zoom=5.5, center={"lat": 39.0, "lon": 38.5},
            map_style="carto-positron"
        )
        if fay_verisi:
            fig_map.update_layout(map_layers=[{
                "sourcetype": "geojson", "source": fay_verisi, "type": "line", 
                "color": "red", "line": {"width": 1.5}
            }])
        
        # Kenar boşluklarını sıfırla ve lejantı sol üste taşı
        fig_map.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0},
            legend=ortak_lejant_ayari
        )
        st.plotly_chart(fig_map, width="stretch")

    with tab2:
        df_filtered['Derinlik_Neg'] = df_filtered['Derinlik'] * -1
        fig_3d = px.scatter_3d(
            df_filtered, x='Boylam', y='Enlem', z='Derinlik_Neg', 
            color='Risk_Kategorisi', color_discrete_map=renk_haritasi, 
            size='Büyüklük', hover_name='Yer', opacity=0.8
        )
        
        # 3D eksen başlıklarını ayarla ve lejantı sol üste taşı
        fig_3d.update_layout(
            scene=dict(zaxis=dict(title='Derinlik (km)')), 
            margin={"r":0,"t":0,"l":0,"b":0},
            legend=ortak_lejant_ayari
        )
        st.plotly_chart(fig_3d, width="stretch")

    with tab3:
        st.dataframe(df_filtered.drop(columns=['Risk_Kategorisi', 'Derinlik_Neg'] if 'Derinlik_Neg' in df_filtered else ['Risk_Kategorisi']), width="stretch", hide_index=True)

else:
    st.error("Veri yüklenemedi. Lütfen CSV bağlantısını ve dosya içeriğini kontrol edin.")