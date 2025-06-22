#!/usr/bin/env python
# coding: utf-8

import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
import folium
from streamlit_folium import st_folium
from matplotlib import cm, colors
import json
import matplotlib.pyplot as plt
from folium.plugins import MarkerCluster

# Style
st.markdown("""
    <style>
        body { background-color: white; }
        .main { background-color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("Peta Sebaran Stasiun BMKG")

# Load data Excel
file_path = "Tugas BMKG_Data Peta.xlsx"
xls = pd.ExcelFile(file_path)

sheets_to_plot = ['PHOBS', 'ARG', 'AWS', 'AAWS', 'ASRS', 'IKLIMMIKRO', 'SOIL']
dfs = {
    sheet: xls.parse(sheet)[[
        'NO STASIUN', 'LINTANG', 'BUJUR', 'DESA', 'KECAMATAN', 'KAB/KOTA', 'PROVINSI'
    ]].dropna(subset=['LINTANG', 'BUJUR']).assign(JENIS=sheet)
    for sheet in sheets_to_plot
}
all_data = pd.concat(dfs.values(), ignore_index=True)
all_center = [all_data['LINTANG'].mean(), all_data['BUJUR'].mean()]

# Sidebar filter
with st.expander("🔍 Filter Peta", expanded=True):
    all_jenis = all_data['JENIS'].unique().tolist()
    selected_jenis_raw = st.multiselect("Jenis Stasiun", options=["Select All"] + all_jenis, default=[])
    selected_jenis = all_jenis if "Select All" in selected_jenis_raw else selected_jenis_raw

    all_provinsi = all_data['PROVINSI'].unique().tolist()
    selected_provinsi = st.selectbox("Pilih Provinsi", options=["All"] + all_provinsi)

    if selected_provinsi != "All":
        filtered_by_prov = all_data[all_data['PROVINSI'] == selected_provinsi]
        all_kabupaten = filtered_by_prov['KAB/KOTA'].unique().tolist()
        selected_kab = st.selectbox("Pilih Kab/Kota", options=["All"] + all_kabupaten)

        if selected_kab != "All":
            filtered_by_kab = filtered_by_prov[filtered_by_prov['KAB/KOTA'] == selected_kab]
            all_kecamatan = filtered_by_kab['KECAMATAN'].unique().tolist()
            selected_kec = st.selectbox("Pilih Kecamatan", options=["All"] + all_kecamatan)
        else:
            selected_kec = "All"
    else:
        selected_kab = selected_kec = "All"

    apply_filter = st.button("Terapkan Filter")

    if apply_filter:
        if not selected_jenis:
            st.warning("Silakan pilih minimal satu jenis stasiun sebelum menerapkan filter.")
        else:
            st.session_state['selected_jenis'] = selected_jenis
            st.session_state['selected_provinsi'] = selected_provinsi
            st.session_state['selected_kab'] = selected_kab
            st.session_state['selected_kec'] = selected_kec

sel_jenis = st.session_state.get('selected_jenis', all_jenis)
sel_provinsi = st.session_state.get('selected_provinsi', "All")
sel_kab = st.session_state.get('selected_kab', "All")
sel_kec = st.session_state.get('selected_kec', "All")

filtered_data = all_data[all_data['JENIS'].isin(sel_jenis)]
if sel_provinsi != "All":
    filtered_data = filtered_data[filtered_data['PROVINSI'] == sel_provinsi]
    if sel_kab != "All":
        filtered_data = filtered_data[filtered_data['KAB/KOTA'] == sel_kab]
        if sel_kec != "All":
            filtered_data = filtered_data[filtered_data['KECAMATAN'] == sel_kec]

prov_summary = filtered_data.groupby('PROVINSI').size().reset_index(name='JUMLAH')

m = folium.Map(location=all_center, zoom_start=5, control_scale=True)

geojson_path = "indonesia_provinces.geojson"
with open(geojson_path, 'r', encoding='utf-8') as f:
    geojson_data = json.load(f)

def style_function(feature):
    prov_name = feature['properties']['state'].upper()
    jumlah = prov_summary[prov_summary['PROVINSI'].str.upper() == prov_name]['JUMLAH']
    count = int(jumlah.values[0]) if not jumlah.empty else 0
    color = cm.YlOrRd(count / prov_summary['JUMLAH'].max()) if prov_summary['JUMLAH'].max() > 0 else (1,1,1,1)
    return {
        'fillOpacity': 0.7,
        'weight': 1,
        'color': 'black',
        'fillColor': colors.to_hex(color)
    }

def popup_function(feature):
    prov_name = feature['properties']['state'].upper()
    prov_data = filtered_data[filtered_data['PROVINSI'].str.upper() == prov_name]
    if prov_data.empty:
        return folium.Popup(f"<b>{prov_name}</b><br>Tidak ada data", max_width=250)
    summary = prov_data.groupby('JENIS').size().reset_index(name='JUMLAH')
    popup_html = f"<b>{prov_name}</b><br>"
    for _, row in summary.iterrows():
        popup_html += f"{row['JENIS']}: {row['JUMLAH']} stasiun<br>"
    return folium.Popup(popup_html, max_width=300)

for feature in geojson_data['features']:
    popup = popup_function(feature)
    folium.GeoJson(
        feature,
        style_function=style_function,
        tooltip=feature['properties']['state'],
        popup=popup
    ).add_to(m)

unique_prov = sorted(all_data['PROVINSI'].unique())
color_palette = plt.cm.get_cmap('tab20b', len(unique_prov))
provinsi_colors = {
    prov: colors.to_hex(color_palette(i)) for i, prov in enumerate(unique_prov)
}

# Cluster only by provinsi
prov_layer = folium.FeatureGroup(name="Cluster Provinsi", show=True).add_to(m)
all_layer = folium.FeatureGroup(name="Semua Marker", show=False).add_to(m)

for provinsi_name, group in filtered_data.groupby("PROVINSI"):
    cluster = MarkerCluster(name=f"{provinsi_name}")
    cluster.add_to(prov_layer)
    for _, row in group.iterrows():
        folium.CircleMarker(
            location=[row['LINTANG'], row['BUJUR']],
            radius=3,
            color=provinsi_colors.get(provinsi_name, 'blue'),
            fill=True,
            fill_color=provinsi_colors.get(provinsi_name, 'blue'),
            fill_opacity=0.5,
            popup=(f"<b>Jenis:</b> {row['JENIS']}<br>"
                   f"<b>Stasiun:</b> {row['NO STASIUN']}<br>"
                   f"<b>Kab/Kota:</b> {row['KAB/KOTA']}<br>"
                   f"<b>Kecamatan:</b> {row['KECAMATAN']}<br>"
                   f"<b>Desa:</b> {row['DESA']}<br>"
                   f"<a href='https://www.google.com/maps?q={row['LINTANG']},{row['BUJUR']}' target='_blank'>📍 Lihat di Google Maps</a>"),
            tooltip=row['NO STASIUN']
        ).add_to(cluster)

for _, row in filtered_data.iterrows():
    folium.CircleMarker(
        location=[row['LINTANG'], row['BUJUR']],
        radius=3,
        color=provinsi_colors.get(row['PROVINSI'], 'blue'),
        fill=True,
        fill_color=provinsi_colors.get(row['PROVINSI'], 'blue'),
        fill_opacity=0.5,
        popup=(f"<b>Jenis:</b> {row['JENIS']}<br>"
               f"<b>Stasiun:</b> {row['NO STASIUN']}<br>"
               f"<b>Kab/Kota:</b> {row['KAB/KOTA']}<br>"
               f"<b>Kecamatan:</b> {row['KECAMATAN']}<br>"
               f"<b>Desa:</b> {row['DESA']}<br>"
               f"<a href='https://www.google.com/maps?q={row['LINTANG']},{row['BUJUR']}' target='_blank'>📍 Lihat di Google Maps</a>"),
        tooltip=row['NO STASIUN']
    ).add_to(all_layer)

folium.LayerControl().add_to(m)

col1, col2 = st.columns([2, 1])
with col1:
    map_data = st_folium(m, width=900, height=600, returned_objects=["last_clicked"], key="map")

from streamlit.components.v1 import html
html("""
<script>
const map = window._last_folium_map;
function updateLayers() {
    const zoom = map.getZoom();
    map.eachLayer(layer => {
        if (layer.options && layer.options.name === "Cluster Provinsi") {
            zoom <= 5 ? map.addLayer(layer) : map.removeLayer(layer);
        } else if (layer.options && layer.options.name === "Semua Marker") {
            zoom >= 6 ? map.addLayer(layer) : map.removeLayer(layer);
        }
    });
}
map.on('zoomend', updateLayers);
updateLayers();
</script>
""", height=0)

with col2:
    st.subheader("Ringkasan Data")
    if not filtered_data.empty:
        st.markdown(f"**Jumlah Stasiun Terpilih:** {len(filtered_data)}")
        st.dataframe(
            filtered_data[['NO STASIUN', 'JENIS', 'PROVINSI', 'KAB/KOTA', 'KECAMATAN', 'DESA']].reset_index(drop=True),
            height=600
        )
    else:
        st.info("Tidak ada data yang sesuai dengan filter yang dipilih.")
